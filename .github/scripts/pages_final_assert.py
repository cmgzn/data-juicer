"""仅用于隔离验收：检查真实双语/API 产物及缓存过滤。"""

import json
import os
import re
from pathlib import Path

site = Path(os.environ["PUBLISH_DIR"])
repo = Path(os.environ["GITHUB_WORKSPACE"]) / "repo"
forbidden = {".git", ".doctrees", ".buildinfo", ".sphinx-cache-state.json", "environment.pickle"}
leaks = [str(path.relative_to(site)) for path in site.rglob("*") if path.name in forbidden]
assert not leaks, f"发布目录泄漏缓存：{leaks[:20]}"
versions = json.loads((site / "versions.json").read_text())["versions"]
assert versions == ["main", "v999.0.0"], versions
summary = {"versions": versions, "cache_leaks": leaks, "entries": []}
for lang, entry in (("en", "index.html"), ("zh_CN", "index_ZH.html")):
    for version in versions:
        root = site / lang / version
        page = root / entry
        assert page.is_file() and page.stat().st_size > 1000, str(page)
        api = [path for path in root.rglob("*.html") if "api" in path.relative_to(root).parts]
        assert len(api) > 50, (lang, version, "缺少真实 API 页面", len(api))
        summary["entries"].append({"lang": lang, "version": version, "api_pages": len(api)})
    root = site / lang / "main"
    keep = (root / "pages_cache_keep.html").read_text()
    probe = (repo / "data_juicer/pages_cache_probe.py").read_text()
    marker = re.search(r"PAGES_FINAL_API_V\d+", probe).group()
    assert marker in keep, (lang, "API 内容未更新", marker)
    removed_source = repo / "docs/sphinx_doc/source/pages_cache_removed.rst"
    removed_page = root / "pages_cache_removed.html"
    assert removed_page.exists() == removed_source.exists(), (lang, "删除页面残留或缺页")
    if not removed_source.exists():
        for name in ("searchindex.js", "genindex.html"):
            assert "pages_cache_removed" not in (root / name).read_text(), (lang, name)
    summary[lang] = {"api_marker": marker, "removed_page_exists": removed_page.exists()}
print("PAGES_FINAL_ASSERT " + json.dumps(summary, ensure_ascii=False, sort_keys=True))
