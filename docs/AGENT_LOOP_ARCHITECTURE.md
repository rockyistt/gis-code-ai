# Agent Loop Architecture

This document describes the new multi-agent layer added on top of the existing
GIS workflow generator.

## Goal

The original project already has strong building blocks:

- `InteractiveScaffolder` generates runnable multi-step GIS JSON.
- `TopologyEngine` recommends physically plausible next steps.
- RAG and the step-level LLM predictor can supply real step templates.

The current implementation has three practical difficulties:

1. `examples/demo_interactive.py` shows the important bridge from one predicted
   step to many workflow steps. Its anchor step, choice queue, and topology
   recommendations are the real multi-step mechanism.
2. The fine-tuned LoRA weights were trained in Colab, so local deployment must
   verify model artifacts, tokenizer files, RAG index files, and local hardware.
3. LangChain/LangGraph are useful to test, but they should be optional because
   the core generator must still run offline without extra orchestration
   dependencies.

The new architecture keeps the existing components and adds a loop/harness layer:

1. `PlannerAgent` converts a user prompt into step-level intents.
2. `GeneratorAgent` calls `InteractiveScaffolder` to materialize JSON.
3. `ValidatorAgent` checks schema, IDs, indices, and method consistency.
4. `RepairAgent` fixes recoverable structural issues.
5. `ReviewerAgent` assigns final status and confidence.

## Loop Engineering

`WorkflowLoop` coordinates the agents with a small feedback loop:

```text
prompt
  -> PlannerAgent
  -> GeneratorAgent
  -> ValidatorAgent
      -> RepairAgent -> ValidatorAgent, until valid or budget exhausted
  -> ReviewerAgent
```

`LangGraphWorkflowLoop` provides the same behavior through LangGraph:

```text
START
  -> plan
  -> init_generation
  -> rag
      -> materialize, when RAG finds a compatible method/object template
      -> fine_tuned_model, when RAG misses and model fallback is enabled
      -> fallback, when no model fallback is enabled
  -> fine_tuned_model
      -> materialize, when the local model returns parseable JSON
      -> fallback, when model loading or prediction fails
  -> fallback
  -> materialize
      -> rag, when more planned steps remain
      -> validate, when workflow generation is complete
  -> validate
      -> repair -> validate, when validation has errors and repair budget remains
      -> review, when valid or repair budget is exhausted
  -> END
```

In the LangGraph path, the generation source is visible per step:

- `RAGAgent`: retrieves a compatible real template from the RAG index.
- `FineTunedModelAgent`: calls the local step-level fine-tuned model when enabled.
- `FallbackAgent`: marks the step for deterministic heuristic generation.
- `StepMaterializerAgent`: writes the chosen template/fallback into workflow JSON.

The loop returns a `WorkflowState` containing:

- `workflow`: generated GIS JSON
- `plan`: step intents
- `findings`: validation/review issues
- `repairs`: deterministic repairs applied
- `traces`: per-agent collaboration trace
- `status`: `ready`, `failed`, or intermediate state
- `confidence`: simple final quality score

## Harness Engineering

`WorkflowHarness` makes repeatable scenario evaluation possible. A harness case
defines a prompt plus expected properties, for example minimum step count,
required objects, or required methods.

This lets the project report loop quality with scenario pass rates instead of
only checking that a script runs.

## Usage

Run the native demo:

```bash
python examples/demo_agent_loop.py "Create E MS Installatie FP"
```

Run the LangGraph demo:

```bash
pip install -r requirements-langgraph.txt
python examples/demo_agent_loop.py --engine langgraph "Create E MS Installatie FP"
```

Run LangGraph with RAG enabled:

```bash
python examples/demo_agent_loop.py --engine langgraph --use-rag \
  "Create E MS Veld FP where Functie, Nummer Kort, Type have Kabelveld, 3, D in elektra"
```

Use from Python:

```python
from src.agents import WorkflowLoop

loop = WorkflowLoop(max_steps=5)
state = loop.run("Create E MS Installatie FP")
print(state.status)
print(state.workflow)
```

Run harness cases:

```python
from src.agents import HarnessCase, WorkflowHarness, WorkflowLoop

harness = WorkflowHarness(WorkflowLoop(max_steps=4))
result = harness.run_case(
    HarnessCase(
        name="substation cascade",
        prompt="Create E MS Installatie FP",
        min_steps=4,
        required_methods=["Create"],
    )
)
print(result.passed)
```

Run the local deployment preflight:

```bash
python scripts/check_local_deployment.py
python scripts/check_local_deployment.py --check-langgraph
```

## Extension Points

- Replace `PlannerAgent` with an LLM planner.
- Enable `GeneratorAgent(use_rag=True)` when the RAG index is available.
- Enable `GeneratorAgent(load_llm=True)` or pass a custom generator when local
  model loading is acceptable.
- Add domain-specific validator rules for station IDs, foreign-key predicates,
  and GIS object lifecycle constraints.
- Add LangSmith tracing when the project needs visual traces of LangGraph node
  transitions and agent state.
