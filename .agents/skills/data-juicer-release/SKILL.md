---
name: data-juicer-release
description: 准备、检查或执行 Data-Juicer 发版，包括版本范围、Release PR、双语公告、发布回归、GitHub Release、PyPI、Docker 和版本文档验收。用于 Data-Juicer 发版或发布状态核查；普通功能开发和单个 PR review 不适用。
---

# Data-Juicer 发版

将历史惯例落实为可核验的发布流程。默认用中文沟通，公告语言跟随目标文件。运行 Python 使用 `uv run python ...`；复用已有环境时可用 `uv run --no-project --python ... python ...`。

## 任务范围

- 总结或审计：读取历史、配置和运行结果，给出流程或差距。
- 准备发版：准备版本、公告、必要修复、验证及 PR 草稿，记录待发布事项。
- 执行发布：按用户已有授权操作。调用此 skill 不自动授权合并、推送 tag、发布 Release、触发具有发布副作用的工作流或发送消息。需要授权时先完成可独立进行的准备，提供具体版本、提交和动作；已有明确授权则不重复询问。
- 不扩大为发布关联仓库、模型或数据集；区分 Python 包版本与论文/品牌的“2.0”等名称。

## 建立当前事实

1. 确认远端、工作区改动、分支和待发布版本。常见上游为 `datajuicer/data-juicer`，本地常见位置为 `/Users/cmgzn/work/data-juicer`；均需核实。读取适用 AGENTS.md，保留已有工作。
2. 刷新上游 main，查询远端 tags、GitHub Releases、近期 Release PR 与 PyPI。本地 tag 冲突时单独核对，不强制覆盖或据此断言远端曾重打 tag。
3. 读取**目标提交**的以下文件；同时检查 main 上的触发配置，识别差异。不要用旧 checkout 的配置代表 PR 或当前 main：
   - `data_juicer/__init__.py`、`pyproject.toml`、`hatch_build.py`
   - `.github/workflows/unit-test.yml`、`unit-test-partial.yml`、`pre-commit.yml`
   - `.github/workflows/publish-pypi.yml`、`publish-docker.yml`、`publish-docker-oss.yml`
   - `.github/workflows/deploy_sphinx_docs.yml`
4. 记录上一正式 tag、候选版本、候选 SHA、比较范围和测试对应 SHA。

需要历史证据或撰写公告时读取 [references/history-and-templates.md](references/history-and-templates.md)。该文件是有日期的观察，使用前仍需刷新事实。

## 准备 Release PR

沿用当时仓库惯例，通常从 main 创建 `Release/vX.Y.Z`，合入 main；用户指定分支时遵从用户。

- 汇总上一正式 tag 到候选提交的已合入改动，关联 PR、用户行为变化、兼容性限制及验证证据。
- 更新 `data_juicer/__init__.py` 中 `__version__`，核实 Hatch 动态版本来源。
- 更新 `README.md`、`README_ZH.md` 的 News，保持双语内容对应。需精简 README 时按现有形式归档至 `docs/news.md`、`docs/news_zh.md`。
- 依赖变化时同步检查 `pyproject.toml`、`uv.lock`，不为发版无理由刷新锁文件。
- 纳入必要回归修复并说明原因；不以发版为由放宽断言、隐藏错误或无依据跳过测试。
- 版本或日期缺失时先完成差异清单和草稿，再询问影响发布的缺失信息，不虚构发布日期。
- 公告只描述实际合入、有证据的行为。明确默认/可选、实验功能和安装限制；不把单测结果当作集群或 GPU 性能证据。

## 验证候选版本

以实际工作流和候选 SHA 为依据，区分以下证据：

1. pre-commit、文档构建、相关定向测试。
2. 全量回归只在分支推送后，通过 GitHub Actions 手动触发 `unittest-regression`（`unit-test.yml`），选择实际承载候选提交的仓库与分支；不要尝试使用本地机器资源运行全量回归，也不要在远端不可用时退回本地跑全量。核对运行的 head SHA 与候选 SHA 一致。全量回归通常约需 3 小时，排队、模型下载等可能延长耗时；等待期间可继续准备公告和核查其他证据，不因尚未结束而重复触发。记录 standalone、Ray 的测试数、跳过数、失败原因和运行链接。partial 通过不能代替全量；旧提交的定时回归需说明覆盖差异。
3. 对 pytest 测试查看**完整工作流**是否另有 pytest 步骤、运行条件和先后顺序。unittest 发现 0 项仅证明该 loader 未执行这些函数，不能据此否定整个 CI 的覆盖。区分“配置会运行”“本轮实际运行”“取消/跳过”。
4. 核对 partial 文件映射。历史规则将 `batch_controller.py` 映射为 `tests/core/elasticjuicer/test_batch_controller.py`，不同名称可能导致全量回退。占位文件仅解决选择问题，不提供覆盖；先确认当前规则。
5. 验证本轮涉及的实际入口和输出，例如 CLI、文件 I/O、Ray Actor、checkpoint 恢复。分别表述注入 OOM、逻辑 GPU、真实 CUDA 和吞吐证据。
6. 按目标构建配置生成 wheel、sdist；在干净环境、仓库目录外安装 wheel，验证导入路径、版本、`dj-process --help`、最小处理 recipe，必要时检查 extras 和资源文件。避免源码目录掩盖打包缺失。

模型下载超时、密钥缺失、依赖冲突与代码失败分别记录；环境问题不能自动算通过。候选代码改变后重新验证受影响路径；依赖、环境或公共入口改变时评估重跑全量，需要重跑时先推送分支，再在 GitHub 手动触发。定向测试和安装包冒烟可按任务需要本地执行，但不能扩展为本地全量回归。不把旧提交结果写成最终提交已全绿。GitHub runner 不可用或权限不足时记录阻塞，不改用本地资源替代。

## 确定发布提交和说明

- PR 合并后核对 main 与已验证提交的关系；若还有修复，重新确定范围和证据。
- tag 指向最终确认的发布提交，不默认等于 Release PR 合并提交。核对 `vX.Y.Z`、源码版本、预期产物一致。
- Release Notes 以最终 tag 差异为准。PR 数、贡献者数、代码统计需明确口径并计算，不能核实则省略。
- 沿用当前页面组织方式，常见栏目为 Major Updates、Enhancements、New OPs、Fixed Bugs、Acknowledgements、New Contributors、Full Changelog。
- README 放双语摘要，GitHub Release 放详细条目、PR 链接和兼容性限制；区分候选日期和实际发布日期。
- 创建 PR 后按环境要求附加到当前聊天。未经用户发消息授权只提供 comment/公告草稿。

## 发布与验收

在授权范围内操作，先核实现有触发配置，再逐条确认：

| 渠道 | 历史触发方式 | 完成证据 |
| --- | --- | --- |
| GitHub Release | 发布正式 Release | tag、目标 SHA、正式/预发布状态、页面内容 |
| PyPI | Release `published` 或手动 | 任务成功，指定版本可安装，版本和入口正确 |
| Docker Hub | Release `published` 或手动 | `vX.Y.Z`、`latest` 的预期 digest，拉取和运行验证 |
| 版本文档 | main/tag push 或手动 | 任务成功，新版本索引和中英文页面可访问 |
| OSS 镜像 | 独立定时或手动 | 任务结果、实际对象和本次镜像来源 |

发布 Release 可能立即触发外部发布，不将 Publish 当作保存草稿。人工补跑前检查 workflow/ref、已存在产物、失败阶段和重复发布风险。失败后先读取状态和日志，避免盲目重试；产物已存在或状态不明时暂停对应重发操作，继续独立核查并报告原因。

OSS 历史任务同步 `latest`，不天然证明某个版本已归档。各渠道独立验收，不由 Release 页面或一个绿色 job 推断其他产物成功。发布任务问题与已发布代码缺陷分开处理；不擅自移动已发布 tag，代码缺陷提出后续修复版本方案。

## 交付记录

按任务范围报告完成工作、证据和剩余事项，不执行未请求的发布：

- 版本、上一 tag、候选/最终 SHA、Release PR 和页面链接。
- 测试与构建：本地通过、远端通过、失败、跳过、取消、未验证分别列出。
- GitHub、PyPI、Docker、文档、OSS 各自状态；范围外项目标记不适用。
- 兼容性变化、已知限制、待决定或授权的具体动作。

历史惯例不等于强制规范；只有实际产物与目标版本核实后才能声称发布完成。
