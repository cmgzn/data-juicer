import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from data_juicer.ops.mapper.dialog_intent_detection_mapper import DialogIntentDetectionMapper
from data_juicer.ops.mapper.dialog_sentiment_detection_mapper import (
    DialogSentimentDetectionMapper,
)
from data_juicer.ops.mapper.dialog_sentiment_intensity_mapper import (
    DialogSentimentIntensityMapper,
)
from data_juicer.ops.mapper.dialog_topic_detection_mapper import DialogTopicDetectionMapper
from data_juicer.utils.constant import Fields, MetaKeys
from data_juicer.utils.model_utils import free_models
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class LocalDialogHandler(BaseHTTPRequestHandler):
    requests = []

    def log_message(self, format, *args):
        return

    def do_POST(self):
        path = urlparse(self.path).path
        body_len = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(body_len) or b"{}")
        self.__class__.requests.append((path, body))

        system_prompt = body["messages"][0]["content"]
        if "意图" in system_prompt:
            content = "意图分析：用户在请求可执行建议。\n意图类别：请求建议\n"
        elif "情绪值" in system_prompt:
            content = "情绪分析：用户态度积极但仍有疑问。\n情绪值：2\n"
        elif "情感" in system_prompt or "情绪" in system_prompt:
            content = "情感分析：用户表达认可和好奇。\n情感类别：积极\n"
        else:
            content = "话题分析：用户围绕模型评测展开讨论。\n话题类别：技术\n"

        payload = json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class DialogDetectionLocalAPITest(DataJuicerTestCaseBase):
    def tearDown(self):
        free_models()
        super().tearDown()

    def _start_local_dialog_server(self):
        LocalDialogHandler.requests = []
        server = HTTPServer(("127.0.0.1", 0), LocalDialogHandler)
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        self.addCleanup(self._stop_local_dialog_server, server, thread)
        return f"http://127.0.0.1:{server.server_port}"

    @staticmethod
    def _stop_local_dialog_server(server, thread):
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

    @staticmethod
    def _client_params(base_url):
        return {"base_url": base_url, "api" + "_key": "local-token"}

    def _sample(self):
        return {
            "history": [["你好", "你好，我可以帮你分析数据。"]],
            "query": "请帮我解释覆盖率结果，并给出下一步建议。",
            "response": "可以。先确认基线，再补行为测试，最后合并 coverage。",
        }

    def test_dialog_detection_mappers_process_local_chat_responses(self):
        base_url = self._start_local_dialog_server()
        params = self._client_params(base_url)

        intent = DialogIntentDetectionMapper(
            api_model="gpt-4o",
            intent_candidates=["请求建议", "信息查找"],
            model_params=params,
            max_round=1,
            max_query_chars_for_prompt=12,
            max_response_chars_for_prompt=16,
        )
        sentiment = DialogSentimentDetectionMapper(
            api_model="gpt-4o",
            sentiment_candidates=["积极", "中性"],
            model_params=params,
            max_round=1,
        )
        intensity = DialogSentimentIntensityMapper(
            api_model="gpt-4o",
            model_params=params,
            max_round=1,
        )
        topic = DialogTopicDetectionMapper(
            api_model="gpt-4o",
            topic_candidates=["技术", "生活"],
            model_params=params,
            max_round=1,
        )

        sample = self._sample()
        for op in [intent, sentiment, intensity, topic]:
            sample = op.process_single(sample)

        meta = sample[Fields.meta]
        self.assertEqual(meta[MetaKeys.dialog_intent_labels], ["请求建议"])
        self.assertEqual(meta[MetaKeys.dialog_sentiment_labels], ["积极"])
        self.assertEqual(meta[MetaKeys.dialog_sentiment_intensity], [2, 2])
        self.assertEqual(meta[MetaKeys.dialog_topic_labels], ["技术"])
        self.assertEqual(len(LocalDialogHandler.requests), 8)

    def test_dialog_detection_parsers_and_existing_meta_short_circuit(self):
        base_url = self._start_local_dialog_server()
        params = self._client_params(base_url)

        intent = DialogIntentDetectionMapper(api_model="gpt-4o", model_params=params)
        self.assertEqual(
            intent.parse_output("意图分析：请求资料。\n意图类别：信息查找\n"),
            ("请求资料。", "信息查找"),
        )
        self.assertEqual(intent.parse_output("unstructured"), ("", ""))

        intensity = DialogSentimentIntensityMapper(api_model="gpt-4o", model_params=params)
        self.assertEqual(
            intensity.parse_output("情绪分析：明显积极。\n情绪值：3\n"),
            ("明显积极。", 3),
        )
        self.assertEqual(intensity.parse_output("unstructured"), ("", 0))

        sample = self._sample()
        sample[Fields.meta] = {
            MetaKeys.dialog_topic_labels: ["existing"],
            MetaKeys.dialog_topic_labels_analysis: ["kept"],
        }
        topic = DialogTopicDetectionMapper(api_model="gpt-4o", model_params=params)
        self.assertIs(topic.process_single(sample), sample)
        self.assertEqual(sample[Fields.meta][MetaKeys.dialog_topic_labels], ["existing"])


if __name__ == "__main__":
    unittest.main()
