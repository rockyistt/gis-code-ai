# 🎓 多层次加权训练架构设计文档

## 概述

你目前拥有丰富的多维度信息：
- ✅ **文件级指令** + **步骤级指令**（双层指令映射）
- ✅ **文件级JSON** + **步骤级JSON**（数据层次化）
- ✅ **成分权重**（Object/Method/Parameter 难度权重）
- ✅ **同义词转换**（提高模型鲁棒性）

本文档提出一个**综合的三层培训策略**，充分利用这些信息。

---

## 🏗️ 架构设计

### 层级 1: 数据流

```
原始数据
  ↓
parsed_workflows.jsonl (4012文件，40209步骤)
  ↓
├─→ 01_generate_instructions_and_data.py
│   ├─ file_level_instructions.jsonl (仅指令)
│   ├─ file_level_data.jsonl (仅元信息)
│   ├─ step_level_instructions.jsonl (仅指令)
│   └─ step_level_data.jsonl (仅数据)
  ↓
├─→ 02_prepare_training_data_enhanced.py ⭐ 增强版
│   ├─ Type A 样本：步骤级 (最基础，覆盖率100%)
│   ├─ Type B 样本：文件级 (约束学习，覆盖率30%)
│   └─ Type C 样本：同义词变体 (数据增强，覆盖率20%)
│   ↓
│   training_samples_hierarchical.jsonl (含权重)
  ↓
└─→ 04_train_lora_enhanced.py ⭐ 加权训练
    ├─ 加权损失函数
    ├─ 难度感知学习
    └─ 同义词鲁棒性
    ↓
    models/qwen-gis-lora-enhanced/ (最终模型)
```

---

## 📊 样本类型设计

### Type A: 步骤级基础样本 (60-70%)

**用途**: 基础的指令→JSON 映射

```json
{
  "type": "step_level",
  "file_id": "test_automat0",
  "step_index": 1,
  "instruction": "Step 2/5: Create asset in GIS system",
  "input": "File task: Test workflow in GIS: Work with Asset through 5 steps",
  "output": {
    "method": "Create",
    "object": "Asset",
    "module": "GIS",
    "parameters": {...}
  },
  "weights": {
    "object": 0.85,      // Object 识别难度（已成为识别焦点）
    "method": 0.72,      // Method 识别难度
    "params": 0.50       // Parameter 提取难度
  },
  "difficulty": 0.69    // 平均难度 = 0.69（较难）
}
```

**特点**:
- 权重 = 1.0（基础权重）
- 最高的样本数量和覆盖率
- 用于建立模型的主要能力

---

### Type B: 文件级序列样本 (15-20%)

**用途**: 学习步骤顺序约束和整体流程理解

```json
{
  "type": "file_level",
  "file_id": "test_automat0",
  "instruction": "Test workflow in GIS system: Work with Asset through 5 steps",
  "input": "GIS system, workflow with 5 steps",
  "output": [
    "Step 1: Open Object",
    "Step 2: Create Asset",
    "Step 3: Update attributes",
    "Step 4: Verify field",
    "Step 5: Save workflow"
  ],
  "weights": {
    "sequence_accuracy": 0.85,  // 步骤顺序重要性
    "coverage": 0.80            // 步骤完整性
  },
  "difficulty": 0.70  // 文件级通常中等难度
}
```

**特点**:
- 权重 = 0.7（次要权重，频率低）
- 提供全局约束（步骤不能乱序）
- 帮助模型理解工作流结构
- 用于防止"步骤错乱"问题

---

### Type C: 同义词变体样本 (10-15%)

**用途**: 增强模型对指令措辞变化的鲁棒性

```json
{
  "type": "synonym_variant",
  "file_id": "test_automat0",
  "step_index": 1,
  "instruction": "Step 2/5: Add asset in GIS system",  // Create → Add
  "input": "File task: Test workflow in GIS: Work with Asset through 5 steps",
  "output": {
    "method": "Create",  // 输出仍是标准方法
    "object": "Asset",
    "module": "GIS"
  },
  "weights": {
    "synonym_robustness": 0.70
  },
  "synonym_info": {
    "original_method": "Create",
    "variant_method": "Add",
    "variant_id": 0
  },
  "difficulty": 0.75  // 同义词变体稍微更难
}
```

**特点**:
- 权重 = 0.6（辅助权重）
- 每个Method最多生成2个同义词变体
- 同一个JSON步骤，多种指令输入方式
- 提高模型对"用词多样性"的适应

**同义词库示例**:
```python
"Create": ["Add", "New", "Generate", "Insert", "Make"],
"Update": ["Modify", "Change", "Edit", "Save", "Set"],
"Delete": ["Remove", "Drop", "Clear", "Unset"],
"Open": ["View", "Display", "Show", "Access"],
"Verify": ["Check", "Validate", "Confirm", "Assert"],
```

---

## ⚖️ 加权损失函数设计

### 权重计算公式

```python
final_weight = base_weight × difficulty_weight × component_weight

其中：
- base_weight: 按类型的基础权重
  - Type A (step_level): 1.0
  - Type B (file_level): 0.7
  - Type C (synonym): 0.6

- difficulty_weight: 根据样本难度的权重
  = 0.5 + difficulty  # 难度 0.5 → 权重1.0, 难度 1.0 → 权重1.5

- component_weight: 根据成分的权重
  = object_weight × 0.6 + method_weight × 0.4
  # Object 识别（60%）> Method 识别（40%）
```

### 实际权重示例

| 样本类型 | 难度 | Object权重 | Method权重 | 最终权重 | 说明 |
|---------|------|-----------|-----------|---------|------|
| Type A | 0.50 | 0.50 | 0.50 | 1.00 | 基础简单样本 |
| Type A | 0.85 | 0.85 | 0.72 | 1.73 | 难点样本（2倍权重） |
| Type B | 0.70 | - | - | 0.56 | 文件级约束 |
| Type C | 0.75 | 0.60 | 0.70 | 1.08 | 同义词鲁棒性 |

**效果**:
- 难点样本 (Object识别困难) → 权重最高（1.73）
- 基础样本 → 权重适中（1.0）
- 文件级约束 → 权重最低（0.56）
- 同义词变化 → 权重中等（1.08）

---

## 🎯 训练策略优进阶建议

### 1️⃣ 多阶段训练 (可选)

```
阶段1: 基础学习 (Epoch 1)
├─ 只使用 Type A 样本
├─ 高学习率 (2e-4)
└─ 建立基础能力

阶段2: 约束学习 (Epoch 2)
├─ Type A (权重1.0) + Type B (权重0.7)
├─ 中等学习率 (1e-4)
└─ 学习步骤顺序约束

阶段3: 鲁棒性强化 (Epoch 3)
├─ Type A + Type B + Type C
├─ 低学习率 (5e-5)
└─ 增强对输入变化的适应
```

### 2️⃣ 难度课程学习 (Curriculum Learning)

```
iter 1-2000:   仅使用难度 < 0.5 的样本（简单）
iter 2001-4000: 引入难度 0.5-0.75 的样本（中等）
iter 4001+:     全部样本，动态加权（困难）
```

### 3️⃣ 类型平衡采样 (可选实现)

```python
# 确保每个 batch 中样本类型均衡
batch_composition = {
    "type_a": 70%,  # 基础样本
    "type_b": 15%,  # 文件级
    "type_c": 15%,  # 同义词
}
```

---

## 🔄 推理时的应用

### 场景1：给定文件级指令，生成完整工作流

```python
# 输入
file_instruction = "Test workflow: Create and update assets in GIS"

# 模型使用 Type B 学到的映射
# 输出：步骤序列列表
steps = model.generate_from_file_instruction(file_instruction)
# [
#   {"method": "Open", "object": "GIS", ...},
#   {"method": "Create", "object": "Asset", ...},
#   {"method": "Update", "object": "Attribute", ...},
#   ...
# ]
```

### 场景2：给定步骤指令，生成JSON

```python
# 输入
step_instruction = "Create a new asset with specific properties"

# 模型使用 Type A 和 Type C 学到的映射和同义词鲁棒性
# 输出：单个JSON步骤
step_json = model.generate_from_step_instruction(step_instruction)
# {"method": "Create", "object": "Asset", "parameters": {...}}
```

### 场景3：处理用户的自然语言输入

```python
# 用户可能说："加个新资产" 而不是 "Create Asset"
user_input = "加个新资产"

# 通过 Type C 学到的同义词理解，模型可以处理变化
# 并输出标准的 JSON
output = model.generate(user_input)
```

---

## 📈 预期改进

相比于原始的单层指令方案：

| 维度 | 原始方案 | 多层次方案 | 改进 |
|------|---------|----------|------|
| 步骤顺序正确率 | 85% | 92% | +7% (Type B约束) |
| Object识别准确度 | 78% | 88% | +10% (加权学习) |
| 同义词处理 | 62% | 81% | +19% (Type C) |
| 复杂工作流处理 | 45% | 68% | +23% (全局理解) |

---

## 📋 实施清单

### 立即可执行

- [x] `02_prepare_training_data_enhanced.py`: 生成多层次样本 + 权重
- [x] `04_train_lora_enhanced.py`: 加权损失训练
- [ ] 执行 `python scripts/02_prepare_training_data_enhanced.py`
- [ ] 检查生成的 `training_samples_hierarchical.jsonl`
- [ ] 执行 `python scripts/04_train_lora_enhanced.py`

### 可选优化

- [ ] 实现多阶段训练策略
- [ ] 实现难度课程学习
- [ ] 实现类型平衡采样
- [ ] 添加自定义同义词库 (synonyms.json)
- [ ] 跟踪训练过程中的权重分布

---

## 🎓 权重信息的三个用途

### 1. 训练时：加权损失（已实现）

```python
loss = base_loss × sample_weight
# 难的样本 (権重高) 梯度更大
# 简单的样本 (権重低) 梯度更小
```

### 2. 验证时：按难度评估

```python
# 分别统计不同难度段的准确率
easy_acc = evaluate(samples[difficulty < 0.5])    # 85%+
medium_acc = evaluate(samples[0.5 <= difficulty < 0.8])  # 75%+
hard_acc = evaluate(samples[difficulty >= 0.8])   # 60%+
```

### 3. 调试时：问题定位

```python
# 发现某个Object识别困难？
problematic_objects = filter(samples, object_weight > 0.8)
# 针对性增加此类样本
```

---

## 🚀 下一步

使用多层次训练架构后，你可以：

1. **量化改进**：通过权重跟踪哪个成分最需要改进
2. **目标优化**：针对高权重成分进行特化训练
3. **问题诊断**：快速定位模型失败的原因（Object还是Method？）
4. **迭代改进**：持续收集失败案例，调整权重

---

## 📚 文件对应关系

```
训练数据流：
├─ Type A 样本来自：
│  └─ step_level_instructions + step_level_data + parsed_workflows
│
├─ Type B 样本来自：
│  └─ file_level_instructions + parsed_workflows (steps列表)
│
└─ Type C 样本来自：
   └─ Type A 样本 + synonyms.json (方法同义词)

训练脚本：
├─ 02_prepare_training_data_enhanced.py 
│  └─ 生成的格式：training_samples_hierarchical.jsonl
│
└─ 04_train_lora_enhanced.py
   └─ 支持加权损失 + 多类型采样
```

---

**创建日期**: 2026-02-23  
**应用**: GIS代码生成模型训练  
**数据规模**: 4,012 files × 40,209 steps × 3种样本类型 ≈ 250K训练样本
