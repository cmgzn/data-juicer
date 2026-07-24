import sys

from loguru import logger


def _get_executor_type():
    """Peek at --executor_type or config file to decide which analyzer to use."""
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--executor_type" and i + 1 < len(args):
            return args[i + 1]
    for i, arg in enumerate(args):
        if arg == "--config" and i + 1 < len(args):
            try:
                import yaml

                with open(args[i + 1]) as f:
                    cfg = yaml.safe_load(f)
                return cfg.get("executor_type", "default")
            except Exception:
                pass
    return "default"


@logger.catch(reraise=True)
def main():
    executor_type = _get_executor_type()
    if executor_type in ("ray", "ray_partitioned"):
        from data_juicer.core import RayAnalyzer

        analyzer = RayAnalyzer()
    else:
        from data_juicer.core import Analyzer

        analyzer = Analyzer()
    analyzer.run()


if __name__ == "__main__":
    main()
