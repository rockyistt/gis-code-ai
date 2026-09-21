param(
    [string]$LlamaCppDir = "$PSScriptRoot\..\external\llama.cpp",
    [string]$ModelPath = "$PSScriptRoot\..\models\gguf\gis-step-model-Q4_K_M.gguf",
    [string]$LoraPath = "$PSScriptRoot\..\models\gguf\gis-step-model-lora.gguf",
    [string]$HostName = "127.0.0.1",
    [int]$Port = 8080,
    [int]$ContextSize = 2048,
    [int]$Threads = 8
)

$ErrorActionPreference = "Stop"

$model = Resolve-Path -LiteralPath $ModelPath
$llamaCpp = Resolve-Path -LiteralPath $LlamaCppDir
$lora = $null
if ($LoraPath -and (Test-Path -LiteralPath $LoraPath)) {
    $lora = Resolve-Path -LiteralPath $LoraPath
}

$serverCandidates = @(
    (Join-Path $llamaCpp "build\bin\Release\llama-server.exe"),
    (Join-Path $llamaCpp "build\bin\llama-server.exe"),
    (Join-Path $llamaCpp "llama-server.exe")
)
$serverExe = $serverCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $serverExe) {
    throw "llama-server.exe not found. Build llama.cpp first."
}

Write-Host "Starting llama.cpp server..."
Write-Host "  model: $model"
if ($lora) {
    Write-Host "  lora:  $lora"
}
Write-Host "  url:   http://${HostName}:${Port}"

$serverArgs = @(
    "-m", $model,
    "--host", $HostName,
    "--port", $Port,
    "--ctx-size", $ContextSize,
    "--threads", $Threads
)
if ($lora) {
    $serverArgs += @("--lora", $lora)
}

& $serverExe @serverArgs
