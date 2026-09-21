# GGUF + llama.cpp Local Deployment

This is the recommended local CPU deployment path for the fine-tuned GIS step
model.

## Why

The current local model is a merged 7B model:

```text
models/step-level-model-865/model.safetensors  ~12.6 GB
```

The current environment is CPU-only with limited free RAM. Loading the full
Transformers model directly is not practical. GGUF + llama.cpp lets us quantize
the model and run it as a lightweight local server.

## Target Architecture

```text
LangGraph
  -> RAGAgent
  -> FineTunedModelAgent
       -> LlamaCppServerPredictor
       -> llama.cpp server
       -> quantized GGUF model
  -> FallbackAgent
```

## Install llama.cpp

Install or build llama.cpp so these commands are available on `PATH`:

```text
llama-server
llama-cli
llama-quantize
```

On Windows, the easiest route is usually:

1. Install CMake and Visual Studio Build Tools.
2. Clone `https://github.com/ggml-org/llama.cpp`.
3. Build with CMake according to the llama.cpp README.

## Convert Hugging Face Model To GGUF

Use the project helper script:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\convert_model_to_gguf.ps1 `
  -LlamaCppDir ".\external\llama.cpp" `
  -Quantization Q4_K_M
```

Or run the underlying llama.cpp command manually:

```powershell
python convert_hf_to_gguf.py `
  "C:\Luqi's internship\Github\gis-code-ai\models\step-level-model-865" `
  --outfile "C:\Luqi's internship\Github\gis-code-ai\models\gguf\gis-step-model-f16.gguf"
```

## Quantize

Recommended first quantization:

```powershell
llama-quantize `
  "C:\Luqi's internship\Github\gis-code-ai\models\gguf\gis-step-model-f16.gguf" `
  "C:\Luqi's internship\Github\gis-code-ai\models\gguf\gis-step-model-Q4_K_M.gguf" `
  Q4_K_M
```

If quality is too low, try `Q5_K_M`. If memory is still tight, try `Q4_0`.

## Start Local Server

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_llama_cpp_server.ps1
```

## Configure Project

`configs/local_config.json` contains a `llama_cpp` section:

```json
{
  "llama_cpp": {
    "enabled": false,
    "backend": "server",
    "server_url": "http://127.0.0.1:8080",
    "model_path": "./models/gguf/gis-step-model-Q4_K_M.gguf"
  }
}
```

Set `enabled` to `true` after the server is working.

## Check Deployment

```powershell
python scripts/check_gguf_deployment.py
```

## Use In LangGraph

After llama.cpp server is running:

```powershell
python examples/demo_agent_loop.py `
  --engine langgraph `
  --use-rag `
  --load-llm `
  --model-backend llama_cpp_server `
  "Create E MS Installatie FP"
```

## Sources

- Hugging Face bitsandbytes quantization docs
- Hugging Face GGUF docs
- llama.cpp README
