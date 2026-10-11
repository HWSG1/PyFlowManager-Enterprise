"""Persistencia local, recuperación tras fallos y progreso por etapa, sin servicios reales."""
import io
import json
import logging
import tempfile
import sys
import types
import unittest
from datetime import datetime
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import Mock, patch
from test_transcripciones_principal import m, bundle, writer, Connection


class StageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "data.sqlite"

    def stage(self, ids):
        stage = m.LocalStage(self.path)
        stage.prepare([{"conversationId": cid} for cid in ids], {}, {}, {})
        return stage

    def test_pending_download_survives_restart_without_redownloading_saved(self):
        stage = self.stage(["1", "2"])
        row = m.aggregate_conversation([bundle(cid="1", text="large\n" * 10000)])
        row[m.MAIN][0]["FECHA_CARGA"] = datetime(2026, 10, 10, 9, 12)
        stage.save(row)
        stage.commit()
        stage.close()
        with_stage = m.LocalStage(self.path, resume=True)
        try:
            self.assertEqual(list(with_stage.pending()), [{"conversationId": "2"}])
            restored = next(with_stage.results())
            self.assertEqual(restored[m.MAIN][0]["TEXT"], row[m.MAIN][0]["TEXT"])
            self.assertEqual(restored[m.MAIN][0]["FECHA_CARGA"], row[m.MAIN][0]["FECHA_CARGA"])
        finally:
            with_stage.close()

    def test_no_hana_before_download_completion(self):
        stage = self.stage(["1"])
        try:
            with patch.object(m, "HanaTranscriptWriter") as hana, self.assertRaises(ValueError):
                m.upload_stage(stage, Mock())
            hana.assert_not_called()
        finally:
            stage.close()

    def test_diagnostics_preserved_without_individual_json_files(self):
        config = types.SimpleNamespace(timezone_name="America/Tegucigalpa", media_type="todos",
            save_transcript_json=True, json_output_dir=str(Path(self.temp.name) / "json"), api_sleep_seconds=0)
        conv = {"conversationId": "1", "participants": [{"purpose": "customer", "sessions": [
            {"sessionId": "a", "mediaType": "message"}]}]}
        payload = {"transcriptId": "t", "phrases": [
            {"text": "primera", "offset": {"unknown": 1}}, {"text": "segunda"}]}
        stage = self.stage(["1"])
        try:
            with patch.object(m, "transcript_urls", return_value=[{"url": "test", "communicationId": "a"}]), \
                 patch.object(m, "download_payload", return_value=payload):
                result = m.aggregate_conversation(m.process_conversation_transcripts(conv, config, "token", {}, {}, Mock()))
            stage.save(result)
            stage.commit()
            stage.close()
            stage = m.LocalStage(self.path, resume=True)
            self.assertEqual(stage.diagnostic_counts(), {"ordering": 1})
            diagnostic = json.loads(stage.db.execute("SELECT payload FROM diagnostics").fetchone()[0])
            self.assertEqual(diagnostic["source"], payload)
            self.assertEqual(next(stage.results())[m.MAIN][0]["TEXT"], "primera\nsegunda")
            self.assertFalse(Path(config.json_output_dir).exists())
            with patch.object(m, "transcript_urls", side_effect=RuntimeError("API failure")):
                failed = m.aggregate_conversation(m.process_conversation_transcripts(conv, config, "token", {}, {}, Mock()))
            stage.save(failed)
            stage.commit()
            self.assertEqual(stage.diagnostic_counts(), {"error": 1})
            self.assertEqual(stage.counts()["errors"], 1)
            self.assertFalse(list(Path(self.temp.name).rglob("*.json")))
        finally:
            stage.close()

    def test_resume_older_stage_adds_diagnostics_table(self):
        stage = self.stage(["1"])
        stage.save(m.aggregate_conversation([bundle(cid="1")]))
        stage.db.execute("DROP TABLE diagnostics")
        stage.commit()
        stage.close()
        stage = m.LocalStage(self.path, resume=True)
        try:
            self.assertEqual(stage.diagnostic_counts(), {})
            self.assertEqual(next(stage.results())[m.MAIN][0]["TEXT"], "customer: hola")
        finally:
            stage.close()

    def test_hana_failure_resumes_only_unconfirmed_batches(self):
        stage = self.stage([str(i) for i in range(4)])
        conn = Connection()
        try:
            for i in range(4):
                stage.save(m.aggregate_conversation([bundle(cid=str(i))]))
            stage.commit()
            stage.set_meta("download_complete", True)
            w = writer(conn)
            w.batch_size = 2
            w.close = lambda: None
            original_flush = w.flush
            def fail_after_first_commit():
                result = original_flush()
                conn.fail_commit = True
                return result
            w.flush = fail_after_first_commit
            with patch.object(m, "HanaTranscriptWriter", return_value=w), redirect_stdout(io.StringIO()):
                with self.assertRaises(RuntimeError):
                    m.upload_stage(stage, Mock())
            self.assertEqual(stage.counts()["upload_pending"], 2)
            self.assertFalse(stage.meta("upload_complete", False))
            stage.close()
            stage = m.LocalStage(self.path, resume=True)
            conn.fail_commit = False
            second = writer(conn)
            second.close = lambda: None
            with patch.object(m, "HanaTranscriptWriter", return_value=second), redirect_stdout(io.StringIO()):
                m.upload_stage(stage, Mock())
            self.assertEqual(second.written_counts[m.MAIN], 2)
            self.assertEqual(stage.counts()["upload_pending"], 0)
            self.assertEqual(conn.db.execute(f"SELECT COUNT(*) FROM BI_SS.{m.MAIN}").fetchone()[0], 4)
        finally:
            stage.close()
            conn.db.close()

    def test_commit_checkpoint_gap_is_safe_to_replay(self):
        stage = self.stage(["1"])
        conn = Connection()
        try:
            stage.save(m.aggregate_conversation([bundle(cid="1")]))
            stage.commit()
            stage.set_meta("download_complete", True)
            w = writer(conn)
            w.close = lambda: None
            with patch.object(m, "HanaTranscriptWriter", return_value=w), patch.object(stage, "mark_uploaded", side_effect=OSError("disk error")), redirect_stdout(io.StringIO()):
                with self.assertRaises(OSError):
                    m.upload_stage(stage, Mock())
            self.assertEqual(stage.counts()["upload_pending"], 1)
            second = writer(conn)
            second.close = lambda: None
            with patch.object(m, "HanaTranscriptWriter", return_value=second), redirect_stdout(io.StringIO()):
                m.upload_stage(stage, Mock())
            self.assertEqual(conn.db.execute(f"SELECT COUNT(*) FROM BI_SS.{m.MAIN}").fetchone()[0], 1)
        finally:
            stage.close()
            conn.db.close()

    def test_progress_only_changes_and_resets_per_stage(self):
        stream = io.StringIO()
        logger = logging.getLogger("stage-test")
        handler = logging.StreamHandler(stream)
        handler.addFilter(m.CompactConsoleFilter())
        logger.handlers = [handler]
        logger.setLevel(logging.INFO)
        logger.propagate = False
        with redirect_stdout(io.StringIO()):
            logger.info("Routine API message")
            for _ in range(1000):
                logger.warning("Orden de transcript | very long diagnostic")
                logger.warning("HTTP 429 | retry")
            for name in ("Descarga", "Carga HANA"):
                progress = m.StageProgress(logger, name)
                for i in range(1000):
                    progress.update(i, 1000)
                progress.update(1000, 1000, finished=True)
                progress.update(1000, 1000, finished=True)
            logger.error("Fatal error")
        lines = stream.getvalue().splitlines()
        self.assertEqual(len(lines), 201)
        self.assertEqual(lines[0], "Descarga | 1%")
        self.assertEqual(lines[99], "Descarga | 100%")
        self.assertEqual(lines[100], "Carga HANA | 1%")
        self.assertEqual(lines[-1], "Fatal error")

    def test_same_file_cannot_be_used_by_two_runs(self):
        stage = self.stage([])
        try:
            with self.assertRaises(Exception):
                m.LocalStage(self.path, resume=True)
        finally:
            stage.close()

    def test_main_resumes_completed_download_without_genesys(self):
        stage = self.stage(["1"])
        stage.save(m.aggregate_conversation([bundle(cid="1")]))
        stage.commit()
        stage.set_meta("download_complete", True)
        stage.close()
        conn = Connection()
        self.addCleanup(conn.db.close)
        config = types.SimpleNamespace(dry_run=False, output_format="csv", output_csv=str(Path(self.temp.name) / "export.csv"))
        w = writer(conn)
        w.close = lambda: None
        with patch.object(sys, "argv", ["test", "--resume-file", str(self.path)]), \
             patch.object(m, "load_config", return_value=config) as load, \
             patch.object(m, "get_access_token", side_effect=AssertionError("Must not contact Genesys")) as token, \
             patch.object(m, "prepare_stage", side_effect=AssertionError("Must not prepare again")), \
             patch.object(m, "HanaTranscriptWriter", return_value=w), \
             patch.object(m, "setup_logger", return_value=Mock()), redirect_stdout(io.StringIO()):
            self.assertEqual(m.main(), 0)
        load.assert_called_once_with(require_genesys=False)
        token.assert_not_called()
        self.assertEqual(conn.db.execute(f"SELECT COUNT(*) FROM BI_SS.{m.MAIN}").fetchone()[0], 1)
        self.assertIn("customer: hola", Path(config.output_csv).read_text(encoding="utf-8-sig"))
        stage = m.LocalStage(self.path, resume=True)
        try:
            self.assertTrue(stage.meta("upload_complete"))
            self.assertTrue(stage.meta("export_complete"))
        finally:
            stage.close()


if __name__ == "__main__":
    unittest.main()
