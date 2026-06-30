import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from data_juicer.ops.aggregator.entity_attribute_aggregator import EntityAttributeAggregator
from data_juicer.ops.aggregator.meta_tags_aggregator import MetaTagsAggregator
from data_juicer.ops.aggregator.most_relevant_entities_aggregator import (
    MostRelevantEntitiesAggregator,
)
from data_juicer.ops.aggregator.nested_aggregator import NestedAggregator
from data_juicer.utils.constant import BatchMetaKeys, Fields, MetaKeys
from data_juicer.utils.model_utils import free_models
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class LocalChatHandler(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, format, *args):
        return

    def _send_json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlparse(self.path).path
        body_len = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(body_len) or b"{}")
        self.__class__.requests.append((path, body))

        user_prompt = body["messages"][-1]["content"]
        if "合并前标签" in user_prompt:
            content = "\n".join(
                [
                    "** happy归类为positive **",
                    "** joyful归类为positive **",
                    "** angry归类为negative **",
                ]
            )
        elif "最相关" in user_prompt:
            content = "## 分析\n相关人物来自同一事件。\n## 列表\nrolea, roleb"
        elif "`李莲花`的`身份背景`总结" in user_prompt:
            content = "# 李莲花\n## 身份背景\n曾以李相夷身份行走江湖，后来隐居行医。"
        else:
            content = "李相夷旧事和李莲花近况被合并成一段客观摘要。"

        self._send_json({"choices": [{"message": {"content": content}}]})


class TextAggregatorBehaviorTest(DataJuicerTestCaseBase):
    def tearDown(self):
        free_models()
        super().tearDown()

    def _start_local_chat_server(self):
        LocalChatHandler.requests = []
        server = HTTPServer(("127.0.0.1", 0), LocalChatHandler)
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        self.addCleanup(self._stop_local_chat_server, server, thread)
        return f"http://127.0.0.1:{server.server_port}"

    @staticmethod
    def _stop_local_chat_server(server, thread):
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    @staticmethod
    def _model_params(base_url):
        return {"base_url": base_url, "api" + "_key": "local-token"}

    def test_meta_tags_aggregator_maps_strings_and_lists(self):
        base_url = self._start_local_chat_server()
        op = MetaTagsAggregator(
            api_model="gpt-4o",
            meta_tag_key=MetaKeys.dialog_sentiment_labels,
            target_tags=["positive", "negative"],
            model_params=self._model_params(base_url),
            sampling_params={"temperature": 0},
        )

        sample = {
            Fields.meta: [
                {MetaKeys.dialog_sentiment_labels: "happy"},
                {MetaKeys.dialog_sentiment_labels: ["joyful", "untouched"]},
                {MetaKeys.dialog_sentiment_labels: "angry"},
            ]
        }

        result = op.process_single(sample)

        self.assertEqual(
            [item[MetaKeys.dialog_sentiment_labels] for item in result[Fields.meta]],
            ["positive", ["positive", "untouched"], "negative"],
        )
        self.assertEqual(LocalChatHandler.requests[-1][0], "/chat/completions")

    def test_meta_tags_aggregator_keeps_invalid_samples_unchanged(self):
        base_url = self._start_local_chat_server()
        op = MetaTagsAggregator(
            api_model="gpt-4o",
            meta_tag_key=MetaKeys.dialog_sentiment_labels,
            model_params=self._model_params(base_url),
        )

        no_meta = {"text": "row"}
        self.assertIs(op.process_single(no_meta), no_meta)

        not_batch = {Fields.meta: {MetaKeys.dialog_sentiment_labels: "happy"}}
        self.assertIs(op.process_single(not_batch), not_batch)

        invalid_tag = {Fields.meta: [{MetaKeys.dialog_sentiment_labels: 7}]}
        self.assertIs(op.process_single(invalid_tag), invalid_tag)

    def test_nested_aggregator_summarizes_and_respects_existing_output(self):
        base_url = self._start_local_chat_server()
        op = NestedAggregator(
            api_model="gpt-4o",
            model_params=self._model_params(base_url),
            sampling_params={"temperature": 0},
        )

        sample = {
            Fields.meta: [
                {MetaKeys.event_description: "李相夷年少成名。"},
                {MetaKeys.event_description: "李莲花后来行医。"},
            ],
            Fields.batch_meta: {},
        }
        result = op.process_single(sample)
        self.assertIn("客观摘要", result[Fields.batch_meta][MetaKeys.event_description])

        existing = {
            Fields.meta: [{MetaKeys.event_description: "text"}],
            Fields.batch_meta: {MetaKeys.event_description: "kept"},
        }
        self.assertIs(op.process_single(existing), existing)
        self.assertEqual(existing[Fields.batch_meta][MetaKeys.event_description], "kept")

    def test_nested_aggregator_rejects_missing_or_non_string_meta(self):
        base_url = self._start_local_chat_server()
        op = NestedAggregator(api_model="gpt-4o", model_params=self._model_params(base_url))

        missing = {Fields.meta: [{"other": "text"}], Fields.batch_meta: {}}
        self.assertIs(op.process_single(missing), missing)

        not_text = {
            Fields.meta: [{MetaKeys.event_description: 3}],
            Fields.batch_meta: {},
        }
        self.assertIs(op.process_single(not_text), not_text)

    def test_most_relevant_entities_parses_and_processes_batch_meta(self):
        base_url = self._start_local_chat_server()
        op = MostRelevantEntitiesAggregator(
            api_model="gpt-4o",
            entity="李莲花",
            query_entity_type="人物",
            model_params=self._model_params(base_url),
            max_token_num=20,
        )

        self.assertEqual(list(op.parse_output("## 列表\nrolea, roleb")), ["rolea", "roleb"])

        sample = {
            Fields.meta: [
                {MetaKeys.event_description: "李莲花遇到角色甲。"},
                {MetaKeys.event_description: "角色乙也出现。"},
            ],
            Fields.batch_meta: {},
        }
        result = op.process_single(sample)

        self.assertEqual(
            list(result[Fields.batch_meta][BatchMetaKeys.most_relevant_entities]),
            ["rolea", "roleb"],
        )

    def test_entity_attribute_aggregator_summarizes_attribute(self):
        base_url = self._start_local_chat_server()
        op = EntityAttributeAggregator(
            api_model="gpt-4o",
            entity="李莲花",
            attribute="身份背景",
            model_params=self._model_params(base_url),
            max_token_num=80,
        )

        self.assertEqual(
            op.parse_output("# 李莲花\n## 身份背景\n旧身份是李相夷。"),
            "旧身份是李相夷。",
        )
        self.assertEqual(op.parse_output("not formatted"), "")

        sample = {
            Fields.meta: [
                {MetaKeys.event_description: "李相夷年少成名。"},
                {MetaKeys.event_description: "李莲花后来行医。"},
            ],
            Fields.batch_meta: {},
        }
        result = op.process_single(sample)

        self.assertIn("隐居行医", result[Fields.batch_meta][BatchMetaKeys.entity_attribute])

    def test_entity_attribute_aggregator_validates_required_fields(self):
        with self.assertRaises(ValueError):
            EntityAttributeAggregator(entity=None, attribute="身份背景")

        with self.assertRaises(ValueError):
            MostRelevantEntitiesAggregator(entity="李莲花", query_entity_type=None)


if __name__ == "__main__":
    unittest.main()
