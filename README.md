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

### 🎯 核心目标

从大量GIS平台测试JSON文件中学习，使AI能够理解用户的自然语言指令，并生成相应的GIS操作测试代码。

### ✨ 核心特性

- 📄 **JSON工作流解析** - 将GIS测试JSON文件解析为结构化工作流
- 💡 **智能指令生成** - Step级规则生成 + File级智能聚合，避免信息丢失
- 🧠 **层次化双粒度建模** - File级（业务任务）+ Step级（具体操作）+ 嵌套关系
- ⚖️ **关键词加权系统** - 为不同类型关键词设置权重（动作3.0/对象2.0/上下文1.5）
- 🏗️ **层次化训练策略** - 保留File-Step嵌套关系，利用上下文信息提升质量
- 🤖 **RAG检索增强** - 从代码库中检索相似workflow作为示例
- 🔥 **LoRA高效微调** - 3.2M可训练参数 vs 7B全量，支持加权损失函数
- 🎨 **Web界面** - Gradio交互式界面
- 💰 **成本友好** - 可在Colab免费运行

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

## 📊 完整流程架构

### 🏗️ 双层结构训练架构（File → Steps → JSON）

```
┌────────────────────────────────────────────────────────────────┐
│                      数据处理流程                                │
└────────────────────────────────────────────────────────────────┘

步骤1️⃣：原始数据解析
  4,012 个 raw JSON 文件
      ↓
  WorkflowParser
      ↓
  parsed_workflows.jsonl (13.40 MB)
  ├─ file_id: file_000001 ~ file_004012
  ├─ test_app, test_env
  └─ steps: [step_0, step_1, ..., step_9]
       ├─ method (Create, Update, Open, ...)
       ├─ object (E MS Kabel, HS Kabel, ...)
       ├─ database, module, command
       └─ test_data {create, update, editor}

步骤2️⃣：指令生成
  parsed_workflows.jsonl
      ↓
  InstructionGenerator
      ├─ 文件级指令生成
      └─ 步骤级指令生成
      ↓
  输出两个文件：
  ├─ file_level_instructions.json (4,012 项)
  │   "Test workflow in App: Work with Objects through N steps"
  │
  └─ step_level_instructions.jsonl (40,209 行)
      "Step X/Y: Method Object" + context info
```

### 🎓 双层训练架构

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│                   Task-1: 文件级指令 → 步骤指令                  │
│                                                                   │
│  输入: "Test workflow in GIS: Work with Cables through 7 steps"  │
│       (来自 file_level_instructions.json)                        │
│                                                                   │
│           ↓                                                       │
│         ┌─────────────────────────────┐                          │
│         │   Task-1 模型 (LoRA微调)    │                          │
│         │   CodeLlama-7B + LoRA       │                          │
│         └──────────┬──────────────────┘                          │
│                    ↓                                              │
│  输出: [                                                         │
│    "Step 1/7: Open MS Kabel",                                   │
│    "Step 2/7: Create a new MS Kabel",                           │
│    "Step 3/7: Update HS Kabel",                                 │
│    ...                                                           │
│  ]                                                               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│               Task-2: 步骤指令 → JSON代码                        │
│                                                                   │
│  输入: "Step 2/7: Create a new MS Kabel"                        │
│       (来自 step_level_instructions.jsonl)                       │
│                                                                   │
│       + 上下文:                                                  │
│       - 文件任务: "Work with Cables..."                         │
│       - 前置步骤: ["Step 1: Open MS Kabel"]                     │
│       - 后续步骤: ["Step 3: Update HS Kabel", ...]             │
│                                                                   │
│           ↓                                                       │
│         ┌─────────────────────────────┐                          │
│         │   Task-2 模型 (LoRA微调)    │                          │
│         │   CodeLlama-7B + LoRA       │                          │
│         └──────────┬──────────────────┘                          │
│                    ↓                                              │
│  输出: {                                                         │
│    "action": "create_object",                                   │
│    "params": {                                                   │
│      "object_type": "E MS Kabel",                               │
│      "coordinates": [186355533, 439556907],                     │
│      "properties": {...}                                        │
│    }                                                             │
│  }                                                               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 📊 数据架构对比

| 阶段 | 输入来源 | 输入类型 | 输出类型 | 样本数 | 目的 |
|------|--------|--------|--------|--------|------|
| **Task-1** | file_level_instructions.json | 文件级指令 | 步骤指令列表 | 4,012 | 学习任务分解 |
| **Task-2** | step_level_instructions.jsonl | 步骤指令 + 上下文 | JSON代码 | 40,209 | 学习代码生成 |

### 📈 训练配置

```yaml
Task-1 模型 (文件→步骤):
  - 数据样本: 4,012 个文件级指令
  - 序列长度: 1,024 tokens
  - 训练轮数: 5 epochs
  - 学习率: 5e-5 (较小，保留基础知识)
  - Batch Size: 2, Gradient Accumulation: 2
  - 预期耗时: 2-3 小时 (T4 GPU)

Task-2 模型 (步骤→JSON):
  - 数据样本: 40,209 个步骤指令
  - 序列长度: 512 tokens
  - 训练轮数: 3 epochs
  - 学习率: 1e-4 (标准学习率)
  - Batch Size: 4, Gradient Accumulation: 1
  - 预期耗时: 3-4 小时 (T4 GPU)
```

### 🔄 推理流程（端到端）

```
用户输入:
  "Create cables and configure properties in the system"
          ↓
  Task-1 模型 (文件→步骤)
  生成步骤分解:
    ├─ Step 1/5: Open cable configuration
    ├─ Step 2/5: Create E-type cable
    ├─ Step 3/5: Create H-type cable
    ├─ Step 4/5: Set cable properties
    └─ Step 5/5: Verify configuration
          ↓
  Task-2 模型 (步骤→JSON) 循环处理每个步骤
    ├─ Step 1 → {action: "open_config", params: {...}}
    ├─ Step 2 → {action: "create_object", params: {...}}
    ├─ Step 3 → {action: "create_object", params: {...}}
    ├─ Step 4 → {action: "set_properties", params: {...}}
    └─ Step 5 → {action: "verify", params: {...}}
          ↓
  完整工作流:
  {
    "workflow": {
      "task": "Create cables and configure...",
      "steps": [
        {step: 1, ...},
        {step: 2, ...},
        ...
      ]
    }
  }
```

### 📚 数据文件说明
         │
         ▼
   完整JSON测试代码
```

## 📂 数据处理流程详解

### 步骤1：上传JSON测试文件

将从GIS平台导出的JSON测试文件放入 `data/raw/` 目录：

```bash
data/raw/
├── template/                    # 高质量模板文件（优先处理）
│   ├── template_insert_kabels.json
│   └── template_ms_installatie.json
├── test_data_1/                 # 普通测试数据
│   ├── test_automat0.json
│   └── test_automat1.json
└── test_data_hv/                # 其他测试数据
```

### 步骤2：解析JSON为结构化工作流

```bash
# 运行解析器
python -m src.data_processing.workflow_parser

# 生成: data/processed/parsed_workflows.jsonl
```

**解析效果**：将扁平化的JSON转换为层次化结构，每个工作流包含：
- 文件级元数据：应用名称、数据库、对象类型等
- 步骤级详情：每个操作的模块、方法、参数等

### 步骤3：生成加权指令（双层策略）

#### 3.1 Step级规则生成（高质量）

```bash
# 使用规则引擎生成step级指令（带关键词权重）
python scripts/generate_instructions_weighted.py

# 生成文件:
# - data/processed/step_level_instructions_weighted_variants_marked.jsonl
```

**生成内容**：
- **精确的step级指令**：每个操作步骤都有具体对象名称（无"multiple objects"）
- **关键词权重标注**：
  - 动作词（Create/Update/Delete）：权重 3.0
  - 对象名（E MS Kabel）：权重 2.0
  - 上下文（elektra, database）：权重 1.5
- **变体标记**：每个指令生成3个语言变体，增强训练鲁棒性
- **结构化信息**：保留action、object、adverbials等结构

**示例**：
```json
{
  "instruction": "**Insert** *E HS Aardingstrafo FP* object with 3 attributes elektra database",
  "keywords": [
    ["Insert", 3.0],
    ["E HS Aardingstrafo FP", 2.0],
    ["elektra", 1.5]
  ],
  "structure": {
    "action": "Insert",
    "object": "E HS Aardingstrafo FP object",
    "adverbials": ["with", "3", "attributes", "elektra", "database"]
  }
}
```

#### 3.2 File级智能聚合（规划中）

```bash
# 从step聚合生成file级指令
python scripts/aggregate_step_to_file_instructions.py

# 生成文件:
# - data/processed/file_level_instructions_aggregated.jsonl
```

**聚合策略**：
1. **任务推断**：从文件名识别业务任务
   - `template_insert_kabels` → "Install cables for MS, LS, and HS voltage"
   - `aardingstrafo` → "Configure grounding transformers for MS and HS"
   - `installatie_en_veld` → "Set up installation with rails and fields"

2. **对象智能列表**：从steps提取所有涉及对象，智能总结
   - 列出前3个主要对象
   - 添加类别说明（MS/HS infrastructure）
   - 示例："`E Stationcomplex`, `E MS Aardingstrafo FP`, `E HS Aardingstrafo FP` (and 2 more MS/HS objects)"

3. **操作统计**：汇总所有CRUD操作类型
   - 示例："create, delete, update"

**优势**：相比LLM生成，避免了94.7%的"multiple objects"模糊问题

### 步骤4：构建层次化训练数据（规划中）

生成的数据集格式（保留File-Step嵌套关系）：

**层次化训练样本**：
```json
{
  "instruction": "Create E MS Kabel object with 6 attributes",
  "context": {
    "file_task": "Install cables for MS, LS, and HS voltage levels",
    "current_step": 3,
    "total_steps": 7,
    "previous_steps": [
      {"index": 0, "action": "Open E MS Kabel", "module": "Editor(s)"},
      {"index": 1, "action": "Go to Object Editor", "module": "Tabs"}
    ],
    "remaining_objects": ["E HS Kabel", "E LS Kabel"]
  },
  "keywords": [
    ["Create", 3.0],
    ["E MS Kabel", 2.0],
    ["elektra", 1.5]
  ],
  "output": "{当前步骤的JSON代码}"
}
```

**关键改进**：
- ✅ **File任务描述**：告诉step它在完成什么整体任务（非上下文）
- ✅ **Step上下文感知**：包含前序步骤，避免逻辑错误和重复操作
- ✅ **进度跟踪**：知道当前进度(3/7)和剩余任务
- ✅ **关键词权重**：训练时可使用加权损失函数
- ✅ **依赖关系**：模型理解Open→Create→Update→Delete顺序

**概念澄清**：
- 上下文（Context）**仅存在于Step级训练**
- File级只是任务描述，用于RAG检索和为Step提供整体目标
- File之间是平行关系，无序列依赖

**训练策略**：
- **Context Window** (推荐优先)：简单高效，立即可用
- **Multi-Task Learning** (性能最佳)：File + Step双任务联合训练
- **Hierarchical Generation** (长workflow)：先计划后执行

详见：[层次化训练策略文档](docs/HIERARCHICAL_TRAINING_STRATEGY.md)

### 步骤5：层次化LoRA训练（规划中）

```bash
# 使用层次化训练策略
python -m src.training.train_lora_hierarchical \
  --data data/processed/hierarchical_training_data.json \
  --model CodeLlama/CodeLlama-7b-Instruct-hf \
  --strategy context_window \
  --weighted_loss true \
  --output models/codellama-gis-lora

# 训练参数
# - LoRA rank: 32, alpha: 16
# - 可训练参数: 3.2M (vs 7B全量)
# - 加权损失：keyword_weight × token_loss
# - Context Window: File task + Previous steps
# - 批大小: 1, 梯度累积: 2
```

**训练策略选择**：

| 策略 | 实现难度 | 预期效果 | 适用场景 |
|-----|---------|---------|---------|
| Context Window | ⭐ 简单 | 对象准确率 +13% | 立即实施 |
| Multi-Task Learning | ⭐⭐⭐ 中等 | 对象准确率 +16% | 性能优化 |
| Hierarchical Generation | ⭐⭐⭐⭐ 复杂 | 对象准确率 +18% | 长workflow |

**加权损失函数**：
```python
# 利用关键词权重调整损失
loss = 0
for token, weight in zip(tokens, keyword_weights):
    loss += weight * cross_entropy_loss(predicted, token)
```

详见：[层次化训练策略文档](docs/HIERARCHICAL_TRAINING_STRATEGY.md)

### 步骤6：推理生成（计划中）

```bash
# 命令行推理
python examples/demo_inference.py \
  --instruction "创建一个新的MS电缆并设置3相状态"

# 或启动Web界面
python -m src.app.gradio_ui
```

## 🔍 已实现的功能

✅ JSON工作流解析器 (`src/data_processing/workflow_parser.py`)  
✅ Step级加权指令生成 (`scripts/generate_instructions_weighted.py`)  
✅ 关键词权重系统 (keywords with importance scores)  
✅ "Multiple objects"问题分析工具 (`scripts/analyze_multiple_objects.py`)  
✅ 数据质量分析工具 (`src/data_processing/analyze_data.py`)  
✅ LoRA训练脚本基础版 (`src/training/train_lora.py`)  
✅ 完整处理流水线 (`src/data_processing/run_pipeline.py`)  
✅ 层次化训练策略文档 (`docs/HIERARCHICAL_TRAINING_STRATEGY.md`)

## 🚧 计划中的功能

🔄 **数据处理增强**
- [ ] File级智能聚合脚本（从step推断业务任务）
- [ ] 层次化训练数据构建器（保留File-Step嵌套关系）
- [ ] 依赖关系标注工具（Open→Create→Update→Delete）

🧠 **训练策略升级**
- [ ] Context Window训练实现（File上下文+历史步骤）
- [ ] 加权损失函数（利用关键词重要度）
- [ ] Multi-Task Learning架构（File + Step双头）

🔍 **检索增强**
- [ ] RAG向量化模块（FAISS/sentence-transformers）
- [ ] 文件级相似度检索（基于业务任务匹配）

🎯 **推理与评估**
- [ ] 层次化推理引擎（结合RAG + 上下文生成）
- [ ] 评估框架（对象一致性、步骤顺序、JSON有效性）
- [ ] Gradio交互界面

## 🚀 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/yourusername/gis-code-ai.git
cd gis-code-ai
pip install -r requirements.txt
```

### 2. 准备数据

将你的JSON测试文件放入 `data/raw/` 目录。

### 3. 运行完整流程

```bash
# 设置API密钥
$env:DASHSCOPE_API_KEY="your-dashscope-api-key"

# 运行数据处理流程
python src/data_processing/run_pipeline.py

# 或使用Qwen生成指令
python scripts/generate_instructions_qwen.py
```

### 4. 分析结果

生成的文件在 `data/processed/` 目录：
- `parsed_workflows.jsonl` - 结构化工作流
- `file_level_instructions_qwen.jsonl` - 文件级用户指令
- `step_level_instructions_qwen.jsonl` - 步骤级用户指令

## 📋 项目目录结构

```
gis-code-ai/
├── data/
│   ├── raw/                    # 原始JSON测试文件
│   │   ├── template/           # 高质量模板
│   │   └── test_data_*/        # 普通测试数据
│   └── processed/              # 处理后的数据
│       ├── parsed_workflows.jsonl              # 解析后的工作流
│       ├── file_level_instructions_qwen.jsonl  # 文件级指令
│       └── step_level_instructions_qwen.jsonl  # 步骤级指令
├── src/
│   ├── data_processing/        # 数据处理模块
│   │   ├── workflow_parser.py          # JSON解析器
│   │   ├── instruction_generator.py    # 指令生成器
│   │   ├── analyze_data.py             # 数据分析
│   │   └── run_pipeline.py             # 完整流程
│   ├── rag/                    # RAG检索模块（待实现）
│   ├── inference/              # 推理引擎（待实现）
│   └── app/                    # Web应用（待实现）
├── scripts/
│   └── generate_instructions_qwen.py   # 命令行工具
├── examples/
│   ├── demo_inference.py       # 推理示例
│   └── evaluate_workflows.py   # 评估脚本
├── configs/
│   └── example_config.yaml     # 配置示例
└── docs/
    └── corrected_workflow_evaluation.md  # 评估报告
```

## 📚 核心概念

### 层次化双粒度处理

本项目采用**层次化双粒度**方法处理GIS测试工作流：

#### 1. **步骤级（Step-Level）** - 数据源
   - **生成方式**: 规则引擎（高质量、无信息丢失）
   - **特点**: 
     - ✅ 每个step对象清晰明确
     - ✅ 关键词权重标注（action: 3.0, object: 2.0, context: 1.5）
     - ✅ 无"multiple objects"模糊问题
   - **示例**: "**Insert** *E HS Aardingstrafo FP* object with 3 attributes elektra database"
   - **用途**: 模型训练主要数据源

#### 2. **文件级（File-Level）** - 任务描述
   - **生成方式**: 从步骤聚合 + 文件名推断
   - **特点**:
     - ✅ 推断业务任务：`aardingstrafo` → "Configure grounding transformers"
     - ✅ 智能对象列表：列出前3个 + 类别说明
     - ✅ 避免模糊描述：94.7% → <10% "multiple objects"
     - ❌ 无上下文：File之间是平行关系
   - **示例**: "Configure grounding transformers for MS and HS voltage systems"
   - **用途**: 
     - RAG检索相似案例
     - 为Step训练提供整体任务描述（非上下文）

#### 3. **层次化训练（Hierarchical Training）** - 关键创新
   - **核心思想**: 在Step级训练时引入上下文，让每个step感知：
     - File任务描述（我在完成什么整体目标？）
     - Previous steps历史（之前做了什么？）
     - Remaining objects待处理（还需要做什么？）
   - **注意**: 上下文仅适用于Step级，File级无上下文概念
   - **优势**:
     - 对象匹配率：72% → 85%+ 
     - 步骤顺序正确率：65% → 78%+
     - 避免重复操作和逻辑错误
   - **实现**: Context Window / Multi-Task Learning
   - **详细文档**: [HIERARCHICAL_TRAINING_STRATEGY.md](docs/HIERARCHICAL_TRAINING_STRATEGY.md)

#### 数据流转示意

```
Step级数据（规则生成）
    ↓
  精确、带权重、无信息丢失
    ↓
  ├──→ 直接用于训练（保留上下文）
  │
  └──→ 聚合生成File级（推断任务）
          ↓
      File上下文反馈到Step训练
          ↓
      形成完整的层次化体系
```

### 数据流转示意

```
原始JSON → 解析 → 结构化数据 → LLM生成 → 训练数据 → 模型训练 → 推理
  (raw)         (parsed)        (instructions)    (model)    (generate)
```

## 💰 成本估算

| 项目 | 成本 | 说明 |
|-----|------|------|
| 指令生成 (Qwen) | ¥0.5-2 | 100个文件，约5万tokens |
| 模型训练 | ¥0 | Colab免费GPU或本地GPU |
| RAG向量库 | ¥0 | 本地部署 |
| 推理运行 | ¥0 | 本地或Colab |
| **总计** | **< ¥5** | 非常经济！ |

## 🔧 技术栈

- **LLM**: Qwen / OpenAI GPT
- **数据处理**: Python, JSONL
- **微调框架**: LoRA (PEFT)
- **向量检索**: FAISS / ChromaDB (计划)
- **Web UI**: Gradio (计划)

## 📈 当前进展

✅ **阶段1: 数据准备** (已完成)
- JSON解析器
- 指令生成器 (支持Qwen和OpenAI)
- 数据分析工具
- 批处理脚本

🚧 **阶段2: 模型训练** (进行中)
- [ ] 准备训练数据格式
- [ ] LoRA微调脚本
- [ ] 训练监控

🔜 **阶段3: RAG检索** (计划)
- [ ] 向量化embedding
- [ ] 相似度检索
- [ ] 模板匹配

🔜 **阶段4: 推理系统** (计划)
- [ ] 端到端生成
- [ ] 质量评估
- [ ] Web界面

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启Pull Request

## 📄 许可证

本项目采用 MIT 许可证。

## 🙏 致谢

- [Qwen](https://github.com/QwenLM/Qwen) - 优秀的中文基础模型
- [Datawhale](https://github.com/datawhalechina) - 开源学习社区

---

**⭐ 如果这个项目对你有帮助，请给个Star！**
⭐ 如果这个项目对您有帮助，请给我们一个Star！⭐
</div>
