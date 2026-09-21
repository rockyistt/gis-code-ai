# GIS Code AI

GIS Code AI is a research prototype for converting natural-language GIS test requirements into executable JSON workflows. The current system extends the original single-step generator into a controllable agentic workflow with planning, historical-template retrieval, local model fallback, validation, repair, review, and provenance output.

## Current Architecture

The workflow is organized into five responsibility layers:

1. **Interaction** - accepts a GIS instruction and selects either automatic planning or human-in-the-loop decisions.
2. **Planning** - extracts GIS intents and proposes the next operation using domain topology and historical transitions.
3. **Generation** - retrieves and reranks historical JSON templates, falls back to the fine-tuned model when retrieval misses, and uses deterministic scaffolding if the model is unavailable.
4. **Quality** - validates schema and semantic consistency, repairs recoverable errors, and routes unresolved issues for replanning or human review.
5. **Output** - exports clean executable JSON separately from agent traces and provenance.

LangGraph coordinates the stateful loop and conditional routes. The individual components are responsibility-based workflow nodes rather than independent autonomous agents.

See [Agent Loop Architecture](docs/AGENT_LOOP_ARCHITECTURE.md) and [Latest Architecture Flowchart](docs/LATEST_ARCHITECTURE_FLOWCHART.md).

## Repository Layout

```text
configs/                 Domain synonyms and example configuration
data/raw/                Historical source workflows (access-controlled data)
data/processed/          Generated datasets and the compact RAG index
docs/                    Architecture, deployment, and restart documentation
examples/                Interactive and end-to-end demos
scripts/                 Data, RAG, evaluation, and deployment utilities
src/agents/              Planning, generation, quality, loop, and harness nodes
src/inference/           RAG and local-model inference adapters
src/interactive/         Multi-step workflow scaffolding
tests/                   Focused unit and workflow tests
```

Large model weights, local `llama.cpp` builds, temporary evaluation outputs, Word reports, and internal handover files are intentionally excluded from Git.

## Quick Start

The project was developed with Python 3.12 in `C:\Python\tf_env`. A fresh environment can be created with any equivalent Python installation:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -r requirements-langgraph.txt
python -m pip install pytest
```

Run the focused test suite:

```powershell
python -m pytest tests\test_agent_loop.py -q
```

Run an interactive workflow with RAG and LangGraph:

```powershell
python examples\demo_agent_loop.py --engine langgraph --use-rag --show-agent-trace
```

The demo asks for the initial GIS instruction and whether the system should plan automatically or pause for user choices. A prompt can also be supplied directly:

```powershell
python examples\demo_agent_loop.py "Create E MS Installatie FP" `
  --engine langgraph --planning-mode auto --max-steps 1 `
  --use-rag --show-agent-trace
```

## Inspect and Evaluate RAG

The RAG index uses normalized `all-MiniLM-L6-v2` embeddings plus weighted keyword overlap. A rule-based reranker then checks method, object, requested fields, and JSON-section compatibility.

Inspect retrieval candidates before and after reranking, including their original JSON templates:

```powershell
python scripts\debug_rag_rerank.py "Create E MS Installatie FP" `
  --top-k 10 --show-reasons --show-json all
```

Run the internal non-self reranker benchmark:

```powershell
python scripts\evaluate_rag_reranker.py `
  --query-mode instruction --top-ks 1,3,5,10 --exclude-self `
  --output tmp\rag_reranker_nonself_eval.json
```

This benchmark measures consistency on the existing 865-template corpus. It is not a production-accuracy claim; held-out user prompts and domain-expert labels are still required.

## Optional Local Fine-Tuned Model

The deployable local artifact is the Q4_K_M GGUF model and is not stored in Git:

```text
models/gguf/gis-step-model-Q4_K_M.gguf
```

Clone and build `llama.cpp` separately, then start its local server:

```powershell
git clone https://github.com/ggml-org/llama.cpp external\llama.cpp
powershell -ExecutionPolicy Bypass -File scripts\start_llama_cpp_server.ps1
```

Run the workflow with model fallback enabled:

```powershell
python examples\demo_agent_loop.py "Create E MS Installatie FP" `
  --engine langgraph --planning-mode auto --use-rag --load-llm `
  --model-backend llama_cpp_server --show-agent-trace
```

See [GGUF and llama.cpp Deployment](docs/GGUF_LLAMA_CPP_DEPLOYMENT.md) for conversion and server details.

## Rebuilding the Data and RAG Index

```powershell
python scripts\00_parse_workflows.py
python scripts\01_generate_instructions_and_data.py
python scripts\02_build_rag.py
```

The historical dataset currently contains 4,012 workflows and 40,209 step-level records. The RAG knowledge base contains 865 deduplicated templates. Raw and processed data may contain client-derived structures and must only be copied or shared under the applicable company and client data policy.

## Project Status and Known Limitations

- The complete LangGraph workflow, human-in-the-loop mode, validation routes, clean output, and trace output are implemented.
- RAG retrieval and rule-based reranking are implemented and can be inspected independently.
- The CodeLlama-7B LoRA model has been converted to Q4_K_M GGUF for CPU inference through `llama.cpp`.
- Parameter-rich instructions remain the main model-quality gap and require a curated training/evaluation set.
- Existing reranker results are internal non-self measurements, not an independent production benchmark.
- The local model server is not started automatically and model artifacts must be restored separately.

For a future restart, follow [Project Archive and Restart Guide](docs/PROJECT_ARCHIVE_AND_RESTART_GUIDE.md). Internal successors should also use the separately archived company handover package.

## Data and Security Notes

- Never commit API keys, credentials, `.env` files, model weights, or customer-identifying material.
- Confirm repository visibility and client-data approval before sharing the repository with a new person or organization.
- Store model artifacts and internal reports in an approved company repository or document store, not in public Git history.
- Preserve clean workflow JSON separately from trace JSON; traces can contain prompts, decisions, and retrieved-template provenance.
