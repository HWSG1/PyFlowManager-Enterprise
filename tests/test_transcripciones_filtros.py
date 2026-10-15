"""Selección múltiple sin servicios externos."""
import json
import os
import unittest
from unittest.mock import Mock, patch
from test_transcripciones_principal import m


class MultipleFiltersTests(unittest.TestCase):
    def config(self, **values):
        with patch.dict(os.environ, values, clear=True):
            return m.load_config(require_genesys=False)

    def test_multiple_values_are_or_within_each_dimension(self):
        config = self.config(FLOW_SELECTION_ID="f1;f2", QUEUE_ID="q1;q2",
            MEDIA_TYPE="voice;message", PARTICIPANT_PURPOSE="botflow;agent",
            ORIGINAL_DIRECTION="inbound;outbound")
        body = m.build_details_job_body("start", "end", config)
        groups = {group["predicates"][0]["dimension"]: group
                  for group in body["segmentFilters"] + body["conversationFilters"]}
        for dimension, expected in {"flowId": ["f1", "f2"], "queueId": ["q1", "q2"],
                "mediaType": ["voice", "message"], "purpose": ["botflow", "agent"],
                "originatingDirection": ["inbound", "outbound"]}.items():
            self.assertEqual(groups[dimension]["type"], "or")
            self.assertEqual([p["value"] for p in groups[dimension]["predicates"]], expected)
        conversation = {"originatingDirection": "outbound", "participants": [
            {"purpose": "botflow", "sessions": [{"flow": {"flowId": "f2"}, "mediaType": "message", "sessionId": "a"}]},
            {"purpose": "agent", "sessions": [{"mediaType": "voice", "sessionId": "b"},
                {"mediaType": "email", "sessionId": "c"}]}]}
        self.assertTrue(m.conversation_matches_post_filters(conversation, config))
        self.assertEqual(len(m.obtener_session_ids_para_transcript(conversation, config.media_type)), 2)
        conversation["participants"][0]["sessions"][0]["flow"]["flowId"] = "excluded"
        self.assertFalse(m.conversation_matches_post_filters(conversation, config))

    def test_catalog_multi_selections_preserve_ids_without_name_lookup(self):
        selected = json.dumps([{"id": "id1", "name": "One"}, {"id": "id2", "name": "Two"}])
        config = self.config(**{key: selected for key in
            ("QUEUE_NAME", "USER_NAME", "CAMPAIGN_NAME", "CONTACT_LIST_NAME", "WRAPUP_CODE_NAME")})
        m.apply_resolved_filters(config, "unused", Mock())
        for field in ("queue", "user", "campaign", "contact_list", "wrapup_code"):
            self.assertEqual(getattr(config, field + "_id"), "id1;id2")

    def test_legacy_defaults_and_manual_flow_precedence(self):
        config = self.config(FLOW_SELECTION_ID="old-flow", FLOW_ID="manual1;manual2")
        self.assertEqual(config.flow_id, "manual1;manual2")
        self.assertEqual(m.build_details_job_body("a", "b", self.config()),
            {"order": "asc", "orderBy": "conversationStart", "interval": "a/b"})
        self.assertEqual(self.config(MEDIA_TYPE="").media_type, "todos")
        with self.assertRaises(ValueError):
            self.config(MEDIA_TYPE="voice;invalid")


if __name__ == "__main__":
    unittest.main()
