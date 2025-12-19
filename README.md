# gis-code-ai
AI自动化在GIS测试方面的应用

# 🌍 GIS Code AI - Intelligent GIS JSON Code Generator

<div align="center">

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/rockyistt/gis-code-ai/blob/main/notebooks/00_Quick_Start.ipynb)

**从自然语言到GIS测试代码，一键生成！**

</div>

---

## 📖 项目简介

本项目实现了一个智能GIS JSON代码生成系统，能够根据用户的自然语言描述，自动生成完整的GIS测试工作流代码。

### ✨ 核心特性

- 🤖 **RAG检索增强** - 从1000+代码库中检索相似workflow
- 🔥 **LoRA微调** - 在Colab免费GPU上2小时完成训练
- 🧠 **双粒度建模** - 文件级检索 + 步骤级生成
- 💡 **LLM指令生成** - 自动从代码生成训练数据
- 🎨 **Web界面** - Gradio交互式界面
- 💰 **成本友好** - 总成本<$1，可在Colab免费运行

### 🎯 快速开始

#### 在线运行（推荐）
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/rockyistt/gis-code-ai/blob/main/notebooks/00_Quick_Start.ipynb)

点击上方按钮，5分钟即可体验完整功能！

#### 本地安装
```bash
# 克隆仓库
git clone https://github.com/rockyistt/gis-code-ai.git
cd gis-code-ai

# 安装依赖
pip install -r requirements.txt

# 快速测试
python -m src.data_processing.preprocess_dual_granularity --help
```

## 📊 系统架构

```
用户输入:  "实现点缓冲区分析"
    │
    ▼
┌─────────────────────┐
│  ML预测 (可选)       │ ← 您的文本分析模型
│  预测步骤序列        │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌─────────┐ ┌─────────┐
│RAG检索   │ │LoRA生成 │
│(文件级) │ │(步骤级) │
└────┬────┘ └────┬────┘
     │           │
     └─────┬─────┘
           ▼
    完整JSON代码
```

## 📂 数据准备

### 上传您的JSON测试文件

将原始JSON文件放入 `data/raw/` 目录：

```bash
data/raw/
├── buffer_analysis.json
├── overlay_workflow.json
└── spatial_query.json
```

### JSON文件格式示例

```json
{
  "description": "缓冲区分析工作流",
  "workflow_type": "spatial_analysis",
  "test_modules": [
    {
      "step":  1,
      "module":  "LoadData",
      "description": "加载点数据",
      "code": "{... }"
    },
    {
      "step": 2,
      "module": "BufferAnalysis",
      "description": "执行缓冲区分析",
      "code": "{... }"
    }
  ]
}
```

## 🚀 使用指南

### 步骤1: 数据处理

```python
from src.data_processing.preprocess_dual_granularity import DualGranularityProcessor

processor = DualGranularityProcessor(raw_json_dir="data/raw")
results = processor.process_all(output_dir="data/processed")

# 输出: 
# ✅ 文件级数据:  150 条
# ✅ 步骤级数据: 1200 条
```

### 步骤2: 生成训练指令

```python
from src.data_processing.instruction_generator import InstructionGenerator

generator = InstructionGenerator(llm_backend="openai", model="gpt-4o-mini")
training_data = generator.batch_generate(
    workflow_files=parsed_files,
    output_path="data/processed/train_data.jsonl",
    variants_per_file=5
)

# 成本:  ~$0.05 for 100 files
```

### 步骤3: 构建RAG系统

```python
from src.rag.embedding import GISCodeEmbedder
from src.rag.retriever import GISCodeRetriever

# 构建向量索引
embedder = GISCodeEmbedder()
embedder.build_index("data/processed/file_level_data.jsonl")

# 检索测试
retriever = GISCodeRetriever(embedder)
results = retriever.retrieve("实现缓冲区分析", top_k=3)
```

### 步骤4: LoRA训练（Colab）

在Colab中运行 [`03_LoRA_Training.ipynb`](notebooks/03_LoRA_Training.ipynb)

预计时间:  2-3小时（Colab T4 GPU）

### 步骤5: 生成代码

```python
from src.inference.workflow_generator import WorkflowGenerator

generator = WorkflowGenerator(ml_classifier, rag_retriever, lora_model)
result = generator.generate("我想做点数据的缓冲区分析")

print(result['workflow'])  # 完整的JSON代码
```

### 步骤6: 启动Web界面

```bash
python app/gradio_app.py
```

访问 http://localhost:7860

## 📚 详细文档

- [系统架构](docs/ARCHITECTURE.md) - 完整技术设计
- [数据格式](docs/DATA_FORMAT.md) - 数据结构说明
- [训练指南](docs/TRAINING_GUIDE.md) - 训练最佳实践
- [API文档](docs/API_REFERENCE.md) - 代码接口文档
- [常见问题](docs/FAQ.md) - 疑难解答

## 🎓 Jupyter Notebooks

| Notebook | 描述 | 运行时间 | Colab |
|----------|------|---------|-------|
| [00_Quick_Start](notebooks/00_Quick_Start. ipynb) | 5分钟快速体验 | 5 min | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/rockyistt/gis-code-ai/blob/main/notebooks/00_Quick_Start.ipynb) |
| [01_Data_Processing](notebooks/01_Data_Processing.ipynb) | 完整数据处理流程 | 30 min | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/rockyistt/gis-code-ai/blob/main/notebooks/01_Data_Processing.ipynb) |
| [02_RAG_Setup](notebooks/02_RAG_Setup.ipynb) | RAG系统构建 | 1 hour | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/rockyistt/gis-code-ai/blob/main/notebooks/02_RAG_Setup.ipynb) |
| [03_LoRA_Training](notebooks/03_LoRA_Training.ipynb) | LoRA模型训练 | 2-3 hours | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/rockyistt/gis-code-ai/blob/main/notebooks/03_LoRA_Training.ipynb) |
| [04_Complete_Pipeline](notebooks/04_Complete_Pipeline.ipynb) | 端到端完整流程 | 4-6 hours | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/rockyistt/gis-code-ai/blob/main/notebooks/04_Complete_Pipeline.ipynb) |
| [05_Inference_Demo](notebooks/05_Inference_Demo.ipynb) | 推理演示 | 10 min | [![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/rockyistt/gis-code-ai/blob/main/notebooks/05_Inference_Demo.ipynb) |

## 💰 成本估算

| 项目 | 成本 | 说明 |
|-----|------|------|
| 指令生成 (OpenAI) | $0.05 | 100个文件 × 5变体 |
| LoRA训练 | $0 | Colab免费T4 GPU |
| RAG构建 | $0 | 本地ChromaDB |
| 推理 | $0 | 本地/Colab运行 |
| **总计** | **$0.05** | 几乎免费！ |

## 🔧 技术栈

- **基础模型**:  Qwen2.5-0.5B-Instruct
- **微调**: LoRA (rank=8, alpha=16)
- **向量库**: ChromaDB
- **Embedding**: text2vec-base-chinese
- **训练框架**: Transformers + PEFT
- **UI**: Gradio
- **LLM API**: OpenAI (可选)

## 📈 性能指标

基于测试数据集：

- ✅ JSON语法正确率: 87%
- ✅ 功能匹配准确率: 73%
- ✅ 推理速度: ~3秒/条 (Colab T4)
- ✅ 训练时间: 2.5小时 (1000条数据)

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

## 🙏 致谢

- [Datawhale Happy-LLM](https://github.com/datawhalechina/happy-llm) - 提供LLM学习框架
- [Qwen](https://github.com/QwenLM/Qwen) - 优秀的中文基础模型
- OpenAI - 提供指令生成API

## 📧 联系方式

- 项目链接: [https://github.com/rockyistt/gis-code-ai](https://github.com/rockyistt/gis-code-ai)
- 问题反馈: [Issues](https://github.com/rockyistt/gis-code-ai/issues)

---

<div align="center">
⭐ 如果这个项目对您有帮助，请给我们一个Star！⭐
</div>
