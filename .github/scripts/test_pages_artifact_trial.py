import json
import tempfile
import unittest
from pathlib import Path

from pages_artifact_trial import prepare


class SnapshotTrialTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.destination = self.root / "publish"
        (self.source / "versions.json").write_text(json.dumps({"versions": ["main", "v1.4.0"]}))
        for lang, entry in (("en", "index.html"), ("zh_CN", "index_ZH.html")):
            for ref in ("main", "v1.4.0"):
                folder = self.source / lang / ref
                folder.mkdir(parents=True)
                (folder / entry).write_text(f"{lang}/{ref}")
                (folder / ".doctrees").mkdir()
                (folder / ".doctrees" / "environment.pickle").write_bytes(b"cache")
        for name in ("index.html", "404.html"):
            (self.source / name).write_text("https://datajuicer.github.io/data-juicer/en/main/")

    def test_preserves_every_language_version_and_omits_build_caches(self):
        report = prepare(self.source, self.destination, "https://cmgzn.github.io/data-juicer")
        self.assertEqual(report["language_version_entries"], 4)
        self.assertEqual(report["versions"], ["main", "v1.4.0"])
        self.assertFalse(list(self.destination.rglob("environment.pickle")))
        for lang, entry in (("en", "index.html"), ("zh_CN", "index_ZH.html")):
            for ref in report["versions"]:
                self.assertEqual((self.destination / lang / ref / entry).read_bytes(),
                                 (self.source / lang / ref / entry).read_bytes())
        self.assertIn("cmgzn.github.io", (self.destination / "index.html").read_text())

    def test_missing_historical_entry_fails_before_copy(self):
        (self.source / "zh_CN" / "v1.4.0" / "index_ZH.html").unlink()
        with self.assertRaisesRegex(ValueError, "Missing entry"):
            prepare(self.source, self.destination, "https://cmgzn.github.io/data-juicer")
        self.assertFalse(self.destination.exists())

    def test_unlisted_version_is_not_silently_dropped(self):
        (self.source / "en" / "v1.5.0").mkdir()
        with self.assertRaisesRegex(ValueError, "disagree"):
            prepare(self.source, self.destination, "https://cmgzn.github.io/data-juicer")

    def test_symbolic_links_are_rejected(self):
        (self.source / "en" / "main" / "bad-link").symlink_to(self.root)
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            prepare(self.source, self.destination, "https://cmgzn.github.io/data-juicer")

    def test_existing_destination_is_not_overwritten(self):
        self.destination.mkdir()
        with self.assertRaisesRegex(ValueError, "already exist"):
            prepare(self.source, self.destination, "https://cmgzn.github.io/data-juicer")


if __name__ == "__main__":
    unittest.main()
