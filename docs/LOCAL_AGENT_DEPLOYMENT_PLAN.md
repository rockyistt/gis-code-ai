# Local Agent Deployment Plan

This note connects the current project difficulties to a concrete local rollout.

## Existing Difficulty 1: Single Step To Multi Step

`examples/demo_interactive.py` already solves the transition pattern:

- Parse or retrieve the first step.
- Keep an `anchor_step` for the current physical object.
- Use `TopologyEngine.get_downstream_recommendations(...)` to propose next
  actions.
- Keep side actions such as Update/Delete/Run/Switch from moving the anchor.
- Use `InteractiveScaffolder.build_cascade_step(...)` to propagate IDs and
  foreign-key references.

The new `PlannerAgent` preserves this idea in non-interactive form. It chooses
the structural cascade first, then lifecycle actions if no structural edge is
available.

## Existing Difficulty 2: Colab Weights To Local Deployment

The local path should contain either a full model or a LoRA adapter:

```text
models/step-level-model-865/
  adapter_config.json
  adapter_model.bin or adapter_model.safetensors
  tokenizer.json or tokenizer.model or tokenizer_config.json
  training_info.json
```

RAG should contain:

```text
data/processed/rag_index/
  embeddings.npy
  metadata.jsonl
```

Use the preflight script before running inference:

```bash
python scripts/check_local_deployment.py
```

Then run the lightweight model smoke test:

```bash
python scripts/smoke_test_local_model.py
```

Only when the lightweight checks pass, load the 7B model:

```bash
python scripts/smoke_test_local_model.py --load-model --max-tokens 256
```

This mirrors the Colab reload-and-test notebook, but keeps the expensive model
load behind an explicit flag.

If this fails, fix artifacts before debugging agent orchestration. Otherwise a
LangGraph or multi-agent demo may appear broken when the real issue is missing
weights, tokenizer files, or RAG files.

## Existing Difficulty 3: Trying LangChain/LangGraph

The project now supports two orchestration modes:

- `WorkflowLoop`: native Python loop, zero new framework dependency.
- `LangGraphWorkflowLoop`: optional graph runtime for comparison and demos.

Install optional dependencies:

```bash
pip install -r requirements-langgraph.txt
```

Run both modes with the same input:

```bash
python examples/demo_agent_loop.py --engine native "Create E MS Installatie FP"
python examples/demo_agent_loop.py --engine langgraph "Create E MS Installatie FP"
```

Enable the real fallback chain:

```bash
python examples/demo_agent_loop.py --engine native --use-rag --load-llm "Create E MS Installatie FP"
```

Compare:

- status and confidence
- generated step count
- agent trace order
- validation findings
- repair count

This gives a clean experiment: same domain agents, same scaffolder, different
orchestration runtime.
