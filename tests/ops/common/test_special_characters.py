import string
import unittest

from data_juicer.ops.common.special_characters import (
    EMOJI,
    MAIN_SPECIAL_CHARACTERS,
    OTHER_SPECIAL_CHARACTERS,
    SPECIAL_CHARACTERS,
    VARIOUS_WHITESPACES,
)
from data_juicer.utils.unittest_utils import DataJuicerTestCaseBase


class SpecialCharactersTest(DataJuicerTestCaseBase):

    def test_main_special_characters_composition(self):
        """MAIN_SPECIAL_CHARACTERS should be punctuation + digits +
        whitespace."""
        expected = string.punctuation + string.digits + string.whitespace
        self.assertEqual(MAIN_SPECIAL_CHARACTERS, expected)

    def test_other_special_characters_is_nonempty_string(self):
        """OTHER_SPECIAL_CHARACTERS should be a non-empty string."""
        self.assertIsInstance(OTHER_SPECIAL_CHARACTERS, str)
        self.assertGreater(len(OTHER_SPECIAL_CHARACTERS), 0)

    def test_emoji_is_nonempty_list(self):
        """EMOJI should be a non-empty list of strings."""
        self.assertIsInstance(EMOJI, list)
        self.assertGreater(len(EMOJI), 0)
        # Each element should be a string (emoji character)
        for e in EMOJI[:10]:
            self.assertIsInstance(e, str)

    def test_special_characters_is_set(self):
        """SPECIAL_CHARACTERS should be a set."""
        self.assertIsInstance(SPECIAL_CHARACTERS, set)

    def test_special_characters_contains_punctuation(self):
        """SPECIAL_CHARACTERS should contain all ASCII punctuation."""
        for ch in string.punctuation:
            self.assertIn(ch, SPECIAL_CHARACTERS)

    def test_special_characters_contains_digits(self):
        """SPECIAL_CHARACTERS should contain all ASCII digits."""
        for ch in string.digits:
            self.assertIn(ch, SPECIAL_CHARACTERS)

    def test_special_characters_contains_whitespace(self):
        """SPECIAL_CHARACTERS should contain standard whitespace chars."""
        for ch in string.whitespace:
            self.assertIn(ch, SPECIAL_CHARACTERS)

    def test_special_characters_contains_emoji(self):
        """SPECIAL_CHARACTERS should contain emoji characters."""
        # Check a sample of emojis are in SPECIAL_CHARACTERS
        for e in EMOJI[:20]:
            self.assertIn(e, SPECIAL_CHARACTERS)

    def test_special_characters_contains_other_special(self):
        """SPECIAL_CHARACTERS should contain chars from
        OTHER_SPECIAL_CHARACTERS."""
        for ch in OTHER_SPECIAL_CHARACTERS[:20]:
            self.assertIn(ch, SPECIAL_CHARACTERS)

    def test_various_whitespaces_is_set(self):
        """VARIOUS_WHITESPACES should be a set."""
        self.assertIsInstance(VARIOUS_WHITESPACES, set)

    def test_various_whitespaces_is_nonempty(self):
        """VARIOUS_WHITESPACES should contain multiple entries."""
        self.assertGreater(len(VARIOUS_WHITESPACES), 5)

    def test_various_whitespaces_contains_common_whitespace(self):
        """VARIOUS_WHITESPACES should contain regular space and tab."""
        self.assertIn(' ', VARIOUS_WHITESPACES)
        self.assertIn('\t', VARIOUS_WHITESPACES)

    def test_various_whitespaces_contains_unicode_whitespace(self):
        """VARIOUS_WHITESPACES should contain ideographic space (U+3000)
        and zero-width space (U+200B)."""
        self.assertIn('　', VARIOUS_WHITESPACES)  # ideographic space
        self.assertIn('​', VARIOUS_WHITESPACES)  # zero-width space

    def test_various_whitespaces_all_elements_are_strings(self):
        """All elements in VARIOUS_WHITESPACES should be strings."""
        for ws in VARIOUS_WHITESPACES:
            self.assertIsInstance(ws, str)


if __name__ == '__main__':
    unittest.main()
