import unittest
from copy import deepcopy
from unittest.mock import MagicMock, patch

from data_juicer.ops.mapper.sentence_augmentation_mapper import SentenceAugmentationMapper
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class SentenceAugmentationMapperTest(DataJuicerTestCaseBase):

    hf_model = 'Qwen/Qwen2-7B-Instruct'

    text_key = "caption1"
    text_key_second = "caption2"

    @classmethod
    def tearDownClass(cls) -> None:
        super().tearDownClass(cls.hf_model)

    def _run_sentence_augmentation_mapper(self):
        op = SentenceAugmentationMapper(
            hf_model=self.hf_model,
            task_sentence="Please replace one entity in this sentence with "
                          "another entity, such as an animal, a vehicle, or a "
                          "piece of furniture. Please only answer with the "
                          "replaced sentence.",
            max_new_tokens=512,
            temperature=0.9,
            top_p=0.95,
            num_beams=1,
            text_key=self.text_key,
            text_key_second=self.text_key_second
        )

        samples = [
            {self.text_key: 'a book is near a cat and a dog'}
        ]

        for sample in samples:
            result = op.process(deepcopy(sample))
            print(f'Output results: {result}')
            self.assertNotEqual(sample, result)

    def test_sentence_augmentation_mapper(self):
        self._run_sentence_augmentation_mapper()

    @patch("data_juicer.ops.mapper.sentence_augmentation_mapper.prepare_model")
    def test_default_uses_huggingface_backend(self, mock_prepare):
        mock_prepare.return_value = lambda device="cpu": None

        SentenceAugmentationMapper(
            hf_model=self.hf_model,
            task_sentence="Rewrite the sentence.",
            text_key=self.text_key,
            text_key_second=self.text_key_second,
        )

        mock_prepare.assert_called_once_with(
            model_type="huggingface",
            pretrained_model_name_or_path=self.hf_model,
        )

    @patch("data_juicer.ops.mapper.sentence_augmentation_mapper.prepare_model")
    @patch("data_juicer.ops.mapper.sentence_augmentation_mapper.get_model")
    def test_api_model_backend(self, mock_get_model, mock_prepare):
        mock_prepare.return_value = lambda device="cpu": None
        api_client = MagicMock(return_value='"a chair is near a cat and a dog"')
        mock_get_model.return_value = api_client

        op = SentenceAugmentationMapper(
            api_model="qwen-turbo",
            api_endpoint="/chat/completions",
            response_path="choices.0.message.content",
            task_sentence="Please replace one entity.",
            max_new_tokens=64,
            temperature=0.7,
            top_p=0.9,
            sampling_params={"seed": 1},
            text_key=self.text_key,
            text_key_second=self.text_key_second,
        )
        result = op.process_single({self.text_key: "a book is near a cat and a dog"})

        mock_prepare.assert_called_once_with(
            model_type="api",
            model="qwen-turbo",
            endpoint="/chat/completions",
            response_path="choices.0.message.content",
        )
        api_client.assert_called_once()
        messages = api_client.call_args.args[0]
        kwargs = api_client.call_args.kwargs
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("a book is near a cat and a dog", messages[1]["content"])
        self.assertEqual(kwargs["max_tokens"], 64)
        self.assertEqual(kwargs["temperature"], 0.7)
        self.assertEqual(kwargs["top_p"], 0.9)
        self.assertEqual(kwargs["seed"], 1)
        self.assertEqual(result[self.text_key_second], "a chair is near a cat and a dog")


if __name__ == '__main__':
    unittest.main()
