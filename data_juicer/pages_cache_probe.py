"""仅用于隔离验收的 API 夹具，不进入上游 PR。"""


def cache_probe():
    """PAGES_FINAL_API_V2：验证增量重建会更新真实 autodoc 正文。"""
    return "v2"
