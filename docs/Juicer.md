# Juicer: Natural-Language Data Refinement Model

**Juicer** is a data-refinement model built on [Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) (MoE architecture: 35B total parameters / 3B activated). It turns natural-language cleaning instructions, filtering rules, and semantic-tagging requirements into structured outputs—strict tagged text or canonical JSON.

Juicer is **not** a general-purpose chat model. It is purpose-built for data-refinement workflows and can be deployed locally to process sensitive data in your own environment.

---

## Highlights

- **Natural-language recipe execution** — describe what you want (e.g., "remove emails, deduplicate sentences, normalize whitespace") and Juicer executes it.
- **Order-sensitive refinement** — distinguishes filtering-before-cleanup from filtering-after-cleanup and tracks intermediate state.
- **Structured semantic tagging** — rubric scoring, PII redaction, safety classification, and hallucination detection with JSON output under defined schemas.
- **Local deployment** — run on your own infrastructure; supports vLLM, SGLang, and Transformers backends.

---

## Core Capabilities

| Type | Description | Examples |
|------|-------------|---------|
| Atomic | Single-step mapper or filter | Remove URLs; keep only English text |
| Compositional | Multiple refinement steps in one pass | Remove emails, deduplicate, normalize whitespace |
| Order-sensitive | Execution order respects intermediate state | Filter before cleanup vs. after cleanup |
| Semantic | PII redaction, rubric scoring, safety tagging | Redact identifiers; return structured scores |

---

## Model Details

| Item | Description |
|------|-------------|
| Base model | [Qwen/Qwen3.6-35B-A3B](https://huggingface.co/Qwen/Qwen3.6-35B-A3B) |
| Architecture | Qwen3.6 MoE causal LM; 35B total / 3B activated parameters |
| Output format | Tagged text or task-specific canonical JSON |
| Evaluated serving length | 32,768 tokens |
| License | Apache License 2.0 |

---

## Resources

| Resource | Link |
|----------|------|
| HuggingFace Model | [datajuicer/Juicer-35B-A3B](https://huggingface.co/datajuicer/Juicer-35B-A3B) |
| ModelScope Model | [Data-Juicer/Juicer-35B-A3B](https://www.modelscope.cn/models/Data-Juicer/Juicer-35B-A3B) |
| Juicer Playground | [data-juicer-hub/juicer_playground](https://github.com/datajuicer/data-juicer-hub/tree/main/juicer_playground) |

---

## Quick Start

### 1. Deploy the model

Juicer can be served as an OpenAI-compatible endpoint. On a single H20 (96 GB):

```bash
export MODEL_ID=/path/to/juicer-model
bash serve.sh --model "$MODEL_ID" --port 8000
```

### 2. Launch the Playground

The [Juicer Playground](https://github.com/datajuicer/data-juicer-hub/tree/main/juicer_playground) provides an interactive UI to try recipes, browse showcase cases, and compare Juicer against the base model:

```bash
pip install -r requirements.txt
export JUICER_BASE_URL=http://localhost:8000/v1
python app.py
# open http://localhost:7860
```

---

## Evaluation

Juicer is evaluated on [CDR-Bench](https://github.com/lukahhcm/data-juicer-hub/tree/CDR-Bench), covering atomic mappers/filters, compositional workflows, order-sensitive pipelines, and semantic tasks (PII, hallucination, rubric, safety).

---

## Learn More

For full deployment options (vLLM, SGLang, Transformers), showcase cases, integration code, and AB comparison setup, visit the [Juicer Playground README](https://github.com/datajuicer/data-juicer-hub/tree/main/juicer_playground).
