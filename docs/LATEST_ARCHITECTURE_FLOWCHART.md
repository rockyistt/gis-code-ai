# Latest GIS Code AI Architecture

## High-Level Flow

```mermaid
flowchart TD
    A[User Instruction] --> B{Planning Mode}

    B -->|Auto Mode| C[LangGraph Planner Agent]
    B -->|Ask Mode| D[Plan-and-Execute Controller]

    D --> E[Candidate Step Menu]
    E --> F[Human Decision]
    F --> G[Selected Step Intent]

    C --> H[Step Intent Plan]
    G --> H

    H --> I[Candidate Provider]
    I --> I1[Topology Rules]
    I --> I2[Historical Transition Index]
    I1 --> H
    I2 --> H

    H --> J[LangGraph Execution Graph]

    J --> K[RAG Agent]
    K -->|Template Found| N[Step Template Normalizer]
    K -->|No Match| L[Fine-Tuned Model Agent]

    L -->|JSON Generated| N
    L -->|Unavailable or Invalid| M[Fallback Agent]

    M --> N
    N --> O[Step Materializer Agent]
    O --> P{More Planned Steps?}
    P -->|Yes| K
    P -->|No| Q[Validator Agent]

    Q -->|Schema or Consistency Issues| R[Repair Agent]
    R --> Q
    Q -->|Valid| S[Reviewer Agent]

    S --> T[Clean Workflow JSON]
    S --> U[Trace / Provenance JSON]

    T --> V[Executable Test Workflow]
    U --> W[Debugging, Audit, Presentation Evidence]
```

## Layered View

```mermaid
flowchart LR
    subgraph L1[Interaction Layer]
        A1[User Prompt]
        A2[Auto Mode]
        A3[Human-in-the-Loop Mode]
    end

    subgraph L2[Planning Layer]
        B1[Planner Agent]
        B2[Candidate Provider]
        B3[Topology Rules]
        B4[Historical Transitions]
    end

    subgraph L3[Generation Layer]
        C1[RAG Agent]
        C2[Fine-Tuned Model Agent]
        C3[Fallback Agent]
        C4[Template Normalizer]
        C5[Step Materializer]
    end

    subgraph L4[Quality Layer]
        D1[Validator Agent]
        D2[Repair Agent]
        D3[Reviewer Agent]
    end

    subgraph L5[Output Layer]
        E1[Clean Workflow JSON]
        E2[Trace JSON]
    end

    A1 --> A2
    A1 --> A3
    A2 --> B1
    A3 --> B2
    B1 --> B2
    B2 --> B3
    B2 --> B4
    B2 --> C1
    C1 --> C4
    C1 --> C2
    C2 --> C4
    C2 --> C3
    C3 --> C4
    C4 --> C5
    C5 --> D1
    D1 --> D2
    D2 --> D1
    D1 --> D3
    D3 --> E1
    D3 --> E2
```

## Why These Layers Were Added

### 1. Interaction Layer

The system now supports two planning modes:

- **Auto Mode**: the system plans and executes the workflow automatically.
- **Human-in-the-Loop Mode**: the system pauses at decision points and asks the user to choose the next step.

This is useful because GIS workflows often contain ambiguous transitions. For example, after creating an object, the next action could be update, delete, open, run a check, click a button, or continue with a physical child object.

### 2. Planning Layer

The planning layer separates **what should happen next** from **how the JSON should be generated**.

Candidate steps come from:

- **Topology rules**: domain logic such as installation -> rail -> field.
- **Historical transitions**: real workflow sequences mined from previous test data.

This makes the system more explainable than pure LLM generation because each recommendation has a source and, when available, historical examples.

### 3. Generation Layer

The generation layer uses a fallback chain:

1. **RAG Agent** retrieves a real historical JSON template when a matching step exists.
2. **Fine-Tuned Model Agent** generates a step when RAG cannot find a suitable template.
3. **Fallback Agent** creates a deterministic schema-safe step when both retrieval and model generation are unavailable.

This design keeps the strengths of the original single-step RAG demo, while adding the fine-tuned model as the missing fallback path.

### 4. LangGraph Execution Layer

LangGraph is used to make the multi-agent workflow explicit:

```text
plan -> rag -> fine_tuned_model -> fallback -> materialize -> validate -> repair -> review
```

Instead of hiding the logic inside one large function, each step is represented as a graph node. This makes the architecture easier to debug, extend, and present.

### 5. Quality Layer

The validator, repairer, and reviewer were added because model-generated JSON can be incomplete or noisy.

The quality layer checks:

- required fields
- valid methods
- step index consistency
- object ID consistency
- whether the final workflow is ready to export

This prevents raw model output from being treated as executable workflow JSON too early.

### 6. Output Layer

The final output is split into two files:

- **Clean Workflow JSON**: only executable workflow fields, matching the original data format.
- **Trace JSON**: internal evidence such as selected candidates, agent traces, RAG/model/fallback source, and validation results.

This separation is important because the final JSON should not contain internal decision fields, but the project still needs traceability for debugging and presentation.

## Suggested Presentation Summary

The latest architecture changes the project from a single-step generator into a controllable multi-agent workflow system.

The key improvement is separation of responsibilities:

- planning decides the next possible steps
- RAG retrieves historical templates
- the fine-tuned model fills gaps when RAG has no answer
- fallback logic guarantees a runnable structure
- LangGraph coordinates the agents
- validation and repair improve reliability
- clean output and trace output separate execution from explanation

This makes the system more robust, explainable, and closer to a practical local deployment workflow.
