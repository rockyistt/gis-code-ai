# Project Archive and Restart Guide

This guide is the public-safe entry point for returning to GIS Code AI after a long break. It explains which artifacts are authoritative, how to restore a working environment, and what must be obtained from approved storage rather than GitHub.

## 1. Source of Truth

- Git repository: `https://github.com/rockyistt/gis-code-ai`
- Main branch: `main`
- End-to-end demo: `examples/demo_agent_loop.py`
- LangGraph orchestration: `src/agents/langgraph_loop.py`
- Agent responsibilities and routing: `src/agents/agents.py`
- Interactive multi-step planning: `examples/demo_plan_execute.py`
- RAG build logic: `scripts/02_build_rag.py`
- RAG reranker inspection: `scripts/debug_rag_rerank.py`
- RAG reranker evaluation: `scripts/evaluate_rag_reranker.py`
- Local model server launcher: `scripts/start_llama_cpp_server.ps1`

The architecture diagram source is `docs/architecture_framework_15072026.drawio`. Open `.drawio` files with diagrams.net (draw.io) in a browser or desktop application.

## 2. Artifact Boundaries

### Stored in Git

- Python source, tests, demos, configuration examples, and PowerShell launch scripts
- RAG index metadata and embeddings needed for the compact retrieval path
- Data-processing and model-conversion scripts
- Architecture and deployment documentation
- Historical source and processed data already tracked in this repository; their sharing approval must be confirmed before handover

### Stored outside Git

- Full Hugging Face model: approximately 13.5 GB
- F16 GGUF: approximately 13.5 GB
- Q4_K_M GGUF used for CPU deployment: approximately 4.1 GB
- LoRA adapter artifacts: approximately 67 MB
- Local `llama.cpp` clone and build products
- Temporary RAG evaluation output and runtime logs
- Internship reports, HR summaries, and company-internal handover documents

Before leaving the project, copy non-Git artifacts to an approved company storage location and record the owner, location, access procedure, artifact version, and checksum in the internal handover record.

## 3. Restore the Environment

```powershell
git clone https://github.com/rockyistt/gis-code-ai.git
Set-Location gis-code-ai
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-langgraph.txt
python -m pip install pytest
```

The SentenceTransformers embedding model (`all-MiniLM-L6-v2`) is downloaded on first use unless it is already cached. For an offline company environment, archive its cache separately and document the approved restore location.

The original local environment at `C:\Python\tf_env` was created from a Microsoft Store Python executable under `WindowsApps`. If that base interpreter is removed or inaccessible, the virtual environment launcher may fail even though the folder still exists. Recreate the environment from an installed Python 3.12 interpreter instead of treating the old folder as portable.

## 4. Verify the Code-Only Path

```powershell
python -m pytest tests\test_agent_loop.py -q
python scripts\check_local_deployment.py --check-langgraph
python examples\demo_agent_loop.py "Create E MS Installatie FP" `
  --engine langgraph --planning-mode auto --max-steps 1 `
  --use-rag --show-agent-trace
```

Expected behavior:

- LangGraph is selected as the engine.
- The Context Manager extracts one GIS intent.
- The Planner creates one or more step intents.
- The RAG Agent logs a hit or miss reason.
- The Validator and Reviewer report final status.
- The displayed workflow contains executable fields only; trace data is printed separately when requested.

## 5. Restore the Local Model Path

1. Restore `models/gguf/gis-step-model-Q4_K_M.gguf` from approved storage.
2. Clone `llama.cpp` into `external/llama.cpp`.
3. Build `llama-server` according to `docs/GGUF_LLAMA_CPP_DEPLOYMENT.md`.
4. Start the server with `scripts/start_llama_cpp_server.ps1`.
5. Run the model-enabled demo shown in the root README.

The model is a fallback after a RAG miss. A successful code-only demo does not prove that the model server is loaded; check the agent trace for `FineTunedModelAgent` and inspect its source/failure reason.

## 6. Rebuild and Inspect RAG

To rebuild the index from tracked processed instructions:

```powershell
python scripts\02_build_rag.py
```

To inspect one prompt:

```powershell
python scripts\debug_rag_rerank.py "Create E MS Installatie FP" `
  --top-k 10 --show-reasons --show-json all
```

Do not interpret self-retrieval or non-self retrieval over the same 865-template corpus as production accuracy. Use a held-out, domain-reviewed query set before making an accuracy or reliability claim.

## 7. Safe Working Rules

- Keep internal reports, client names, employee information, and business-sensitive results outside the Git repository unless the repository and content are explicitly approved.
- Do not commit the model directory, `external/`, runtime logs, temporary outputs, or Word documents.
- Check `git status --short` and inspect every untracked file before staging.
- Use `git diff --cached` before committing.
- Keep generated clean workflow JSON and trace/provenance JSON as separate artifacts.
- Record data lineage when regenerating the 40,209 step records or 865 RAG templates.

## 8. Fast Re-entry Checklist

- Read the root README and `docs/AGENT_LOOP_ARCHITECTURE.md`.
- Confirm access to the Git repository and approved artifact storage.
- Restore the Python environment and run tests.
- Verify RAG first, then restore the optional model server.
- Re-run the internal benchmark only as a regression check.
- Review the internal handover's current limitations and prioritized next steps before changing architecture.
