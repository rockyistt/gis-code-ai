# Harness Engineering Research for GIS Code AI

## What "Harness Engineering" Means Here

For this project, harness engineering should not mean only "unit tests". It should mean the system layer around the model and agents that controls:

- repeatable scenarios
- model/RAG/fallback configuration
- human-in-the-loop vs auto execution
- validation and repair policy
- trace capture
- scoring and regression comparison
- failure diagnosis

In other words, the harness evaluates the whole GIS workflow generator as an executable system, not only the fine-tuned model.

## GitHub Projects Reviewed

### 1. EleutherAI lm-evaluation-harness

Repository: https://github.com/EleutherAI/lm-evaluation-harness

Useful ideas:

- standard task registry
- reproducible model evaluation
- support for local models and LoRA/adapters
- custom prompts and custom metrics

How it maps to our project:

- define GIS workflow eval cases as reusable task configs
- compare RAG-only, fine-tuned-model, fallback-only, and hybrid modes
- report stable metrics across local model versions

### 2. OpenAI Evals

Repository: https://github.com/openai/evals

Useful ideas:

- evals as a registry of benchmarks
- private evals based on real workflow data
- custom evals for use-case-specific behavior

How it maps to our project:

- create a private GIS eval registry from historical workflow examples
- split evals into task groups such as CRUD lifecycle, topology cascade, UI navigation, and datamodel checks
- keep expected behavior separate from model implementation

### 3. promptfoo

Repository: https://github.com/promptfoo/promptfoo

Useful ideas:

- declarative prompt/model test configs
- side-by-side model comparison
- CI/CD integration
- local evaluation and reports

How it maps to our project:

- compare prompt templates for the fine-tuned model
- compare model backends: transformers vs llama.cpp server
- compare orchestration modes: native loop vs LangGraph
- run fast regression checks before changing prompts or generation logic

### 4. DeepEval

Repository: https://github.com/confident-ai/deepeval

Useful ideas:

- Pytest-like LLM test cases
- metrics for agents, RAG, JSON correctness, plan adherence, tool correctness, task completion
- component-level and end-to-end evaluation
- LangGraph integration patterns

How it maps to our project:

- JSON correctness -> schema validation
- plan adherence -> selected steps match expected topology/history path
- task completion -> generated workflow satisfies requested GIS intent
- step efficiency -> generated workflow avoids unnecessary steps
- contextual precision/recall -> RAG template selection quality

### 5. Inspect AI

Repository: https://github.com/UKGovernmentBEIS/inspect_ai

Useful ideas:

- evaluation framework for LLMs with tool usage and multi-turn dialog
- model-graded evaluations
- extensible components for scoring and elicitation
- large reusable eval library

How it maps to our project:

- model/tool interaction is relevant because our workflow generator has RAG, local model, fallback, validation, and human choice
- multi-turn evaluation is relevant for one-step-at-a-time planning
- custom scorers can judge GIS workflow correctness beyond raw JSON syntax

### 6. AgentOps

Repository: https://github.com/AgentOps-AI/agentops

Useful ideas:

- agent monitoring
- trace capture
- cost and benchmark tracking
- framework integrations

How it maps to our project:

- capture per-agent timing, source, fallback usage, and failure reason
- create run-level reports for local experiments
- make it easier to compare local CPU deployment against Colab/GPU behavior

### 7. HarnessForge

Repository: https://github.com/mingju-c/HarnessForge

Useful ideas:

- separates harness from model policy
- treats harness and policy as a pair
- diagnoses failures from trajectories
- evolves harness structure based on failure localization

How it maps to our project:

- separate GIS harness configuration from the fine-tuned model itself
- evaluate model quality under different harnesses:
  - RAG-first
  - model-first
  - human-in-the-loop
  - strict schema repair
  - permissive fallback
- use trace failures to decide whether to improve RAG, prompt, normalizer, planner, or validator

## Current Project State

The project already has a small harness:

- `src/agents/harness.py`
- `HarnessCase`
- `WorkflowHarness`
- basic checks for:
  - minimum step count
  - required objects
  - required methods
  - final status

This is a good start, but it is too shallow for the current architecture.

Current limitations:

- no scenario registry file
- no golden workflow comparison
- no RAG metrics
- no fine-tuned-model metrics
- no trace-level failure diagnosis
- no comparison between harness configurations
- no replay of human choices
- no regression report output

## Recommended Harness Architecture

```text
configs/harness/
  scenarios.yaml
  metrics.yaml
  profiles/
    rag_only.yaml
    llm_only.yaml
    hybrid_auto.yaml
    hybrid_human_loop.yaml

src/agents/
  harness.py
  harness_metrics.py
  harness_runner.py
  harness_report.py

reports/harness/
  run_YYYYMMDD_HHMMSS/
    summary.json
    cases.jsonl
    failures.md
    traces/
```

## Harness Profiles

Harness profiles should make execution mode explicit.

Example:

```yaml
name: hybrid_auto_langgraph
engine: langgraph
planning_mode: auto
use_rag: true
load_llm: true
model_backend: llama_cpp_server
max_steps: 5
max_repairs: 2
```

Another example:

```yaml
name: human_loop_rag_first
engine: langgraph
planning_mode: ask
use_rag: true
load_llm: true
choices: [2, 3, 6]
max_steps: 5
```

## Scenario Registry

Each scenario should define:

```yaml
- id: crud_installatie_fp
  prompt: Create E MS Installatie FP
  expected:
    min_steps: 3
    required_methods: [Create, Update, Delete]
    required_objects: [E MS Installatie FP]
    forbidden_debug_fields: true
    allow_fallback: true
```

More advanced scenario:

```yaml
- id: topology_installatie_to_rail
  prompt: Create E MS Installatie FP
  choices: [1, 6]
  expected:
    ordered_steps:
      - method: Create
        object: E MS Installatie FP
      - method: Create
        object: E MS Rail FP
    required_parent_reference: true
```

## Metrics to Add

### Structural Metrics

- valid JSON
- required step keys present
- no debug fields in clean output
- total_steps matches step length
- method is allowed
- object is non-empty

### Workflow Metrics

- required object coverage
- required method coverage
- ordered path match
- parent-child reference exists
- CRUD lifecycle completeness
- UI action support

### RAG Metrics

- RAG attempted
- RAG hit rate
- compatible template rate
- template source score
- fallback after RAG miss

### Fine-Tuned Model Metrics

- model attempted
- model availability
- parseable JSON rate
- schema-normalized success rate
- model-to-intent match rate

### Agent/Harness Metrics

- number of planner decisions
- number of human interventions
- repair count
- fallback count
- validation error count
- runtime per case

## Failure Taxonomy

Harness results should classify failures by owner:

```text
Planner failure
  wrong candidate step
  missing historical option

RAG failure
  no retrieval
  incompatible template
  low score

Fine-tuned model failure
  unavailable model
  unparseable JSON
  schema mismatch
  intent mismatch

Normalizer failure
  dropped important field
  added misleading fallback field

Materializer failure
  wrong ID propagation
  missing parent reference

Validator/Repair failure
  false positive
  false negative
  over-repair
```

This is the most important harness-engineering layer for this project, because it helps decide what should be improved next.

## Implementation Plan

### Phase 1: Strengthen Current Harness

- Extend `HarnessCase` with:
  - expected ordered steps
  - forbidden fields
  - expected sources
  - choice sequences
  - allowed fallback behavior
- Add `HarnessProfile`
- Add JSON/Markdown report generation

### Phase 2: Add Scenario Registry

- Create `configs/harness/scenarios.yaml`
- Create `configs/harness/profiles/*.yaml`
- Add script:

```text
scripts/run_harness.py --profile hybrid_auto --scenarios configs/harness/scenarios.yaml
```

### Phase 3: Add Trace Diagnosis

- Convert `WorkflowState.traces` into case-level diagnosis.
- Attach failure owner:
  - planner
  - RAG
  - model
  - normalizer
  - materializer
  - validator

### Phase 4: Add Regression Comparison

- Compare two harness runs:

```text
reports/harness/run_A
reports/harness/run_B
```

- Show:
  - pass rate delta
  - fallback count delta
  - RAG hit delta
  - model parse success delta
  - new failures
  - fixed failures

## Recommended Direction

Do not directly import a large external harness framework yet.

The project is domain-specific, and the most valuable checks are GIS workflow checks, not generic LLM scores. The best approach is:

1. Keep a lightweight local harness inspired by these projects.
2. Use YAML scenario/profile configs like lm-evaluation-harness and promptfoo.
3. Use pytest-like case assertions inspired by DeepEval.
4. Use trace/failure ownership inspired by HarnessForge and AgentOps.
5. Keep future integration possible with DeepEval or promptfoo after the local harness is stable.

This gives us harness engineering without turning the project into a dependency-heavy evaluation platform.
