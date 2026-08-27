# Juicer：自然语言数据精炼模型

**Juicer** 是基于 [Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) 构建的数据精炼模型（MoE 架构：35B 总参数 / 3B 激活参数）。它能将自然语言描述的清洗指令、过滤规则和语义标注需求转化为结构化输出——严格的标记文本或规范的 JSON。

Juicer **不是**通用聊天模型，而是专为数据精炼工作流设计，支持本地部署以处理敏感数据。

---

## 亮点

- **自然语言驱动** — 用自然语言描述需求（如"去除邮箱、句子去重、规范空白字符"），Juicer 即可执行。
- **顺序敏感** — 能区分"先过滤后清洗"和"先清洗后过滤"的不同效果，并追踪中间状态。
- **结构化语义标注** — 支持评分量规、PII 脱敏、安全分类、幻觉检测等任务，以 JSON 格式输出。
- **本地部署** — 可在自有环境中运行，支持 vLLM、SGLang 和 Transformers 后端。

---

## 核心能力

| 类型 | 说明 | 示例 |
|------|------|------|
| 原子操作 | 单步映射或过滤 | 去除 URL；仅保留英文文本 |
| 组合操作 | 单次执行多个精炼步骤 | 去除邮箱、去重、规范空白 |
| 顺序敏感 | 执行顺序影响中间状态 | 过滤在清洗之前 vs 之后 |
| 语义操作 | PII 脱敏、评分量规、安全标注 | 脱敏标识符；返回结构化评分 |

---

## 模型信息

| 项目 | 描述 |
|------|------|
| 基座模型 | [Qwen/Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) |
| 架构 | Qwen3.6 MoE 因果语言模型；35B 总参数 / 3B 激活参数 |
| 输出格式 | 标记文本或任务特定的规范 JSON |
| 评测服务长度 | 32,768 tokens |
| 许可证 | Apache License 2.0 |

---

## 资源链接

| 资源 | 链接 |
|------|------|
| HuggingFace 模型 | [datajuicer/Juicer-35B-A3B](https://huggingface.co/datajuicer/Juicer-35B-A3B) |
| ModelScope 模型 | [Data-Juicer/Juicer-35B-A3B](https://www.modelscope.cn/models/Data-Juicer/Juicer-35B-A3B) |
| Juicer Playground | [data-juicer-hub/juicer_playground](https://github.com/datajuicer/data-juicer-hub/tree/main/juicer_playground) |

---

## 快速开始

### 1. 部署模型

Juicer 可作为 OpenAI 兼容端点提供服务。在单张 H20（96 GB）上：

```bash
export MODEL_ID=/path/to/juicer-model
bash serve.sh --model "$MODEL_ID" --port 8000
```

### 2. 启动 Playground

[Juicer Playground](https://github.com/datajuicer/data-juicer-hub/tree/main/juicer_playground) 提供交互式界面，可试用配方、浏览展示用例、对比 Juicer 与基座模型：

```bash
pip install -r requirements.txt
export JUICER_BASE_URL=http://localhost:8000/v1
python app.py
# 打开 http://localhost:7860
```

---

## 评测

Juicer 在 [CDR-Bench](https://github.com/lukahhcm/data-juicer-hub/tree/CDR-Bench) 上进行评测，涵盖原子映射/过滤、组合工作流、顺序敏感管道和语义任务（PII、幻觉、量规、安全）。

---

## 了解更多

完整的部署选项（vLLM、SGLang、Transformers）、展示用例、集成代码和 AB 对比设置，请访问 [Juicer Playground README](https://github.com/datajuicer/data-juicer-hub/tree/main/juicer_playground)。
