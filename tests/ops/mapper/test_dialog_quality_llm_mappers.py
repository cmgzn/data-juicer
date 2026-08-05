# Copyright 2025 The Data-Juicer Authors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the dialog/agent quality LLM mappers that subclass
_DialogTurnQualityMapper or _DialogQualityLLMMapperBase.

Covers unit tests (no LLM calls) and integration tests (actual API calls).
"""

import unittest

from data_juicer.core.data import NestedDataset as Dataset
from data_juicer.ops.mapper.dialog_non_repetition_mapper import (
    DialogNonRepetitionMapper,
)
from data_juicer.ops.mapper.dialog_clarification_quality_mapper import (
    DialogClarificationQualityMapper,
)
from data_juicer.ops.mapper.dialog_memory_consistency_mapper import (
    DialogMemoryConsistencyMapper,
)
from data_juicer.ops.mapper.dialog_proactivity_mapper import (
    DialogProactivityMapper,
)
from data_juicer.ops.mapper.dialog_error_recovery_mapper import (
    DialogErrorRecoveryMapper,
)
from data_juicer.ops.mapper.dialog_topic_shift_mapper import (
    DialogTopicShiftMapper,
)
from data_juicer.ops.mapper.dialog_coreference_mapper import (
    DialogCoreferenceMapper,
)
from data_juicer.ops.mapper.agent_trace_coherence_mapper import (
    AgentTraceCoherenceMapper,
)
from data_juicer.ops.mapper.agent_tool_relevance_mapper import (
    AgentToolRelevanceMapper,
)
from data_juicer.utils.constant import DEFAULT_API_MODEL, Fields, MetaKeys
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase, skip_if_from_fork


# ---------------------------------------------------------------------------
# Unit tests: no LLM calls, validate class attributes & edge-case paths
# ---------------------------------------------------------------------------


class AllDialogMappersContractTest(DataJuicerTestCaseBase):
    """Single test validating the contract all dialog mappers must satisfy."""

    MAPPER_CLASSES = [
        DialogNonRepetitionMapper,
        DialogClarificationQualityMapper,
        DialogMemoryConsistencyMapper,
        DialogProactivityMapper,
        DialogErrorRecoveryMapper,
        DialogTopicShiftMapper,
        DialogCoreferenceMapper,
        AgentTraceCoherenceMapper,
        AgentToolRelevanceMapper,
    ]

    def test_all_mappers_have_op_name_and_meta_key(self):
        for cls in self.MAPPER_CLASSES:
            with self.subTest(cls=cls.__name__):
                self.assertTrue(len(cls.OP_NAME) > 0)
                self.assertTrue(len(cls.META_KEY) > 0)

    def test_all_mappers_produce_nonempty_system_prompt(self):
        for cls in self.MAPPER_CLASSES:
            with self.subTest(cls=cls.__name__):
                op = cls(api_model="any-model")
                prompt = op._system_prompt()
                self.assertIsInstance(prompt, str)
                self.assertGreater(len(prompt), 10)


class DialogNonRepetitionUnitTest(DataJuicerTestCaseBase):
    """Unit tests for DialogNonRepetitionMapper (no API calls)."""


    def test_process_single_empty_dialog_skipped(self):
        op = DialogNonRepetitionMapper(api_model="any-model")
        sample = {"dialog_history": []}
        result = op.process_single(sample)
        meta = result[Fields.meta]
        self.assertIn(MetaKeys.dialog_non_repetition, meta)
        self.assertTrue(meta[MetaKeys.dialog_non_repetition]["skipped"])
        self.assertEqual(
            meta[MetaKeys.dialog_non_repetition]["reason"], "empty_input"
        )

    def test_process_single_existing_meta_no_overwrite(self):
        op = DialogNonRepetitionMapper(api_model="any-model", overwrite=False)
        existing = {"score": 4.0, "reason": "pre-existing"}
        sample = {
            "dialog_history": [("hi", "hello")],
            Fields.meta: {MetaKeys.dialog_non_repetition: existing},
        }
        result = op.process_single(sample)
        self.assertEqual(
            result[Fields.meta][MetaKeys.dialog_non_repetition], existing
        )


class DialogClarificationQualityUnitTest(DataJuicerTestCaseBase):
    """Unit tests for DialogClarificationQualityMapper (no API calls)."""


    def test_process_single_empty_dialog_skipped(self):
        op = DialogClarificationQualityMapper(api_model="any-model")
        sample = {"dialog_history": []}
        result = op.process_single(sample)
        meta = result[Fields.meta]
        self.assertIn(MetaKeys.dialog_clarification_quality, meta)
        self.assertTrue(meta[MetaKeys.dialog_clarification_quality]["skipped"])
        self.assertEqual(
            meta[MetaKeys.dialog_clarification_quality]["reason"], "empty_input"
        )

    def test_process_single_existing_meta_no_overwrite(self):
        op = DialogClarificationQualityMapper(
            api_model="any-model", overwrite=False
        )
        existing = {"score": 3.0, "reason": "pre-existing"}
        sample = {
            "dialog_history": [("hi", "hello")],
            Fields.meta: {MetaKeys.dialog_clarification_quality: existing},
        }
        result = op.process_single(sample)
        self.assertEqual(
            result[Fields.meta][MetaKeys.dialog_clarification_quality], existing
        )


class DialogMemoryConsistencyUnitTest(DataJuicerTestCaseBase):
    """Unit tests for DialogMemoryConsistencyMapper (no API calls)."""


    def test_process_single_empty_dialog_skipped(self):
        op = DialogMemoryConsistencyMapper(api_model="any-model")
        sample = {"dialog_history": []}
        result = op.process_single(sample)
        meta = result[Fields.meta]
        self.assertIn(MetaKeys.dialog_memory_consistency, meta)
        self.assertTrue(meta[MetaKeys.dialog_memory_consistency]["skipped"])
        self.assertEqual(
            meta[MetaKeys.dialog_memory_consistency]["reason"], "empty_input"
        )

    def test_process_single_existing_meta_no_overwrite(self):
        op = DialogMemoryConsistencyMapper(
            api_model="any-model", overwrite=False
        )
        existing = {"score": 5.0, "reason": "pre-existing"}
        sample = {
            "dialog_history": [("hi", "hello")],
            Fields.meta: {MetaKeys.dialog_memory_consistency: existing},
        }
        result = op.process_single(sample)
        self.assertEqual(
            result[Fields.meta][MetaKeys.dialog_memory_consistency], existing
        )


class DialogProactivityUnitTest(DataJuicerTestCaseBase):
    """Unit tests for DialogProactivityMapper (no API calls)."""


    def test_process_single_empty_dialog_skipped(self):
        op = DialogProactivityMapper(api_model="any-model")
        sample = {"dialog_history": []}
        result = op.process_single(sample)
        meta = result[Fields.meta]
        self.assertIn(MetaKeys.dialog_proactivity, meta)
        self.assertTrue(meta[MetaKeys.dialog_proactivity]["skipped"])
        self.assertEqual(
            meta[MetaKeys.dialog_proactivity]["reason"], "empty_input"
        )

    def test_process_single_existing_meta_no_overwrite(self):
        op = DialogProactivityMapper(api_model="any-model", overwrite=False)
        existing = {"score": 2.0, "reason": "pre-existing"}
        sample = {
            "dialog_history": [("hi", "hello")],
            Fields.meta: {MetaKeys.dialog_proactivity: existing},
        }
        result = op.process_single(sample)
        self.assertEqual(
            result[Fields.meta][MetaKeys.dialog_proactivity], existing
        )


class DialogErrorRecoveryUnitTest(DataJuicerTestCaseBase):
    """Unit tests for DialogErrorRecoveryMapper (no API calls)."""


    def test_process_single_empty_dialog_skipped(self):
        op = DialogErrorRecoveryMapper(api_model="any-model")
        sample = {"dialog_history": []}
        result = op.process_single(sample)
        meta = result[Fields.meta]
        self.assertIn(MetaKeys.dialog_error_recovery, meta)
        self.assertTrue(meta[MetaKeys.dialog_error_recovery]["skipped"])
        self.assertEqual(
            meta[MetaKeys.dialog_error_recovery]["reason"], "empty_input"
        )

    def test_process_single_existing_meta_no_overwrite(self):
        op = DialogErrorRecoveryMapper(api_model="any-model", overwrite=False)
        existing = {"score": 4.0, "reason": "pre-existing"}
        sample = {
            "dialog_history": [("hi", "hello")],
            Fields.meta: {MetaKeys.dialog_error_recovery: existing},
        }
        result = op.process_single(sample)
        self.assertEqual(
            result[Fields.meta][MetaKeys.dialog_error_recovery], existing
        )


class DialogTopicShiftUnitTest(DataJuicerTestCaseBase):
    """Unit tests for DialogTopicShiftMapper (no API calls)."""


    def test_process_single_empty_dialog_skipped(self):
        op = DialogTopicShiftMapper(api_model="any-model")
        sample = {"dialog_history": []}
        result = op.process_single(sample)
        meta = result[Fields.meta]
        self.assertIn(MetaKeys.dialog_topic_shift, meta)
        self.assertTrue(meta[MetaKeys.dialog_topic_shift]["skipped"])
        self.assertEqual(
            meta[MetaKeys.dialog_topic_shift]["reason"], "empty_input"
        )

    def test_process_single_existing_meta_no_overwrite(self):
        op = DialogTopicShiftMapper(api_model="any-model", overwrite=False)
        existing = {"score": 3.0, "reason": "pre-existing"}
        sample = {
            "dialog_history": [("hi", "hello")],
            Fields.meta: {MetaKeys.dialog_topic_shift: existing},
        }
        result = op.process_single(sample)
        self.assertEqual(
            result[Fields.meta][MetaKeys.dialog_topic_shift], existing
        )


class DialogCoreferenceUnitTest(DataJuicerTestCaseBase):
    """Unit tests for DialogCoreferenceMapper (no API calls)."""


    def test_process_single_empty_dialog_skipped(self):
        op = DialogCoreferenceMapper(api_model="any-model")
        sample = {"dialog_history": []}
        result = op.process_single(sample)
        meta = result[Fields.meta]
        self.assertIn(MetaKeys.dialog_coreference, meta)
        self.assertTrue(meta[MetaKeys.dialog_coreference]["skipped"])
        self.assertEqual(
            meta[MetaKeys.dialog_coreference]["reason"], "empty_input"
        )

    def test_process_single_existing_meta_no_overwrite(self):
        op = DialogCoreferenceMapper(api_model="any-model", overwrite=False)
        existing = {"score": 5.0, "reason": "pre-existing"}
        sample = {
            "dialog_history": [("hi", "hello")],
            Fields.meta: {MetaKeys.dialog_coreference: existing},
        }
        result = op.process_single(sample)
        self.assertEqual(
            result[Fields.meta][MetaKeys.dialog_coreference], existing
        )


class AgentTraceCoherenceUnitTest(DataJuicerTestCaseBase):
    """Unit tests for AgentTraceCoherenceMapper (no API calls)."""


    def test_process_single_empty_text_skipped(self):
        op = AgentTraceCoherenceMapper(api_model="any-model")
        sample = {"text": ""}
        result = op.process_single(sample)
        meta = result[Fields.meta]
        self.assertIn(MetaKeys.agent_trace_coherence, meta)
        self.assertTrue(meta[MetaKeys.agent_trace_coherence]["skipped"])
        self.assertEqual(
            meta[MetaKeys.agent_trace_coherence]["reason"], "empty_input"
        )

    def test_process_single_missing_text_skipped(self):
        op = AgentTraceCoherenceMapper(api_model="any-model")
        sample = {}
        result = op.process_single(sample)
        meta = result[Fields.meta]
        self.assertIn(MetaKeys.agent_trace_coherence, meta)
        self.assertTrue(meta[MetaKeys.agent_trace_coherence]["skipped"])

    def test_process_single_existing_meta_no_overwrite(self):
        op = AgentTraceCoherenceMapper(api_model="any-model", overwrite=False)
        existing = {"score": 4.0, "reason": "pre-existing"}
        sample = {
            "text": "some session trace",
            Fields.meta: {MetaKeys.agent_trace_coherence: existing},
        }
        result = op.process_single(sample)
        self.assertEqual(
            result[Fields.meta][MetaKeys.agent_trace_coherence], existing
        )


class AgentToolRelevanceUnitTest(DataJuicerTestCaseBase):
    """Unit tests for AgentToolRelevanceMapper (no API calls)."""


    def test_process_single_empty_query_and_response_skipped(self):
        op = AgentToolRelevanceMapper(api_model="any-model")
        # build_agent_tool_fit_user_content always returns content because
        # it includes "(none)" placeholders; however query+response both empty
        # still produces a non-empty user block. The mapper won't skip here
        # because the utility always returns non-empty text. We test that no
        # crash occurs and meta key is set (will be error since no real API).
        sample = {"query": "", "response": ""}
        result = op.process_single(sample)
        meta = result[Fields.meta]
        # Should have the meta key set (either error or skipped)
        self.assertIn(MetaKeys.agent_tool_relevance, meta)

    def test_process_single_existing_meta_no_overwrite(self):
        op = AgentToolRelevanceMapper(api_model="any-model", overwrite=False)
        existing = {"score": 5.0, "reason": "pre-existing"}
        sample = {
            "query": "search for files",
            "response": "I used grep to find them.",
            Fields.meta: {MetaKeys.agent_tool_relevance: existing},
        }
        result = op.process_single(sample)
        self.assertEqual(
            result[Fields.meta][MetaKeys.agent_tool_relevance], existing
        )


class TestDialogNonRepetitionMapper(DataJuicerTestCaseBase):

    def test_default(self):
        samples = [{
            'dialog_history': [
                ('user question 1', 'assistant answer 1'),
                ('user question 2', 'assistant answer 2'),
            ]
        }]
        op = DialogNonRepetitionMapper(
            api_model=DEFAULT_API_MODEL,
            sampling_params={'enable_thinking': False},
        )
        dataset = Dataset.from_list(samples)
        dataset = op.run(dataset)
        result = dataset[0][Fields.meta][MetaKeys.dialog_non_repetition]
        self.assertIn('score', result)
        self.assertIsInstance(result['score'], float)
        self.assertGreaterEqual(result['score'], 1.0)
        self.assertLessEqual(result['score'], 5.0)


@skip_if_from_fork("Skipping API-based test because running from a fork repo")
class TestDialogClarificationQualityMapper(DataJuicerTestCaseBase):

    def test_default(self):
        samples = [{
            'dialog_history': [
                ('I want to build something', 'What kind of project?'),
                ('A web app', 'What framework do you prefer?'),
            ]
        }]
        op = DialogClarificationQualityMapper(
            api_model=DEFAULT_API_MODEL,
            sampling_params={'enable_thinking': False},
        )
        dataset = Dataset.from_list(samples)
        dataset = op.run(dataset)
        result = dataset[0][Fields.meta][MetaKeys.dialog_clarification_quality]
        self.assertIn('score', result)
        self.assertIsInstance(result['score'], float)
        self.assertGreaterEqual(result['score'], 1.0)
        self.assertLessEqual(result['score'], 5.0)


@skip_if_from_fork("Skipping API-based test because running from a fork repo")
class TestDialogMemoryConsistencyMapper(DataJuicerTestCaseBase):

    def test_default(self):
        samples = [{
            'dialog_history': [
                ('My budget is under 500 dollars', 'Got it, under 500.'),
                ('What do you recommend?', 'I recommend this 450 dollar option.'),
            ]
        }]
        op = DialogMemoryConsistencyMapper(
            api_model=DEFAULT_API_MODEL,
            sampling_params={'enable_thinking': False},
        )
        dataset = Dataset.from_list(samples)
        dataset = op.run(dataset)
        result = dataset[0][Fields.meta][MetaKeys.dialog_memory_consistency]
        self.assertIn('score', result)
        self.assertIsInstance(result['score'], float)
        self.assertGreaterEqual(result['score'], 1.0)
        self.assertLessEqual(result['score'], 5.0)


@skip_if_from_fork("Skipping API-based test because running from a fork repo")
class TestDialogProactivityMapper(DataJuicerTestCaseBase):

    def test_default(self):
        samples = [{
            'dialog_history': [
                ('How do I set up CI?', 'Here are the steps. Also you might want to add linting.'),
                ('Good idea, what linter?', 'I suggest ESLint. Want me to show config?'),
            ]
        }]
        op = DialogProactivityMapper(
            api_model=DEFAULT_API_MODEL,
            sampling_params={'enable_thinking': False},
        )
        dataset = Dataset.from_list(samples)
        dataset = op.run(dataset)
        result = dataset[0][Fields.meta][MetaKeys.dialog_proactivity]
        self.assertIn('score', result)
        self.assertIsInstance(result['score'], float)
        self.assertGreaterEqual(result['score'], 1.0)
        self.assertLessEqual(result['score'], 5.0)


@skip_if_from_fork("Skipping API-based test because running from a fork repo")
class TestDialogErrorRecoveryMapper(DataJuicerTestCaseBase):

    def test_default(self):
        samples = [{
            'dialog_history': [
                ('What is 2+2?', 'It is 5.'),
                ('No, that is wrong. 2+2 is 4.', 'You are right, I apologize. 2+2 is 4.'),
            ]
        }]
        op = DialogErrorRecoveryMapper(
            api_model=DEFAULT_API_MODEL,
            sampling_params={'enable_thinking': False},
        )
        dataset = Dataset.from_list(samples)
        dataset = op.run(dataset)
        result = dataset[0][Fields.meta][MetaKeys.dialog_error_recovery]
        self.assertIn('score', result)
        self.assertIsInstance(result['score'], float)
        self.assertGreaterEqual(result['score'], 1.0)
        self.assertLessEqual(result['score'], 5.0)


@skip_if_from_fork("Skipping API-based test because running from a fork repo")
class TestDialogTopicShiftMapper(DataJuicerTestCaseBase):

    def test_default(self):
        samples = [{
            'dialog_history': [
                ('Tell me about Python', 'Python is a programming language.'),
                ('Actually, what about the weather today?', 'The weather looks sunny today!'),
            ]
        }]
        op = DialogTopicShiftMapper(
            api_model=DEFAULT_API_MODEL,
            sampling_params={'enable_thinking': False},
        )
        dataset = Dataset.from_list(samples)
        dataset = op.run(dataset)
        result = dataset[0][Fields.meta][MetaKeys.dialog_topic_shift]
        self.assertIn('score', result)
        self.assertIsInstance(result['score'], float)
        self.assertGreaterEqual(result['score'], 1.0)
        self.assertLessEqual(result['score'], 5.0)


@skip_if_from_fork("Skipping API-based test because running from a fork repo")
class TestDialogCoreferenceMapper(DataJuicerTestCaseBase):

    def test_default(self):
        samples = [{
            'dialog_history': [
                ('I bought a new laptop yesterday', 'Nice! What brand?'),
                ('It is a ThinkPad. Can you tell me how to set it up?', 'Sure, to set up your ThinkPad, first...'),
            ]
        }]
        op = DialogCoreferenceMapper(
            api_model=DEFAULT_API_MODEL,
            sampling_params={'enable_thinking': False},
        )
        dataset = Dataset.from_list(samples)
        dataset = op.run(dataset)
        result = dataset[0][Fields.meta][MetaKeys.dialog_coreference]
        self.assertIn('score', result)
        self.assertIsInstance(result['score'], float)
        self.assertGreaterEqual(result['score'], 1.0)
        self.assertLessEqual(result['score'], 5.0)


@skip_if_from_fork("Skipping API-based test because running from a fork repo")
class TestAgentTraceCoherenceMapper(DataJuicerTestCaseBase):

    def test_default(self):
        samples = [{
            'text': (
                'User: Find the top 3 Python repos on GitHub.\n'
                'Assistant: I will search GitHub for popular Python repositories.\n'
                '[Tool Call] github_search(query="Python", sort="stars", limit=3)\n'
                '[Tool Result] 1. tensorflow 2. django 3. flask\n'
                'Assistant: The top 3 Python repos by stars are: '
                'TensorFlow, Django, and Flask.'
            )
        }]
        op = AgentTraceCoherenceMapper(
            api_model=DEFAULT_API_MODEL,
            sampling_params={'enable_thinking': False},
        )
        dataset = Dataset.from_list(samples)
        dataset = op.run(dataset)
        result = dataset[0][Fields.meta][MetaKeys.agent_trace_coherence]
        self.assertIn('score', result)
        self.assertIsInstance(result['score'], float)
        self.assertGreaterEqual(result['score'], 1.0)
        self.assertLessEqual(result['score'], 5.0)


@skip_if_from_fork("Skipping API-based test because running from a fork repo")
class TestAgentToolRelevanceMapper(DataJuicerTestCaseBase):

    def test_default(self):
        samples = [{
            'query': 'Search for files containing TODO in the project',
            'response': (
                'I used grep to search the codebase and found 5 files '
                'with TODO comments. Here they are: ...'
            ),
        }]
        op = AgentToolRelevanceMapper(
            api_model=DEFAULT_API_MODEL,
            sampling_params={'enable_thinking': False},
        )
        dataset = Dataset.from_list(samples)
        dataset = op.run(dataset)
        result = dataset[0][Fields.meta][MetaKeys.agent_tool_relevance]
        self.assertIn('score', result)
        self.assertIsInstance(result['score'], float)
        self.assertGreaterEqual(result['score'], 1.0)
        self.assertLessEqual(result['score'], 5.0)


if __name__ == '__main__':
    unittest.main()
