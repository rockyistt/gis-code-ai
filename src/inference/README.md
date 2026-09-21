# 🚀 混合推理系统 (Hybrid Inference System)

## 概述

混合推理系统结合了 **RAG (Retrieval-Augmented Generation)** 和 **微调模型** 的优势，提供高效、准确的 GIS 指令解析。

### 工作流程

```
用户指令
   ↓
┌─────────────────┐
│  RAG 检索        │ (利用语义向量 + 关键词权重)
└────────┬────────┘
         ↓
   相似度 >= 0.8?
   ╱            ╲
YES              NO
 │               │
 ↓               ↓
返回 RAG        调用微调模型
结果             进行预测
 │               │
 └───────┬───────┘
         ↓
    返回结果
```

---

## 📦 模块说明

### 1. `hybrid_inference.py` - 混合推理引擎

核心推理类，提供统一的推理接口。

**主要类:** `HybridInferencer`

**功能:**
- 自动加载微调模型（支持 LoRA 和完全合并模型）
- 集成 RAG 检索
- 智能降级（RAG 失败时自动使用模型）
- 批量推理支持

**关键参数:**
- `rag_threshold` (float, 默认 0.8): RAG 相似度阈值
  - 如果 RAG 最高相似度 >= 0.8，使用 RAG 结果
  - 否则使用模型推理
- `top_k` (int, 默认 1): 检索 RAG 时返回的结果数

### 2. `rag_utils.py` - RAG 工具

简化的 RAG 类，用于向量检索和语义匹配。

**主要类:** `StepRAG`

**检索方法:**
- **密集相似度** (70%): 使用 `sentence-transformers` 计算向量余弦相似度
- **关键词重叠** (30%): 基于预存的关键词权重进行加权匹配

**混合分数计算:**
$$\text{score} = 0.7 \times \text{cosine\_sim} + 0.3 \times \text{keyword\_overlap}$$

---

## 🔧 安装和配置

### 前置条件

```bash
# 1. 构建 RAG 索引（如果还没有）
python scripts/02_build_rag.py

# 2. 验证模型文件存在
ls /path/to/gis-models/step-level-model-865/
# 应包含: adapter_config.json, model.safetensors, training_info.json
```

### Python 依赖

```bash
# 基础依赖
pip install torch transformers peft sentence-transformers

# 如果在 Colab 中运行
!pip install -q torch==2.9.0 transformers==4.46.0 peft==0.13.0 sentence-transformers
```

---

## 💡 使用示例

### 基础用法

```python
from src.inference.hybrid_inference import HybridInferencer

# 初始化推理引擎
inferencer = HybridInferencer(
    model_path="/path/to/gis-models/step-level-model-865",
    rag_index_path="/path/to/data/processed/rag_index",
    use_rag=True  # 启用 RAG
)

# 执行推理
result = inferencer.infer(
    instruction="Open E MS Installatie of station 6 002 005",
    rag_threshold=0.8,
    return_details=True
)

# 查看结果
print(f"来源: {result['source']}")           # "rag" 或 "model"
print(f"置信度: {result['confidence']:.4f}")  # 相似度或 1.0
print(f"结果: {result['result']}")           # JSON 输出
```

### 批量推理

```python
instructions = [
    "Open the editor",
    "Create a new cable",
    "Switch to geographical view",
]

results = inferencer.batch_infer(
    instructions,
    rag_threshold=0.8,
    return_details=True
)

for result in results:
    print(f"✅ {result['source'].upper()}: {result['instruction']}")
```

### 在 Jupyter Notebook 中使用

```python
# 在 Colab 中的完整示例
from src.inference.hybrid_inference import HybridInferencer

inferencer = HybridInferencer(
    model_path="/content/drive/MyDrive/gis-models/step-level-model-865",
    rag_index_path="/content/drive/MyDrive/gis-code-ai/data/processed/rag_index",
    use_rag=True,
    device="auto"
)

# 测试
test_instruction = "Open E MS Installatie"
result = inferencer.infer(test_instruction, rag_threshold=0.8)

print("="*70)
print(f"指令: {result['instruction']}")
print(f"来源: {result['source']}")
print(f"说明: {result['explanation']}")
print(f"结果: {result['result']}")
print("="*70)
```

---

## 📊 性能指标

### RAG 检索性能

| 指标 | 值 |
|------|-----|
| 索引大小 | 865 条唯一 instruction-step 对 |
| 向量维度 | 384 维 (all-MiniLM-L6-v2) |
| 检索时间 | ~50ms (GPU) / ~200ms (CPU) |
| 内存占用 | ~2MB (向量) + 10MB (元数据) |

### 模型推理性能

| 指标 | 值 |
|------|-----|
| 基础模型 | CodeLlama-7b-Instruct |
| LoRA 参数 | r=64, alpha=32 |
| 生成时间 | ~1-3s (GPU) / ~10-20s (CPU) |
| 输出长度 | ~100-300 tokens |

---

## ⚙️ 参数调优

### RAG 阈值调整

- **rag_threshold = 0.9** (严格模式)
  - ✅ 高精度，减少错误
  - ❌ 低覆盖率，更多指令使用模型
  
- **rag_threshold = 0.8** (平衡模式 - 推荐)
  - ✅ 好的精度和覆盖率平衡
  - ✅ 较快的响应速度
  
- **rag_threshold = 0.7** (激进模式)
  - ✅ 高覆盖率，快速响应
  - ❌ 可能包含相关性较低的结果

### 优化建议

```python
# 方案 1: 快速响应 (优先 RAG)
inferencer.infer(instruction, rag_threshold=0.7, top_k=1)

# 方案 2: 高精度 (优先模型)
inferencer.infer(instruction, rag_threshold=0.9, top_k=3)

# 方案 3: 均衡 (推荐)
inferencer.infer(instruction, rag_threshold=0.8, top_k=1)
```

---

## 🔍 调试和排查

### 检查 RAG 可用性

```python
if inferencer.rag_available:
    print("✅ RAG 索引可用")
else:
    print("❌ RAG 不可用，将使用模型推理")
```

### 查看 RAG 检索详情

```python
result = inferencer.infer(
    instruction="Open the editor",
    return_details=True
)

if result.get('rag_details'):
    print(f"RAG 相似度: {result['rag_details']['best_score']:.4f}")
    print(f"匹配指令: {result['rag_details']['best_instruction']}")
```

### 模型推理失败排查

```python
try:
    result = inferencer.infer(instruction)
    if result['source'] == 'error':
        print(f"错误: {result['result']}")
except Exception as e:
    print(f"推理异常: {e}")
```

---

## 📝 Notebook 示例

见 `src/training/Reload_model_and_test_20042026.ipynb`:

1. **单元格 1**: RAG 模块加载
2. **单元格 2**: 混合推理函数定义
3. **单元格 3**: 批量测试和结果展示

运行这些单元格可以：
- ✅ 加载 RAG 索引
- ✅ 加载微调模型
- ✅ 执行混合推理
- ✅ 展示性能统计

---

## 🚀 生产部署

### Flask API 示例

```python
from flask import Flask, request, jsonify
from src.inference.hybrid_inference import HybridInferencer

app = Flask(__name__)

# 初始化（启动时执行一次）
inferencer = HybridInferencer(
    model_path="/path/to/model",
    rag_index_path="/path/to/rag/index"
)

@app.route('/infer', methods=['POST'])
def infer():
    data = request.json
    instruction = data.get('instruction', '')
    
    result = inferencer.infer(
        instruction,
        rag_threshold=data.get('rag_threshold', 0.8)
    )
    
    return jsonify({
        'source': result['source'],
        'result': result['result'],
        'confidence': result['confidence'],
        'explanation': result['explanation']
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

### 调用示例

```bash
curl -X POST http://localhost:5000/infer \
  -H "Content-Type: application/json" \
  -d '{"instruction": "Open E MS Installatie", "rag_threshold": 0.8}'
```

---

## 📚 参考资源

- [RAG 构建脚本](../02_build_rag.py)
- [模型训练](../training/)
- [数据处理](../data_processing/)
- [完整文档](../../docs/)

---

## ❓ FAQ

**Q: RAG 和模型各占比多少？**
A: 取决于 `rag_threshold` 设置。建议 0.8 能达到 50-70% 的 RAG 命中率。

**Q: 如何扩展 RAG 知识库？**
A: 运行 `scripts/02_build_rag.py`，它会自动从最新数据生成索引。

**Q: 能否离线使用？**
A: 可以，但需要提前下载模型和 embedding 模型。

**Q: 如何评估推理质量？**
A: 使用 `return_details=True` 获取详细信息，对比 RAG 和模型结果。

---

**最后更新:** 2026-04-20  
**维护者:** GIS Code AI Team
