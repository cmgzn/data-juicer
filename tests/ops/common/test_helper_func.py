import unittest

from data_juicer.ops.common.helper_func import (
    UnionFind,
    get_sentences_from_document,
    get_words_from_document,
    merge_on_whitespace_tab_newline,
    split_on_newline_tab_whitespace,
    split_on_whitespace,
    split_text_by_punctuation,
    strip,
    words_augmentation,
    words_refinement,
)
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class UnionFindTest(DataJuicerTestCaseBase):

    def test_find_creates_new_element(self):
        uf = UnionFind()
        self.assertEqual(uf.find(1), 1)
        self.assertEqual(uf.find(42), 42)

    def test_union_two_elements(self):
        uf = UnionFind()
        uf.union(1, 2)
        self.assertEqual(uf.find(1), uf.find(2))
        self.assertEqual(uf.find(1), 1)

    def test_union_picks_min_as_root(self):
        uf = UnionFind()
        uf.union(5, 3)
        self.assertEqual(uf.find(5), 3)
        self.assertEqual(uf.find(3), 3)

    def test_union_chain(self):
        uf = UnionFind()
        uf.union(1, 2)
        uf.union(2, 3)
        uf.union(3, 4)
        self.assertEqual(uf.find(4), 1)
        self.assertEqual(uf.find(3), 1)
        self.assertEqual(uf.find(2), 1)

    def test_union_separate_groups(self):
        uf = UnionFind()
        uf.union(1, 2)
        uf.union(3, 4)
        self.assertNotEqual(uf.find(1), uf.find(3))
        uf.union(2, 4)
        self.assertEqual(uf.find(1), uf.find(3))

    def test_path_compression(self):
        uf = UnionFind()
        uf.union(3, 2)
        uf.union(4, 3)
        uf.union(5, 4)
        uf.find(5)
        self.assertEqual(uf.parent[5], 2)

    def test_union_same_element(self):
        uf = UnionFind()
        uf.union(1, 1)
        self.assertEqual(uf.find(1), 1)

    def test_negative_elements(self):
        uf = UnionFind()
        uf.union(-5, -3)
        self.assertEqual(uf.find(-5), -5)
        self.assertEqual(uf.find(-3), -5)


class StripTest(DataJuicerTestCaseBase):

    def test_strip_basic(self):
        result = strip("  hello  ", {" "})
        self.assertEqual(result, "hello")

    def test_strip_multiple_chars(self):
        result = strip("##hello##", {"#"})
        self.assertEqual(result, "hello")

    def test_strip_mixed_chars(self):
        result = strip("!@hello@!", {"!", "@"})
        self.assertEqual(result, "hello")

    def test_strip_no_matching_chars(self):
        result = strip("hello", {"#", "@"})
        self.assertEqual(result, "hello")

    def test_strip_all_stripped(self):
        result = strip("###", {"#"})
        self.assertEqual(result, "")

    def test_strip_empty_string(self):
        result = strip("", {"#"})
        self.assertEqual(result, "")

    def test_strip_none(self):
        result = strip(None, {"#"})
        self.assertIsNone(result)

    def test_strip_unicode_chars(self):
        result = strip("\U0001f600hello\U0001f600", {"\U0001f600"})
        self.assertEqual(result, "hello")

    def test_strip_only_leading(self):
        result = strip("##hello", {"#"})
        self.assertEqual(result, "hello")

    def test_strip_only_trailing(self):
        result = strip("hello##", {"#"})
        self.assertEqual(result, "hello")

    def test_strip_preserves_interior(self):
        result = strip("#he#llo#", {"#"})
        self.assertEqual(result, "he#llo")


class SplitOnWhitespaceTest(DataJuicerTestCaseBase):

    def test_basic_split(self):
        result = split_on_whitespace("hello world")
        self.assertEqual(result, ["hello", "world"])

    def test_multiple_spaces(self):
        result = split_on_whitespace("hello   world")
        self.assertEqual(result, ["hello", "world"])

    def test_no_newline_by_default(self):
        result = split_on_whitespace("hello\nworld")
        self.assertEqual(result, ["hello\nworld"])

    def test_with_newline(self):
        result = split_on_whitespace("hello\nworld", new_line=True)
        self.assertEqual(result, ["hello", "world"])

    def test_with_tab(self):
        result = split_on_whitespace("hello\tworld", tab=True)
        self.assertEqual(result, ["hello", "world"])

    def test_with_newline_and_tab(self):
        result = split_on_whitespace("hello\n\tworld", new_line=True, tab=True)
        self.assertEqual(result, ["hello", "world"])

    def test_empty_string(self):
        result = split_on_whitespace("")
        self.assertEqual(result, [])

    def test_only_spaces(self):
        result = split_on_whitespace("   ")
        self.assertEqual(result, [])

    def test_cjk_text_no_spaces(self):
        result = split_on_whitespace("你好世界")
        self.assertEqual(result, ["你好世界"])

    def test_leading_trailing_spaces(self):
        result = split_on_whitespace("  hello  world  ")
        self.assertEqual(result, ["hello", "world"])


class SplitOnNewlineTabWhitespaceTest(DataJuicerTestCaseBase):

    def test_basic(self):
        result = split_on_newline_tab_whitespace("hello world")
        self.assertEqual(result, [[["hello", "world"]]])

    def test_newline_split(self):
        result = split_on_newline_tab_whitespace("hello\nworld")
        self.assertEqual(result, [[["hello"]], [["world"]]])

    def test_tab_split(self):
        result = split_on_newline_tab_whitespace("hello\tworld")
        self.assertEqual(result, [[["hello"], ["world"]]])

    def test_all_levels(self):
        result = split_on_newline_tab_whitespace("a b\tc d\ne f")
        self.assertEqual(result, [[["a", "b"], ["c", "d"]], [["e", "f"]]])

    def test_empty_string(self):
        result = split_on_newline_tab_whitespace("")
        self.assertEqual(result, [[[]]])

    def test_multiple_newlines(self):
        result = split_on_newline_tab_whitespace("a\n\nb")
        self.assertEqual(result, [[["a"]], [[]], [["b"]]])


class MergeOnWhitespaceTabNewlineTest(DataJuicerTestCaseBase):

    def test_basic(self):
        sentences = [[["hello", "world"]]]
        result = merge_on_whitespace_tab_newline(sentences)
        self.assertEqual(result, "hello world")

    def test_with_tabs(self):
        sentences = [[["hello"], ["world"]]]
        result = merge_on_whitespace_tab_newline(sentences)
        self.assertEqual(result, "hello\tworld")

    def test_with_newlines(self):
        sentences = [[["hello"]], [["world"]]]
        result = merge_on_whitespace_tab_newline(sentences)
        self.assertEqual(result, "hello\nworld")

    def test_all_levels(self):
        sentences = [[["a", "b"], ["c", "d"]], [["e", "f"]]]
        result = merge_on_whitespace_tab_newline(sentences)
        self.assertEqual(result, "a b\tc d\ne f")

    def test_empty_subsentences_removed(self):
        sentences = [[["hello"], []], [["world"]]]
        result = merge_on_whitespace_tab_newline(sentences)
        self.assertEqual(result, "hello\nworld")

    def test_all_empty(self):
        sentences = [[[], []], [[]]]
        result = merge_on_whitespace_tab_newline(sentences)
        self.assertEqual(result, "")

    def test_roundtrip_with_split(self):
        doc = "a b\tc d\ne f"
        split_result = split_on_newline_tab_whitespace(doc)
        merged = merge_on_whitespace_tab_newline(split_result)
        self.assertEqual(merged, doc)


class WordsAugmentationTest(DataJuicerTestCaseBase):

    def test_group_size_2(self):
        words = ["a", "b", "c", "d"]
        result = words_augmentation(words, group_size=2, join_char="")
        self.assertEqual(result, ["ab", "bc", "cd"])

    def test_group_size_3(self):
        words = ["a", "b", "c", "d"]
        result = words_augmentation(words, group_size=3, join_char="")
        self.assertEqual(result, ["abc", "bcd"])

    def test_join_char(self):
        words = ["hello", "world", "foo"]
        result = words_augmentation(words, group_size=2, join_char=" ")
        self.assertEqual(result, ["hello world", "world foo"])

    def test_group_size_equals_length(self):
        words = ["a", "b", "c"]
        result = words_augmentation(words, group_size=3, join_char="")
        self.assertEqual(result, ["abc"])

    def test_group_size_larger_than_length(self):
        words = ["a", "b"]
        result = words_augmentation(words, group_size=3, join_char="")
        self.assertEqual(result, [])

    def test_empty_words(self):
        result = words_augmentation([], group_size=2, join_char="")
        self.assertEqual(result, [])

    def test_single_word(self):
        result = words_augmentation(["hello"], group_size=1, join_char="")
        self.assertEqual(result, ["hello"])

    def test_cjk_characters(self):
        words = ["你", "好", "世", "界"]
        result = words_augmentation(words, group_size=2, join_char="")
        self.assertEqual(result, ["你好", "好世", "世界"])


class GetWordsFromDocumentTest(DataJuicerTestCaseBase):

    def test_default_split(self):
        result = get_words_from_document("hello world")
        self.assertEqual(result, ["hello", "world"])

    def test_with_newline(self):
        result = get_words_from_document("hello\nworld", new_line=True)
        self.assertEqual(result, ["hello", "world"])

    def test_without_newline(self):
        result = get_words_from_document("hello\nworld", new_line=False)
        self.assertEqual(result, ["hello\nworld"])

    def test_with_tab(self):
        result = get_words_from_document("hello\tworld", tab=True)
        self.assertEqual(result, ["hello", "world"])

    def test_custom_token_func(self):
        token_func = lambda doc: list(doc)
        result = get_words_from_document("abc", token_func=token_func)
        self.assertEqual(result, ["a", "b", "c"])

    def test_token_func_overrides_splitting(self):
        token_func = lambda doc: [doc]
        result = get_words_from_document("hello world", token_func=token_func)
        self.assertEqual(result, ["hello world"])


class WordsRefinementTest(DataJuicerTestCaseBase):

    def test_lower_case(self):
        words = ["Hello", "WORLD"]
        result = words_refinement(words, lower_case=True)
        self.assertEqual(result, ["hello", "world"])

    def test_strip_chars(self):
        words = ["#hello#", "@world@"]
        result = words_refinement(words, strip_chars={"#", "@"})
        self.assertEqual(result, ["hello", "world"])

    def test_strip_chars_removes_empty(self):
        words = ["##", "hello", "@@"]
        result = words_refinement(words, strip_chars={"#", "@"})
        self.assertEqual(result, ["hello"])

    def test_words_augmentation_enabled(self):
        words = ["a", "b", "c"]
        result = words_refinement(
            words, use_words_aug=True, words_aug_group_sizes=[2], words_aug_join_char=""
        )
        self.assertEqual(result, ["a", "b", "c", "ab", "bc"])

    def test_words_augmentation_multiple_group_sizes(self):
        words = ["a", "b", "c"]
        result = words_refinement(
            words, use_words_aug=True, words_aug_group_sizes=[2, 3], words_aug_join_char=""
        )
        self.assertEqual(result, ["a", "b", "c", "ab", "bc", "abc"])

    def test_combined_operations(self):
        words = ["#Hello#", "#World#", "#Foo#"]
        result = words_refinement(
            words,
            lower_case=True,
            strip_chars={"#"},
            use_words_aug=True,
            words_aug_group_sizes=[2],
            words_aug_join_char="",
        )
        self.assertEqual(result, ["hello", "world", "foo", "helloworld", "worldfoo"])

    def test_no_options(self):
        words = ["Hello", "World"]
        result = words_refinement(words)
        self.assertEqual(result, ["Hello", "World"])


class GetSentencesFromDocumentTest(DataJuicerTestCaseBase):

    def test_default_splitlines(self):
        doc = "hello\nworld"
        result = get_sentences_from_document(doc)
        self.assertEqual(result, "hello\nworld")

    def test_single_line(self):
        doc = "hello world"
        result = get_sentences_from_document(doc)
        self.assertEqual(result, "hello world")

    def test_multiple_lines(self):
        doc = "line1\nline2\nline3"
        result = get_sentences_from_document(doc)
        self.assertEqual(result, "line1\nline2\nline3")

    def test_custom_model_func(self):
        model_func = lambda doc: doc.split(".")
        result = get_sentences_from_document("a.b.c", model_func=model_func)
        self.assertEqual(result, "a\nb\nc")

    def test_empty_document(self):
        result = get_sentences_from_document("")
        self.assertEqual(result, "")

    def test_model_func_overrides_default(self):
        model_func = lambda doc: ["sentence1", "sentence2"]
        result = get_sentences_from_document("ignored", model_func=model_func)
        self.assertEqual(result, "sentence1\nsentence2")


class SplitTextByPunctuationTest(DataJuicerTestCaseBase):

    def test_english_punctuation(self):
        result = split_text_by_punctuation("hello, world!")
        self.assertEqual(result, ["hello", "world"])

    def test_chinese_punctuation(self):
        result = split_text_by_punctuation("你好，世界！")
        self.assertEqual(result, ["你好", "世界"])

    def test_no_punctuation(self):
        result = split_text_by_punctuation("hello world")
        self.assertEqual(result, ["hello world"])

    def test_only_punctuation(self):
        result = split_text_by_punctuation(",.!?")
        self.assertEqual(result, [",.!?"])

    def test_mixed_punctuation(self):
        result = split_text_by_punctuation("hello.world，foo！bar")
        self.assertEqual(result, ["hello", "world", "foo", "bar"])

    def test_empty_string(self):
        result = split_text_by_punctuation("")
        self.assertEqual(result, [""])

    def test_multiple_consecutive_punctuations(self):
        result = split_text_by_punctuation("hello...world")
        self.assertEqual(result, ["hello", "world"])

    def test_parentheses_and_brackets(self):
        result = split_text_by_punctuation("hello(world)[foo]")
        self.assertEqual(result, ["hello", "world", "foo"])

    def test_colon_semicolon(self):
        result = split_text_by_punctuation("key:value;other")
        self.assertEqual(result, ["key", "value", "other"])

    def test_fullwidth_punctuation(self):
        result = split_text_by_punctuation("你好。世界")
        self.assertEqual(result, ["你好", "世界"])


if __name__ == "__main__":
    unittest.main()
