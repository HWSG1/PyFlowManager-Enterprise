"""Pruebas sin credenciales ni llamadas a Genesys."""
import importlib.util
import logging
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("extractor", Path(__file__).with_name("GNS_Extractor_Transcripciones.py"))
extractor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = extractor
spec.loader.exec_module(extractor)


class FilterTests(unittest.TestCase):
    def config(self, **values):
        with patch.dict(os.environ, {"GENESYS_CLIENT_ID": "test", "GENESYS_CLIENT_SECRET": "test", **values}, clear=True), patch.object(extractor, "load_dotenv"):
            return extractor.load_config()

    def conversation(self, media="voice", purpose="ivr"):
        return {"conversationId": "conversation", "originatingDirection": "inbound", "participants": [
            {"purpose": purpose, "sessions": [{"sessionId": "session", "mediaType": media,
              "flow": {"flowId": "flow-a"}, "segments": [{"segmentType": "interact"}]}]}
        ]}

    def test_default_keeps_ivr_without_agent_or_wrapup(self):
        config = self.config()
        self.assertTrue(extractor.conversation_matches_post_filters(self.conversation(), config))
        body = extractor.build_details_job_body("start", "end", config)
        self.assertNotIn("segmentFilters", body)
        self.assertNotIn("conversationFilters", body)

    def test_agent_is_optional_and_does_not_require_wrapup(self):
        config = self.config(PARTICIPANT_PURPOSE="agent")
        self.assertFalse(extractor.conversation_matches_post_filters(self.conversation(), config))
        self.assertTrue(extractor.conversation_matches_post_filters(self.conversation(purpose="agent"), config))

    def test_flow_and_agent_can_be_in_different_sessions(self):
        config = self.config(FLOW_SELECTION_ID="flow-a", PARTICIPANT_PURPOSE="agent")
        conv = self.conversation()
        conv["participants"].append({"purpose": "agent", "sessions": [{"sessionId": "agent-session", "mediaType": "voice"}]})
        self.assertTrue(extractor.conversation_matches_post_filters(conv, config))
        config.flow_id = "other"
        self.assertFalse(extractor.conversation_matches_post_filters(conv, config))

    def test_manual_flow_id_has_priority(self):
        self.assertEqual(self.config(FLOW_ID="manual", FLOW_SELECTION_ID="selected").flow_id, "manual")
        self.assertEqual(self.config(FLOW_SELECTION_ID="selected").flow_id, "selected")

    def test_query_filters(self):
        config = self.config(FLOW_ID="flow-a", MEDIA_TYPE="email", PARTICIPANT_PURPOSE="workflow", ORIGINAL_DIRECTION="outbound")
        body = extractor.build_details_job_body("start", "end", config)
        predicates = [p for f in body["segmentFilters"] for p in f["predicates"]]
        self.assertEqual({p["dimension"]: p["value"] for p in predicates}, {"flowId": "flow-a", "mediaType": "email", "purpose": "workflow"})
        self.assertEqual(body["conversationFilters"][0]["predicates"][0]["dimension"], "originatingDirection")

    def test_digital_media_and_original_direction(self):
        for media in ("email", "message", "chat"):
            config = self.config(MEDIA_TYPE=media, ORIGINAL_DIRECTION="inbound")
            conv = self.conversation(media=media)
            self.assertTrue(extractor.conversation_matches_post_filters(conv, config))
            self.assertEqual(len(extractor.obtener_session_ids_para_transcript(conv, media)), 1)
            self.assertEqual(extractor.obtener_session_ids_para_transcript(conv, "voice"), [])
            conv["originatingDirection"] = "outbound"
            self.assertFalse(extractor.conversation_matches_post_filters(conv, config))

    def test_missing_transcript_keeps_conversation(self):
        config = self.config(MEDIA_TYPE="message")
        with patch.object(extractor, "obtener_transcript_url", return_value=None):
            rows, missing, errors = extractor.process_conversation_transcripts(
                self.conversation(media="message"), 1, 1, config, "token", {}, {}, logging.getLogger("test"))
        self.assertEqual(len(rows), 1)
        self.assertEqual(missing, 1)
        self.assertEqual(errors, [])
        self.assertEqual(rows[0]["transcript_estado"], "SIN_TRANSCRIPCION_API")

    def test_catalog_selections_resolve_ids_without_name_lookup(self):
        import json
        for field in ("user", "queue", "campaign", "contact_list", "wrapup_code"):
            config = self.config(**{field.upper() + "_NAME": json.dumps([
                {"id": "id-a", "name": "Nombre; con coma,"}, {"id": "id-b", "name": "Nombre repetido"}
            ])})
            with patch.object(extractor, "paged_get_entities", side_effect=AssertionError("No debe consultar nombres")):
                result = extractor.apply_resolved_filters(config, "token", logging.getLogger("test"))
            self.assertEqual(getattr(result, field + "_id"), "id-a;id-b")
            self.assertEqual(getattr(result, field + "_name"), "")

    def test_manual_id_overrides_catalog_selection(self):
        config = self.config(QUEUE_ID="manual", QUEUE_NAME='[{"id":"selected","name":"Cola"}]')
        result = extractor.apply_resolved_filters(config, "token", logging.getLogger("test"))
        self.assertEqual(result.queue_id, "manual")

    def test_invalid_choices_fail(self):
        for key in ("MEDIA_TYPE", "PARTICIPANT_PURPOSE", "ORIGINAL_DIRECTION"):
            with self.assertRaises(ValueError):
                self.config(**{key: "invalid"})


if __name__ == "__main__":
    unittest.main()
