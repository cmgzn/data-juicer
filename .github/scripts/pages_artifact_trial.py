"""Prepare the complete published site for an isolated artifact-deployment trial."""

import argparse
import json
import re
import shutil
from pathlib import Path

IGNORED = {".git", ".doctrees", ".buildinfo", ".sphinx-cache-state.json", "__pycache__"}


def prepare(source, destination, base_url):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if destination.exists():
        raise ValueError("Destination must not already exist")
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("Snapshot and publication paths must be independent")
    manifest = json.loads((source / "versions.json").read_text())
    versions = manifest["versions"]
    if not versions or len(versions) != len(set(versions)):
        raise ValueError("Invalid published versions")
    if any(not re.fullmatch(r"main|v\d+\.\d+\.\d+", version) for version in versions):
        raise ValueError("Unexpected published ref")
    actual_versions = set()
    for lang, entry in (("en", "index.html"), ("zh_CN", "index_ZH.html")):
        language_refs = {p.name for p in (source / lang).iterdir() if p.is_dir()}
        if language_refs != set(versions):
            raise ValueError(f"Version manifest and {lang} directories disagree")
        for version in versions:
            if not (source / lang / version / entry).is_file():
                raise ValueError(f"Missing entry: {lang}/{version}/{entry}")
            actual_versions.add((lang, version))
    for path in source.rglob("*"):
        if any(part in IGNORED for part in path.relative_to(source).parts):
            continue
        if path.is_symlink():
            raise ValueError(f"Unexpected symbolic link: {path}")
    shutil.copytree(source, destination, ignore=lambda directory, names: set(names) & IGNORED)
    # The documentation pages remain unchanged; only the root redirects target this fork.
    for name in ("index.html", "404.html"):
        path = destination / name
        text = path.read_text()
        text = text.replace("https://datajuicer.github.io/data-juicer", base_url.rstrip("/"))
        path.write_text(text)
    files = [p for p in destination.rglob("*") if p.is_file()]
    byte_count = sum(p.stat().st_size for p in files)
    return {
        "versions": versions,
        "language_version_entries": len(actual_versions),
        "file_count": len(files),
        "bytes": byte_count,
        "above_documented_1GB_limit": byte_count > 1_000_000_000,
        "under_artifact_10GB_absolute_limit": byte_count < 10_000_000_000,
        "excluded_names": sorted(IGNORED),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    report = prepare(args.source, args.destination, args.base_url)
    Path(args.report).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    if report["above_documented_1GB_limit"]:
        print("::warning::Above the documented Pages site limit; this trial measures actual deployment behavior.")
    if not report["under_artifact_10GB_absolute_limit"]:
        raise SystemExit("Artifact exceeds the absolute upload size limit")


if __name__ == "__main__":
    main()
