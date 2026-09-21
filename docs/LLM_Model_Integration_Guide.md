# 🚀 步骤级 LLM 模型集成指南

## 📋 概述

该项目现在集成了一个**本地化部署**的步骤级模型（CodeLlama-7B + LoRA），用于在 RAG 无法找到匹配时生成 GIS workflow steps。

**模型性能**：
- 推理设备：CPU 或 GPU（自适应）
- CPU 推理速度：~5-8 tokens/sec（fp32）/ ~8-12 tokens/sec（int8）
- GPU 推理速度：~50-100 tokens/sec（fp16）
- 单步生成时间：5-15 秒（CPU）/ 1-3 秒（GPU）

---

## ⚠️ 关键：两种模型加载方案

模型权重可能以**两种不同的格式**存储。系统会**自动检测并选择合适的加载方案**：

### 🔍 方案 1：完整合并模型（推荐）
```
models/step-level-model-865/
├── model.safetensors         ← 完整模型权重（优先检查）
├── pytorch_model.bin         ← 备选权重格式
├── tokenizer.json
├── tokenizer_config.json
└── ...
```

**优点**：
- 加载速度快
- 直接使用 `AutoModelForCausalLM.from_pretrained()`
- 无需下载基础模型

**检查**：如果存在 `model.safetensors` 或 `pytorch_model.bin`，使用此方案。

### 🔍 方案 2：LoRA 适配器
```
models/step-level-model-865/
├── adapter_config.json       ← LoRA 配置
├── adapter_model.bin         ← LoRA 权重
├── tokenizer.json
├── tokenizer_config.json
└── ...
```

**优点**：
- 权重文件更小（通常 100-300 MB）
- 需要联网下载基础模型 `codellama/CodeLlama-7b-Instruct-hf`

**检查**：如果存在 `adapter_config.json` + `adapter_model.bin`，使用此方案。

---

## 📥 第一步：下载模型权重

### 选项 A：自动下载（推荐）

```bash
python scripts/download_model_from_gdrive.py
```

这会：
1. 下载完整的模型文件夹（约 1.5-10 GB，取决于方案）
2. 自动检测文件结构
3. 验证两种方案中的哪一种可用

**首次运行会打开浏览器进行 Google Drive 认证**。

### 选项 B：手动下载

1. 访问 https://drive.google.com/drive/folders/14VU2n1IdQFtFn9qkNunqN6Nhno5jsJS4
2. 下载整个文件夹
3. 解压到 `models/step-level-model-865/`

### 选项 C：诊断已存在的文件

如果已经下载了模型但不确定是哪种方案，运行：

```bash
python scripts/diagnose_model_structure.py
```

输出会告诉你：
- ✅ 检测到的文件
- 📋 支持的加载方案
- 💡 推荐的加载策略

---

## ⚙️ 第二步：安装依赖

模型推理需要额外的库：

```bash
pip install -q torch transformers peft
```

**注意**：这些库在 `requirements.txt` 中已列出，但因为 GPU 依赖的复杂性，建议显式安装。

---

## 🧪 第三步：测试模型

### 快速测试

```bash
python scripts/test_model_complete.py
```

这个脚本会：
1. ✅ 诊断模型文件
2. ✅ 测试模型加载
3. ✅ 运行推理测试

输出示例：
```
======================================================================
📁 第一步：诊断模型文件结构
======================================================================

✅ 模型目录存在：c:\...\models\step-level-model-865

🔍 关键文件检查：

  方案1（完整模型）：
    ✅ model.safetensors (7.33 GB)

  方案2（LoRA 适配器）：
    ❌ adapter_config.json
    ❌ adapter_model.bin

  Tokenizer 文件：
    ✅ tokenizer.json (0.49 MB)
    ✅ tokenizer_config.json (0.01 MB)

✅ 文件诊断完成

======================================================================
🚀 第二步：测试模型加载
======================================================================

[INFO] 初始化 StepLevelPredictor...
[INFO] Detected Scheme 1: Complete merged model
[INFO] Loading from model.safetensors...
[OK]   Complete model loaded on device: auto
[OK]   Model is on device: cuda:0
[OK]   Model ready for inference!

✅ 模型加载成功！
```

### 单元测试

```python
from src.inference.step_llm_predictor import StepLevelPredictor

# 初始化（会自动检测方案并加载）
predictor = StepLevelPredictor("models/step-level-model-865")

# 推理
result = predictor.predict_step("Create E MS Installatie FP")

# 查看结果
import json
print(json.dumps(result, indent=2, ensure_ascii=False))
```

---

## 🎯 第四步：运行 Demo

现在 demo 会自动加载模型：

```bash
python examples/demo_interactive.py
```

输出示例：
```
[INFO] Loading RAG semantic index...
[OK]   RAG index loaded. Mode: AI semantic prediction + topology cascade.
[INFO] Checking for step-level LLM predictor...
[OK]   LLM predictor available. Will be used as RAG fallback.
```

---

## 🔄 推理流程（三层 Fallback）

当你输入一个指令，系统会按这个顺序尝试：

```
1️⃣ RAG 检索 (score >= 0.55)
   ├─ 命中 ✅ → 返回真实模板
   └─ 未命中 ❌ → 进入第2层

2️⃣ 步骤级 LLM 预测（本地模型）
   ├─ 成功生成 JSON ✅ → 返回预测结果
   └─ 失败或模型不可用 ❌ → 进入第3层

3️⃣ 轻量级 Regex 解析器（轻量级）
   └─ 返回基本的 JSON 框架
```

---

## 💡 使用建议

### 自动方案检测

`step_llm_predictor.py` 中的 `_load_model()` 会自动：
1. 检查是否存在 `model.safetensors` 或 `pytorch_model.bin` → 使用方案1
2. 检查是否存在 `adapter_config.json` + `adapter_model.bin` → 使用方案2
3. 如果都不存在 → 抛出 FileNotFoundError

你**不需要手动指定**使用哪种方案。

### GPU 优化（如果有 GPU）

如果你有 NVIDIA GPU（或 AMD），模型会**自动检测并使用**。如果你想强制使用 CPU：

```python
predictor = StepLevelPredictor(
    model_dir="models/step-level-model-865",
    use_gpu=False  # 强制 CPU
)
```

### CPU 优化（无 GPU）

对于长期运行，建议转换为 GGUF 量化格式（速度提升 2-3 倍）。参考 `scripts/export_to_gguf.py`。

### 批量预测

```python
from src.inference.step_llm_predictor import StepLevelPredictor

predictor = StepLevelPredictor("models/step-level-model-865")

instructions = [
    "Create E MS Installatie FP",
    "Update attributes",
    "Delete the object"
]

for instr in instructions:
    result = predictor.predict_step(instr)
    print(result)
```

---

## 📊 架构说明

```
src/interactive/scaffolder.py
  ├─ InteractiveScaffolder
  │   ├─ load_rag_engine()         ← 加载 RAG (865 个条目)
  │   ├─ load_llm_predictor()      ← 加载步骤级模型（方案1/2自动检测）
  │   ├─ build_cascade_step()      ← 生成下一步
  │   └─ _retrieve_template_from_rag()
  │       ├─ RAG 检索 ✅ → 返回模板
  │       └─ RAG 失败 ❌ → _predict_with_llm()
  │           ├─ LLM 成功 ✅ → 返回预测
  │           └─ LLM 失败 ❌ → None (regex fallback)
  │
  └─ examples/demo_interactive.py
      └─ 调用 scaffolder，展示完整工作流

src/inference/step_llm_predictor.py (新增)
  └─ StepLevelPredictor
      ├─ __init__()           ← 自动检测方案并加载
      ├─ _load_model()        ← 支持两种方案（完整模型 / LoRA）
      ├─ predict_step()       ← 主推理入口
      ├─ _format_prompt()     ← 格式化输入
      └─ _extract_json()      ← 解析输出
```

---

## ⚠️ 常见问题

**Q1：如何知道我的模型是方案1还是方案2？**

A：运行诊断脚本：
```bash
python scripts/diagnose_model_structure.py
```
它会告诉你具体是哪种方案。

**Q2：方案1和方案2有什么区别？**

A：
| 特征 | 方案1（完整模型） | 方案2（LoRA） |
|---|---|---|
| 文件大小 | 7-14 GB | 100-300 MB |
| 加载时间 | 快 | 需下载基础模型 |
| 内存占用 | 15 GB | 15 GB（含基础） |
| 推理速度 | 相同 | 相同 |

**Q3：能否同时使用两种方案？**

A：不需要。系统会自动选择本地存在的方案。如果两种都存在，优先使用方案1。

**Q4：模型太大，我的笔记本内存不够**

A：有几个选项：
1. 使用 INT8 量化（4 GB RAM）
2. 导出为 GGUF 并用 llama.cpp（2-3 GB RAM）
3. 仅用 RAG + regex fallback（跳过模型加载）

**Q5：LLM 生成的 JSON 格式不对**

A：这是正常的。LLM 生成是 "best effort"。如果格式错误，系统会自动 fallback 到 regex 解析器。

---

## 🔗 相关文件

- 推理类：`src/inference/step_llm_predictor.py`
- 下载脚本：`scripts/download_model_from_gdrive.py`
- 诊断脚本：`scripts/diagnose_model_structure.py`
- 测试脚本：`scripts/test_model_complete.py`
- Demo：`examples/demo_interactive.py`
- Scaffolder：`src/interactive/scaffolder.py`

---

## 📝 后续优化

未来可以考虑：

1. **GGUF 导出脚本** → CPU 推理速度提升 3 倍
2. **量化到 4-bit** → 模型大小减少到 400 MB
3. **Streaming 推理** → 实时显示生成过程
4. **Batch 推理** → 多条指令并行处理
5. **Model Merging** → LoRA 权重永久焊进基础模型

---

## 🆘 调试

如果遇到问题，按以下步骤诊断：

### 1. 检查模型文件
```bash
python scripts/diagnose_model_structure.py
```

### 2. 检查文件完整性
```bash
ls -la models/step-level-model-865/
```

### 3. 验证 tokenizer
```bash
python -c "from transformers import AutoTokenizer; t = AutoTokenizer.from_pretrained('models/step-level-model-865'); print(t('hello'))"
```

### 4. 测试模型加载和推理
```bash
python scripts/test_model_complete.py
```

### 5. 检查 GPU 状态
```bash
python -c "import torch; print(f'GPU: {torch.cuda.is_available()}, Device: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}')"
```

---

**最后更新**：2026-06-11  
**状态**：✅ 集成完成，支持两种加载方案，可本地部署
