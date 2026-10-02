"""Pruebas locales sin llamadas a Genesys ni a SAP HANA."""
import copy
import importlib.util
import io
import logging
import re
import sqlite3
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from contextlib import ExitStack, redirect_stdout


SCRIPT = Path(__file__).resolve().parents[1] / "runtime/scripts/GNS_Extractor_Transcripciones_HANA/GNS_Extractor_Transcripciones_HANA.py"
spec = importlib.util.spec_from_file_location("extractor_main_only", SCRIPT)
m = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = m
with patch.dict(sys.modules, {"requests": types.SimpleNamespace(Response=object)}):
    spec.loader.exec_module(m)


def bundle(cid="c1", tid="t1", comm="a", text="hola", media="voice", start=200):
    return m.build_bundle(
        {"CONVERSATION_ID": cid, "ORIGINATING_DIRECTION": "inbound"},
        {"transcriptId": tid, "mediaType": media, "phrases": [
            {"phraseIndex": 0, "text": text, "startTimeMs": start, "purpose": "customer"}
        ]}, {"communicationId": comm}, "customer")


class Connection:
    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("ATTACH DATABASE ':memory:' AS BI_SS")
        columns = [f'"{n}" TEXT' for n in m.MAIN_COLUMNS]
        self.db.execute(f'CREATE TABLE BI_SS.{m.MAIN} (' + ','.join(columns) + ', PRIMARY KEY(CONVERSATION_ID))')
        self.commits = 0
        self.rollbacks = 0
        self.fail_commit = False

    def cursor(self):
        return self.db.cursor()

    def commit(self):
        if self.fail_commit:
            raise RuntimeError("Simulated failure")
        self.db.commit()
        self.commits += 1

    def rollback(self):
        self.db.rollback()
        self.rollbacks += 1


def writer(conn):
    w = m.HanaTranscriptWriter.__new__(m.HanaTranscriptWriter)
    w.conn, w.logger = conn, logging.getLogger("test")
    w.capacities, w.buffer, w.written_counts = {}, [], {m.MAIN: 0}
    w.batch_size, w.batch_text_limit, w.buffer_text_chars = 100, 8000000, 0
    return w


class MainOnlyTests(unittest.TestCase):
    def test_text_order_count_and_duplicates(self):
        a = bundle(text="segunda")
        b = bundle(tid="t2", comm="b", text="primera", media="message", start=100)
        duplicate = copy.deepcopy(a)
        duplicate[m.MAIN][0]["COMMUNICATION_ID"] = "z"
        result = m.aggregate_conversation([a, b, duplicate])
        row = result[m.MAIN][0]
        self.assertEqual(row["TEXT"], "customer: primera\ncustomer: segunda")
        self.assertEqual(row["PHRASES_COUNT"], 2)
        self.assertEqual(row["MEDIA_TYPE"], "voice/message")
        self.assertEqual(set(result), {m.MAIN})
        self.assertEqual(len(m.MAIN_COLUMNS), 18)
        self.assertEqual(set(m.STORAGE_TABLES), {m.MAIN})

    def test_ignores_unneeded_analytics_and_scores(self):
        transcript = {"transcriptId": "x", "duration": "not numeric", "analytics": "unused",
                      "participants": "unused", "phrases": [{"text": "hola", "confidence": "bad",
                      "words": "unused", "alternatives": "unused", "offsetMs": {"milliseconds": 12}}]}
        result = m.build_bundle({"CONVERSATION_ID": "c"}, transcript, {"communicationId": "a"}, "customer")
        self.assertEqual(result["_phrases"][0]["OFFSET_MS"], 12)
        self.assertEqual(m.aggregate_conversation([result])[m.MAIN][0]["TEXT"], "hola")

    def test_conflicting_transcript_text_is_not_silently_discarded(self):
        with self.assertRaises(ValueError):
            m.aggregate_conversation([bundle(text="one"), bundle(comm="b", text="two")])

    def test_missing_ids_preserve_distinct_texts(self):
        a = m.build_bundle({"CONVERSATION_ID": "c"}, {"phrases": [{"text": "a"}]}, {"communicationId": "s", "recordingId": "r"}, None)
        b = m.build_bundle({"CONVERSATION_ID": "c"}, {"phrases": [{"text": "b"}]}, {"communicationId": "s", "recordingId": "r"}, None)
        self.assertEqual(m.aggregate_conversation([a, b])[m.MAIN][0]["PHRASES_COUNT"], 2)

    def test_reload_rollback_and_partial_protection_without_child_tables(self):
        c = Connection()
        self.addCleanup(c.db.close)
        w = writer(c)
        w.add(m.aggregate_conversation([bundle()]))
        w.flush()
        w.add(m.aggregate_conversation([bundle(text="updated")]))
        w.flush()
        error = m.state_bundle({"CONVERSATION_ID": "c1"}, "other", "ERROR", "failure")
        w.add(m.aggregate_conversation([bundle(text="partial"), error]))
        w.flush()
        query = f'SELECT TEXT FROM BI_SS.{m.MAIN}'
        self.assertEqual(c.db.execute(query).fetchall(), [("customer: updated",)])
        c.fail_commit = True
        w.add(m.aggregate_conversation([bundle(text="rollback")]))
        with self.assertRaises(RuntimeError):
            w.flush()
        self.assertEqual(c.db.execute(query).fetchall(), [("customer: updated",)])
        self.assertEqual(c.rollbacks, 1)

    def test_batch_100_and_text_memory_limit(self):
        c = Connection()
        self.addCleanup(c.db.close)
        w = writer(c)
        for i in range(100):
            w.add(m.aggregate_conversation([bundle(cid=str(i))]))
        self.assertEqual(c.commits, 1)
        self.assertEqual(w.written_counts[m.MAIN], 100)
        w.batch_text_limit = 1
        w.add(m.aggregate_conversation([bundle(cid="next")]))
        self.assertEqual(c.commits, 2)
        self.assertEqual(w.buffer_text_chars, 0)

    def test_empty_text_never_touches_database(self):
        w = writer(Mock())
        for text in (None, "", " \n\t"):
            w.add(m.aggregate_conversation([bundle(text=text)]))
        w.flush()
        self.assertEqual(w.conn.mock_calls, [])

    def test_only_principal_schema_is_queried(self):
        class Cursor:
            def execute(self, query, args):
                self.query = query
                assert args == ("BI_SS", m.MAIN)
            def fetchall(self):
                if "SYS.CONSTRAINTS" in self.query:
                    return [("CONVERSATION_ID",)]
                return [(name, kind.split("(")[0], int(re.search(r"\d+", kind).group()) if "(" in kind else 0, 0)
                        for name, kind in m.STORAGE_TABLES[m.MAIN]]
            def close(self):
                pass
        w = writer(types.SimpleNamespace(cursor=Cursor))
        w.validate_schema()

    def test_duplicate_download_cached_and_no_contact_enrichment(self):
        config = types.SimpleNamespace(timezone_name="America/Tegucigalpa", media_type="todos",
            output_mode="transcript_campania", save_transcript_json=False, json_output_dir="", api_sleep_seconds=0)
        conv = {"conversationId": "c", "participants": [{"purpose": "customer", "sessions": [
            {"sessionId": "a", "mediaType": "message"}, {"sessionId": "b", "mediaType": "message"}]}]}
        payload = {"transcriptId": "t", "phrases": [{"text": "hola"}]}
        def urls(config, token, cid, comm, logger):
            return [{"url": "https://example.test/signed", "communicationId": comm}]
        with patch.object(m, "transcript_urls", side_effect=urls), patch.object(m, "download_payload", return_value=payload) as download:
            result = m.process_conversation_transcripts(conv, config, "token", {}, {}, logging.getLogger("test"))
        self.assertEqual(download.call_count, 1)
        self.assertEqual(m.aggregate_conversation(result)[m.MAIN][0]["PHRASES_COUNT"], 1)
        self.assertFalse(hasattr(m, "fetch_contact_from_genesys"))

    def test_http_sessions_reused_and_download_isolated(self):
        m.close_http_sessions()
        self.addCleanup(m.close_http_sessions)
        with patch.object(m.requests, "Session", create=True, side_effect=lambda: Mock()) as factory:
            api = m.http_session()
            self.assertIs(m.http_session(), api)
            media = m.http_session(download=True)
            self.assertIsNot(api, media)
            self.assertEqual(factory.call_count, 2)
            m.close_http_sessions()
            api.close.assert_called_once()
            media.close.assert_called_once()

    def test_main_pipeline_includes_only_text_and_counts_errors(self):
        config = types.SimpleNamespace(dry_run=False, timezone_name="America/Tegucigalpa",
            output_mode="solo_transcript", conversation_id="", max_conversations=0, max_transcript_workers=2)
        hana, output = Mock(), Mock()
        hana.capacities = {}
        log = Mock()
        def process(conv, *args):
            cid = conv["conversationId"]
            if cid == "0":
                return [m.state_bundle({"CONVERSATION_ID": cid}, "comm", "ERROR", "failed")]
            return [bundle(cid=cid, text="hola" if cid == "9" else " \t")]
        replacements = {
            "setup_logger": lambda: log, "load_config": lambda: config,
            "parse_dates": lambda *a: ("start", "end", "test"),
            "HanaTranscriptWriter": lambda *a: hana, "OutputWriter": lambda *a: output,
            "get_access_token": lambda *a: "token", "apply_resolved_filters": lambda *a: config,
            "get_wrapup_catalog": lambda *a: {}, "get_queue_catalog": lambda *a: {},
            "validate_filter_safety": lambda *a: None, "create_conversation_details_job": lambda *a: "job",
            "wait_details_job": lambda *a: None,
            "fetch_details_job_results": lambda *a: [{"conversationId": str(i)} for i in range(10)],
            "conversation_matches_post_filters": lambda *a: True, "process_conversation_transcripts": process,
        }
        log.handlers = []
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, "argv", ["test"]))
            stack.enter_context(redirect_stdout(io.StringIO()))
            for key, value in replacements.items():
                stack.enter_context(patch.object(m, key, value))
            self.assertEqual(m.main(), 1)
        hana.add.assert_called_once()
        output.add.assert_called_once()
        self.assertEqual(hana.add.call_args.args[0][m.MAIN][0]["CONVERSATION_ID"], "9")
        output.campaign.assert_not_called()
        output.finish.assert_called_once()
        summaries = [call for call in log.info.call_args_list if str(call.args[0]).startswith("Finalizado")]
        self.assertEqual(summaries[0].args[1:4], (1, 9, 1))


if __name__ == "__main__":
    unittest.main()
