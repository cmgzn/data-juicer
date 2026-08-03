# Copyright 2025 The Data-Juicer Authors. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for dialog_quality_llm_utils and dialog_llm_input_utils helpers."""

import unittest

from data_juicer.ops.mapper.dialog_llm_input_utils import (
    build_dialog_turns_for_prompt,
    clip_query_response_pair,
    clip_text_for_dialog_prompt,
)
from data_juicer.ops.mapper.dialog_quality_llm_utils import (
    build_agent_tool_fit_user_content,
    build_agent_trace_eval_user_content,
    build_dialog_turn_eval_user_content,
    extract_json_object,
    normalize_score_1_5,
)
from data_juicer.utils.constant import Fields
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class ExtractJsonObjectTest(DataJuicerTestCaseBase):
    """Tests for extract_json_object."""

    def test_valid_json_plain(self):
        text = '{"score": 3, "reason": "good"}'
        result = extract_json_object(text)
        self.assertEqual(result, {"score": 3, "reason": "good"})

    def test_valid_json_with_surrounding_text(self):
        text = 'Here is my evaluation: {"score": 4, "reason": "nice"} end.'
        result = extract_json_object(text)
        self.assertEqual(result, {"score": 4, "reason": "nice"})

    def test_valid_json_in_code_block(self):
        text = '```json\n{"score": 5, "reason": "excellent"}\n```'
        result = extract_json_object(text)
        self.assertEqual(result, {"score": 5, "reason": "excellent"})

    def test_valid_json_in_code_block_no_lang(self):
        text = '```\n{"score": 2, "reason": "poor"}\n```'
        result = extract_json_object(text)
        self.assertEqual(result, {"score": 2, "reason": "poor"})

    def test_valid_json_in_code_block_uppercase(self):
        text = '```JSON\n{"score": 1, "reason": "bad"}\n```'
        result = extract_json_object(text)
        self.assertEqual(result, {"score": 1, "reason": "bad"})

    def test_invalid_json(self):
        text = '{"score": 3, "reason": }'
        result = extract_json_object(text)
        self.assertIsNone(result)

    def test_no_json_at_all(self):
        text = "This is just plain text with no JSON."
        result = extract_json_object(text)
        self.assertIsNone(result)

    def test_empty_string(self):
        result = extract_json_object("")
        self.assertIsNone(result)

    def test_none_input(self):
        result = extract_json_object(None)
        self.assertIsNone(result)

    def test_non_string_input(self):
        result = extract_json_object(123)
        self.assertIsNone(result)

    def test_only_opening_brace(self):
        result = extract_json_object("{")
        self.assertIsNone(result)

    def test_nested_json(self):
        text = '{"score": 4, "details": {"sub": 1}}'
        result = extract_json_object(text)
        self.assertEqual(result, {"score": 4, "details": {"sub": 1}})

    def test_json_with_whitespace(self):
        text = '   \n  {"score": 3, "reason": "ok"}  \n  '
        result = extract_json_object(text)
        self.assertEqual(result, {"score": 3, "reason": "ok"})


class BuildDialogTurnsForPromptTest(DataJuicerTestCaseBase):
    """Tests for build_dialog_turns_for_prompt."""

    def test_history_only(self):
        sample = {
            "history": [["Hi", "Hello"], ["How are you?", "Fine"]],
            "query": "",
            "response": "",
        }
        turns = build_dialog_turns_for_prompt(
            sample, history_key="history", query_key="query", response_key="response"
        )
        self.assertEqual(turns, [("Hi", "Hello"), ("How are you?", "Fine")])

    def test_query_response_only_no_history(self):
        sample = {
            "history": [],
            "query": "What is AI?",
            "response": "Artificial intelligence.",
        }
        turns = build_dialog_turns_for_prompt(
            sample, history_key="history", query_key="query", response_key="response"
        )
        self.assertEqual(turns, [("What is AI?", "Artificial intelligence.")])

    def test_query_response_appended_to_history(self):
        sample = {
            "history": [["Hi", "Hello"]],
            "query": "What is AI?",
            "response": "Artificial intelligence.",
        }
        turns = build_dialog_turns_for_prompt(
            sample, history_key="history", query_key="query", response_key="response"
        )
        self.assertEqual(
            turns, [("Hi", "Hello"), ("What is AI?", "Artificial intelligence.")]
        )

    def test_deduplication_last_history_equals_query_response(self):
        """When last history turn matches query/response, should not duplicate."""
        sample = {
            "history": [["Hi", "Hello"], ["What is AI?", "Artificial intelligence."]],
            "query": "What is AI?",
            "response": "Artificial intelligence.",
        }
        turns = build_dialog_turns_for_prompt(
            sample, history_key="history", query_key="query", response_key="response"
        )
        self.assertEqual(
            turns, [("Hi", "Hello"), ("What is AI?", "Artificial intelligence.")]
        )

    def test_deduplication_same_query_different_response(self):
        """When last history has same query but different response, update it."""
        sample = {
            "history": [["What is AI?", "Old answer"]],
            "query": "What is AI?",
            "response": "New answer",
        }
        turns = build_dialog_turns_for_prompt(
            sample, history_key="history", query_key="query", response_key="response"
        )
        self.assertEqual(turns, [("What is AI?", "New answer")])

    def test_no_history_key(self):
        sample = {
            "query": "Hello",
            "response": "Hi",
        }
        turns = build_dialog_turns_for_prompt(
            sample, history_key="history", query_key="query", response_key="response"
        )
        self.assertEqual(turns, [("Hello", "Hi")])

    def test_history_with_none_values(self):
        sample = {
            "history": [[None, "response1"], ["query2", None]],
            "query": "",
            "response": "",
        }
        turns = build_dialog_turns_for_prompt(
            sample, history_key="history", query_key="query", response_key="response"
        )
        self.assertEqual(turns, [("", "response1"), ("query2", "")])

    def test_empty_sample(self):
        sample = {"history": [], "query": "", "response": ""}
        turns = build_dialog_turns_for_prompt(
            sample, history_key="history", query_key="query", response_key="response"
        )
        self.assertEqual(turns, [])


class ClipTextForDialogPromptTest(DataJuicerTestCaseBase):
    """Tests for clip_text_for_dialog_prompt."""

    def test_no_clipping_needed(self):
        text = "Short text"
        result = clip_text_for_dialog_prompt(text, 100)
        self.assertEqual(result, "Short text")

    def test_clipping_applied(self):
        text = "A" * 200
        result = clip_text_for_dialog_prompt(text, 50, "truncated")
        self.assertIn("truncated", result)
        self.assertTrue(len(result) <= 50)

    def test_max_chars_zero_no_clip(self):
        text = "Some long text" * 100
        result = clip_text_for_dialog_prompt(text, 0)
        self.assertEqual(result, text)

    def test_max_chars_negative_no_clip(self):
        text = "Some long text" * 100
        result = clip_text_for_dialog_prompt(text, -1)
        self.assertEqual(result, text)

    def test_max_chars_none_no_clip(self):
        text = "Some long text" * 100
        result = clip_text_for_dialog_prompt(text, None)
        self.assertEqual(result, text)

    def test_empty_text(self):
        result = clip_text_for_dialog_prompt("", 10)
        self.assertEqual(result, "")

    def test_exact_length_no_clip(self):
        text = "ABCDE"
        result = clip_text_for_dialog_prompt(text, 5)
        self.assertEqual(result, "ABCDE")

    def test_very_small_max_chars(self):
        """When max_chars is too small for any text + suffix, returns suffix only."""
        text = "A" * 100
        result = clip_text_for_dialog_prompt(text, 3, "truncated")
        # Should return something, not crash
        self.assertIsNotNone(result)


class ClipQueryResponsePairTest(DataJuicerTestCaseBase):
    """Tests for clip_query_response_pair."""

    def test_both_within_limits(self):
        q, r = clip_query_response_pair("hello", "world", 100, 100)
        self.assertEqual(q, "hello")
        self.assertEqual(r, "world")

    def test_query_clipped(self):
        q, r = clip_query_response_pair("A" * 200, "short", 50, 100)
        self.assertTrue(len(q) <= 50)
        self.assertEqual(r, "short")

    def test_response_clipped(self):
        q, r = clip_query_response_pair("short", "B" * 200, 100, 50)
        self.assertEqual(q, "short")
        self.assertTrue(len(r) <= 50)

    def test_none_inputs(self):
        q, r = clip_query_response_pair(None, None, 100, 100)
        self.assertEqual(q, "")
        self.assertEqual(r, "")


class NormalizeScore15Test(DataJuicerTestCaseBase):
    """Tests for normalize_score_1_5."""

    def test_valid_integer_score(self):
        result = normalize_score_1_5({"score": 3, "reason": "average quality"})
        self.assertEqual(result["score"], 3.0)
        self.assertEqual(result["reason"], "average quality")
        self.assertNotIn("error", result)

    def test_valid_float_score(self):
        result = normalize_score_1_5({"score": 4.5, "reason": "good"})
        self.assertEqual(result["score"], 4.5)

    def test_score_string_numeric(self):
        result = normalize_score_1_5({"score": "3", "reason": "ok"})
        self.assertEqual(result["score"], 3.0)

    def test_score_above_5_clamped(self):
        result = normalize_score_1_5({"score": 10, "reason": "too high"})
        self.assertEqual(result["score"], 5.0)

    def test_score_below_1_clamped(self):
        result = normalize_score_1_5({"score": -2, "reason": "too low"})
        self.assertEqual(result["score"], 1.0)

    def test_score_exactly_1(self):
        result = normalize_score_1_5({"score": 1, "reason": "lowest"})
        self.assertEqual(result["score"], 1.0)

    def test_score_exactly_5(self):
        result = normalize_score_1_5({"score": 5, "reason": "highest"})
        self.assertEqual(result["score"], 5.0)

    def test_non_numeric_score(self):
        result = normalize_score_1_5({"score": "abc", "reason": "bad"})
        self.assertIsNone(result["score"])
        self.assertEqual(result["error"], "bad_score")
        self.assertEqual(result["reason"], "bad")

    def test_missing_score_key(self):
        result = normalize_score_1_5({"reason": "no score"})
        self.assertIsNone(result["score"])
        self.assertEqual(result["error"], "bad_score")

    def test_none_input(self):
        result = normalize_score_1_5(None)
        self.assertIsNone(result["score"])
        self.assertEqual(result["error"], "invalid_json")

    def test_non_dict_input(self):
        result = normalize_score_1_5("not a dict")
        self.assertIsNone(result["score"])
        self.assertEqual(result["error"], "invalid_json")

    def test_missing_reason_key(self):
        result = normalize_score_1_5({"score": 4})
        self.assertEqual(result["score"], 4.0)
        self.assertEqual(result["reason"], "")

    def test_reason_truncated_to_2000(self):
        long_reason = "x" * 5000
        result = normalize_score_1_5({"score": 3, "reason": long_reason})
        self.assertEqual(len(result["reason"]), 2000)


class BuildDialogTurnEvalUserContentTest(DataJuicerTestCaseBase):
    """Tests for build_dialog_turn_eval_user_content."""

    def test_section_headers_present(self):
        sample = {
            "history": [["Hi", "Hello"], ["How?", "Fine"]],
            "query": "Tell me more",
            "response": "Sure, here you go.",
        }
        content = build_dialog_turn_eval_user_content(
            sample,
            history_key="history",
            query_key="query",
            response_key="response",
            max_round=10,
            max_query_chars=500,
            max_response_chars=500,
        )
        self.assertIn("### Earlier turns", content)
        self.assertIn("### Current user message", content)
        self.assertIn("### Assistant reply to score", content)

    def test_single_turn_no_earlier(self):
        sample = {
            "history": [],
            "query": "Question",
            "response": "Answer",
        }
        content = build_dialog_turn_eval_user_content(
            sample,
            history_key="history",
            query_key="query",
            response_key="response",
            max_round=10,
            max_query_chars=500,
            max_response_chars=500,
        )
        self.assertIn("### Current user message", content)
        self.assertIn("Question", content)
        self.assertIn("Answer", content)

    def test_empty_dialog_returns_empty(self):
        sample = {"history": [], "query": "", "response": ""}
        content = build_dialog_turn_eval_user_content(
            sample,
            history_key="history",
            query_key="query",
            response_key="response",
            max_round=10,
            max_query_chars=500,
            max_response_chars=500,
        )
        self.assertEqual(content, "")

    def test_max_round_trims_dialog(self):
        sample = {
            "history": [
                ["T1Q", "T1A"],
                ["T2Q", "T2A"],
                ["T3Q", "T3A"],
                ["T4Q", "T4A"],
            ],
            "query": "T5Q",
            "response": "T5A",
        }
        content = build_dialog_turn_eval_user_content(
            sample,
            history_key="history",
            query_key="query",
            response_key="response",
            max_round=2,
            max_query_chars=500,
            max_response_chars=500,
        )
        # Only last 2 turns should be included: T4 and T5
        # T1, T2, T3 should not appear
        self.assertNotIn("T1Q", content)
        self.assertNotIn("T2Q", content)
        self.assertNotIn("T3Q", content)
        # The last turn (T5) should appear as "current"
        self.assertIn("T5Q", content)
        self.assertIn("T5A", content)

    def test_clipping_applied_to_content(self):
        sample = {
            "history": [],
            "query": "Q" * 1000,
            "response": "R" * 1000,
        }
        content = build_dialog_turn_eval_user_content(
            sample,
            history_key="history",
            query_key="query",
            response_key="response",
            max_round=10,
            max_query_chars=50,
            max_response_chars=50,
        )
        # The full 1000-char strings should not be present
        self.assertNotIn("Q" * 1000, content)
        self.assertNotIn("R" * 1000, content)


class BuildAgentTraceEvalUserContentTest(DataJuicerTestCaseBase):
    """Tests for build_agent_trace_eval_user_content."""

    def test_normal_trace(self):
        sample = {"text": "User: Hi\nAssistant: Hello\nTool: result"}
        content = build_agent_trace_eval_user_content(
            sample, text_key="text", max_chars=500
        )
        self.assertIn("### Session trace excerpt", content)
        self.assertIn("User: Hi", content)

    def test_empty_text_returns_empty(self):
        sample = {"text": ""}
        content = build_agent_trace_eval_user_content(
            sample, text_key="text", max_chars=500
        )
        self.assertEqual(content, "")

    def test_missing_text_key_returns_empty(self):
        sample = {"other": "value"}
        content = build_agent_trace_eval_user_content(
            sample, text_key="text", max_chars=500
        )
        self.assertEqual(content, "")

    def test_non_string_text_returns_empty(self):
        sample = {"text": 123}
        content = build_agent_trace_eval_user_content(
            sample, text_key="text", max_chars=500
        )
        self.assertEqual(content, "")

    def test_whitespace_only_returns_empty(self):
        sample = {"text": "   \n  \t  "}
        content = build_agent_trace_eval_user_content(
            sample, text_key="text", max_chars=500
        )
        self.assertEqual(content, "")

    def test_clipping_long_trace(self):
        sample = {"text": "X" * 2000}
        content = build_agent_trace_eval_user_content(
            sample, text_key="text", max_chars=100
        )
        self.assertIn("text truncated", content)
        self.assertNotIn("X" * 2000, content)


class BuildAgentToolFitUserContentTest(DataJuicerTestCaseBase):
    """Tests for build_agent_tool_fit_user_content."""

    def test_full_sample(self):
        sample = {
            "query": "Find restaurants nearby",
            "response": "I'll search for restaurants...",
            Fields.meta: {
                "tool_types": ["search", "maps"],
                "primary_tool": "search",
            },
        }
        content = build_agent_tool_fit_user_content(
            sample,
            query_key="query",
            response_key="response",
            tool_types_key="tool_types",
            primary_tool_key="primary_tool",
            max_query_chars=500,
            max_response_chars=500,
        )
        self.assertIn("### User request", content)
        self.assertIn("### Assistant reply", content)
        self.assertIn("### Inferred tool list", content)
        self.assertIn("### Primary tool", content)
        self.assertIn("search, maps", content)
        self.assertIn("search", content)

    def test_no_meta(self):
        sample = {
            "query": "Hello",
            "response": "Hi",
        }
        content = build_agent_tool_fit_user_content(
            sample,
            query_key="query",
            response_key="response",
            tool_types_key="tool_types",
            primary_tool_key="primary_tool",
            max_query_chars=500,
            max_response_chars=500,
        )
        self.assertIn("(none)", content)

    def test_meta_not_dict(self):
        sample = {
            "query": "Hello",
            "response": "Hi",
            Fields.meta: "not a dict",
        }
        content = build_agent_tool_fit_user_content(
            sample,
            query_key="query",
            response_key="response",
            tool_types_key="tool_types",
            primary_tool_key="primary_tool",
            max_query_chars=500,
            max_response_chars=500,
        )
        self.assertIn("(none)", content)

    def test_tools_as_string(self):
        sample = {
            "query": "Q",
            "response": "R",
            Fields.meta: {
                "tool_types": "single_tool",
                "primary_tool": None,
            },
        }
        content = build_agent_tool_fit_user_content(
            sample,
            query_key="query",
            response_key="response",
            tool_types_key="tool_types",
            primary_tool_key="primary_tool",
            max_query_chars=500,
            max_response_chars=500,
        )
        self.assertIn("single_tool", content)


if __name__ == "__main__":
    unittest.main()
