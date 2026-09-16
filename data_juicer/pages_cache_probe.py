"""仅用于隔离验收的 API 夹具，不进入上游 PR。"""


def cache_probe():
    """PAGES_FINAL_API_V1：验证真实 autodoc 输出会随源码变化。"""
    return "v1"
