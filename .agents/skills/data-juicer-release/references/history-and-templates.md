# 历史线索与内容模板

观察日期：2026-10-16。来自当日上游提交、远端 tags、Release PR、公开 Releases 和 PyPI；未逐次核验所有历史 Actions。使用时刷新配置、版本和状态。

## 历史观察

- 较早版本有直接修改版本号的提交；近期通常用 release 分支和 PR 合入 main，命名大小写并不完全固定。
- v1.5.3 Release PR 主要修改版本和双语 README；v1.5.4、v1.5.5、v1.6.0 还包含回归修复、依赖或测试调整。
- v1.5.3 Release PR 合并提交为 `e95f9979`，tag 指向后续提交 `85e2e8e`；Release PR 合并点不自动等于发布点。
- 当日远端 v1.5.4、v1.5.5、v1.6.0 分别指向 `7061da6a`、`0e40a865`、`cc914ee4`。
- 2024-11-07 提交 `d2e92f93` / PR #465 引入 Release 发布事件触发 PyPI 和 Docker。
- 当日 PyPI 工作流使用 Python 3.10、Hatch、wheel 安装/导入/CLI 冒烟，版本从 `__init__.py` 动态读取。
- Docker 发布 `datajuicer/data-juicer:vX.Y.Z` 和 `latest`；文档响应 main/tag push；OSS 独立同步 `latest`，定时为北京时间周二 00:00。
- 全量回归支持手动触发，定时为北京时间周五 07:00。已存在独立 ElasticJuicer pytest 步骤，不能仅凭 unittest discovery 否定其 CI 接入。
- 公告、PR 合并、Release、PyPI 上传日期可能不同，不能相互代替。

## 用户指定的执行约定

- 全量回归应在分支推送后，在 GitHub 手动触发；不要尝试用本地资源跑全量。
- 全量回归通常需要约 3 小时。此耗时来自用户的操作经验，是排期估计，不是完成时限或已验证的性能保证。
- 选择承载候选 SHA 的仓库和分支，确认 workflow run 的 SHA；如需重跑，先推送修复再触发。远端不可用时报告阻塞，不以本地全量替代。

## 证据入口

- [v1.5.0 PR #918](https://github.com/datajuicer/data-juicer/pull/918)
- [v1.5.2 PR #987](https://github.com/datajuicer/data-juicer/pull/987)
- [v1.5.3 PR #995](https://github.com/datajuicer/data-juicer/pull/995)
- [v1.5.4 PR #1010](https://github.com/datajuicer/data-juicer/pull/1010)
- [v1.5.5 PR #1037](https://github.com/datajuicer/data-juicer/pull/1037)
- [v1.6.0 PR #1068](https://github.com/datajuicer/data-juicer/pull/1068)
- [发布列表](https://github.com/datajuicer/data-juicer/releases)
- [v1.6.0 Release](https://github.com/datajuicer/data-juicer/releases/tag/v1.6.0)
- [PyPI 元数据](https://pypi.org/pypi/py-data-juicer/json)
- [工作流目录](https://github.com/datajuicer/data-juicer/tree/main/.github/workflows)

PR 描述可能保留“草稿”“回归未完成”等历史措辞。当前合并和测试结论应查结构化状态、实际运行，而非仅看描述。

## Release PR 框架

按实际工作改写，不保留未验证断言：

```text
Release/vX.Y.Z

将版本从 OLD 更新为 NEW，并更新双语发布摘要。
发布范围：上一正式 tag → 候选 SHA
主要变化：用户可见行为及对应 PR。
收尾修复：本 PR 新增修复及原因。
兼容性与安装限制：本次实际存在的项目。

验证：
- 本地：命令、结果、覆盖范围。
- 远端：运行链接、对应 SHA、测试数、跳过和失败。
- 包验证：wheel/sdist、安装路径、版本、CLI、最小 recipe。
- 未完成项：实际阻塞或未验证内容。
```

## Release Notes 框架

采用与当前发布页一致的语言；省略空栏目。条目说明用户效果并关联 PR，不直接堆积提交标题。

```text
Release vX.Y.Z: 两到四个主要亮点

Major Updates
Enhancements
New OPs
Fixed Bugs
Acknowledgements
New Contributors

Full Changelog: https://github.com/datajuicer/data-juicer/compare/vOLD...vNEW
```

如加入 Stats、Code diff，先确定 PR/贡献者去重与比较口径，再计算。单独发布的模型、论文或关联仓库应说明与本包版本的关系。
