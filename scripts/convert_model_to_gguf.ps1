param(
    [string]$LlamaCppDir = "$PSScriptRoot\..\external\llama.cpp",
    [string]$ModelDir = "$PSScriptRoot\..\models\step-level-model-865",
    [string]$OutDir = "$PSScriptRoot\..\models\gguf",
    [string]$PythonExe = "C:\Python\tf_env\Scripts\python.exe",
    [string]$Quantization = "Q4_K_M"
)

$ErrorActionPreference = "Stop"

$llamaCpp = Resolve-Path -LiteralPath $LlamaCppDir
$model = Resolve-Path -LiteralPath $ModelDir
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$out = Resolve-Path -LiteralPath $OutDir
$preparedDir = Join-Path $out "prepared-peft"
$preparedBase = Join-Path $preparedDir "hf-base"
$preparedAdapter = Join-Path $preparedDir "lora-adapter"

$convertScript = Join-Path $llamaCpp "convert_hf_to_gguf.py"
if (-not (Test-Path -LiteralPath $convertScript)) {
    throw "convert_hf_to_gguf.py not found in $llamaCpp"
}

$quantizeCandidates = @(
    (Join-Path $llamaCpp "build\bin\Release\llama-quantize.exe"),
    (Join-Path $llamaCpp "build\bin\llama-quantize.exe"),
    (Join-Path $llamaCpp "llama-quantize.exe")
)
$quantizeExe = $quantizeCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $quantizeExe) {
    throw "llama-quantize.exe not found. Build llama.cpp first."
}

$loraConvertScript = Join-Path $llamaCpp "convert_lora_to_gguf.py"
if (-not (Test-Path -LiteralPath $loraConvertScript)) {
    throw "convert_lora_to_gguf.py not found in $llamaCpp"
}

$f16Path = Join-Path $out "gis-step-model-f16.gguf"
$quantPath = Join-Path $out "gis-step-model-$Quantization.gguf"
$loraPath = Join-Path $out "gis-step-model-lora.gguf"

Write-Host "Preparing PEFT checkpoint for GGUF conversion..."
& $PythonExe "$PSScriptRoot\prepare_peft_gguf_inputs.py" --model-dir $model --out-dir $preparedDir
if ($LASTEXITCODE -ne 0) {
    throw "Failed to prepare PEFT checkpoint."
}

Write-Host "Converting Hugging Face model to GGUF..."
& $PythonExe $convertScript $preparedBase --outfile $f16Path
if ($LASTEXITCODE -ne 0) {
    throw "Failed to convert Hugging Face model to GGUF."
}

Write-Host "Quantizing GGUF model to $Quantization..."
& $quantizeExe $f16Path $quantPath $Quantization
if ($LASTEXITCODE -ne 0) {
    throw "Failed to quantize GGUF model."
}

if (Test-Path -LiteralPath (Join-Path $preparedAdapter "adapter_model.safetensors")) {
    Write-Host "Converting LoRA adapter to GGUF..."
    & $PythonExe $loraConvertScript --base $preparedBase --outfile $loraPath --outtype f16 $preparedAdapter
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to convert LoRA adapter to GGUF."
    }
}

Write-Host ""
Write-Host "Done:"
Write-Host "  $quantPath"
if (Test-Path -LiteralPath $loraPath) {
    Write-Host "  $loraPath"
}
Write-Host ""
Write-Host "Next:"
Write-Host "  powershell -ExecutionPolicy Bypass -File scripts\start_llama_cpp_server.ps1"
