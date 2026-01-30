# 📚 中文快速导航

## 🎯 我想要...

### � 修复Colab崩溃问题（重要！）

**症状**: 训练时正常，从Google Drive加载时崩溃

**一行代码解决**:
```python
# 训练后保存
from colab_model_utils import save_model_safely
save_model_safely(trainer, tokenizer, "codellama-gis-lora")

# 新Session加载
from colab_model_utils import load_model_safely
model, tokenizer = load_model_safely("codellama-gis-lora", use_local_cache=True)
```

📖 详见: [COLAB_DRIVE_CRASH_FIX.md](COLAB_DRIVE_CRASH_FIX.md)

**原因**: Drive文件异步同步 + I/O瓶颈 + 内存峰值  
**解决**: 本地保存→验证→Drive，加载时Drive→本地缓存→分步加载

---

### �🚀 立即测试模型（5分钟）

1. **打开你的Colab Notebook** → 找到 **步骤8** 的新单元格
2. **运行3个单元格**：
   - 单元格8.1: 加载模型
   - 单元格8.2: 推理测试  
   - 单元格8.3: 评估性能

**预期结果**: 看到JSON有效率、步骤数、综合评分

📖 详见: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)

---

### 💻 在Python中使用模型（3行代码）

```python
from src.inference.load_model import load_model_from_drive
generator = load_model_from_drive()
result = generator.generate("Create MS cable")
print(result["generated_code"])
```

📖 详见: [MODEL_LOADING_SUMMARY.md](MODEL_LOADING_SUMMARY.md#第2步推理测试)

---

### 📊 评估模型在测试集上的性能

```python
from src.inference.evaluate_model import ModelEvaluator
import json

with open('data/training/training_data_val.json') as f:
    test_data = json.load(f)

evaluator = ModelEvaluator(load_model_from_drive())
results = evaluator.evaluate_on_dataset(test_data, num_samples=100)
evaluator.print_summary(results)
```

📖 详见: [MODEL_LOADING_SUMMARY.md](MODEL_LOADING_SUMMARY.md#第3步评估模型)

---

### 🔧 理解模型架构和工作原理

📖 阅读: [TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md](TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md)

**包含内容**:
- 技术栈详解
- 模型如何工作
- 评估指标说明
- 推理流程图

预计阅读时间: **20-30分钟**

---

### 🚀 改进模型准确性

📖 阅读: [TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md#-三改进方案三层架构](TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md)

**改进方案包括**:
1. **RAG检索** - 让模型参考相似训练样本
2. **模板约束** - 保证生成JSON结构完整
3. **依赖解析** - 保证步骤顺序合理

**4个阶段实施路线图** (总耗时4-7周)

---

### ❌ 我遇到了问题

查看对应的故障排查：

| 错误 | 查看这里 |
|------|---------|
| `FileNotFoundError: 模型路径不存在` | [MODEL_LOADING_SUMMARY.md#问题-文件notfounderror](MODEL_LOADING_SUMMARY.md) |
| `OutOfMemoryError: CUDA out of memory` | [MODEL_LOADING_SUMMARY.md#问题-outofmemoryerror](MODEL_LOADING_SUMMARY.md) |
| `生成的JSON无效` | [MODEL_LOADING_SUMMARY.md#问题-生成的json无效](MODEL_LOADING_SUMMARY.md) |

---

## 📂 文件导航

### 🟢 我是新手，想快速了解

```
1. 读 QUICK_REFERENCE.md (5分钟)
   ↓
2. 运行 Notebook单元格8 (5分钟)
   ↓
3. 读 MODEL_LOADING_SUMMARY.md (10分钟)
```

**总耗时: 20分钟** → 你会掌握所有基础

---

### 🟡 我想深入理解技术细节

```
1. 读 TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md (30分钟)
   ↓
2. 查看源代码: src/inference/load_model.py (15分钟)
   ↓
3. 查看源代码: src/inference/evaluate_model.py (15分钟)
```

**总耗时: 60分钟** → 你会完全理解架构

---

### 🔴 我想改进模型

```
1. 阅读 TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md 的改进方案部分 (30分钟)
   ↓
2. 理解 RAG + 模板约束系统 (20分钟)
   ↓
3. 按照4阶段路线图实施 (4-7周)
```

---

## 🎓 文档清单

### 📌 必读 (这3份，10分钟快速掌握)

| 文档 | 用途 | 时间 |
|------|------|------|
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | 60秒快速开始 + 常用代码 | 5分钟 |
| [MODEL_LOADING_SUMMARY.md](MODEL_LOADING_SUMMARY.md) | 完整总结 + 常见操作 | 5分钟 |
| Notebook单元格8 | 实际运行 + 看结果 | 5分钟 |

### 📚 补充阅读 (按需选择)

| 文档 | 用途 | 何时读 |
|------|------|-------|
| [QUICK_MODEL_LOADING_GUIDE.md](QUICK_MODEL_LOADING_GUIDE.md) | 3种加载方式详解 | 想了解更多选项时 |
| [COLAB_MODEL_INFERENCE_GUIDE.md](COLAB_MODEL_INFERENCE_GUIDE.md) | 完整Colab代码 | 需要现成代码粘贴时 |
| [TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md](TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md) | 技术深度讨论 | 想改进模型时 |
| [INDEX.md](INDEX.md) | 完整导航 | 查找特定内容时 |

---

## 💡 常见问题速答

### Q: 模型保存在哪里？
**A**: `/content/drive/MyDrive/gis-models/codellama-gis-lora/`

### Q: 怎样加载模型？
**A**: 
```python
from src.inference.load_model import load_model_from_drive
generator = load_model_from_drive()
```

### Q: 怎样生成代码？
**A**:
```python
result = generator.generate("Create MS cable")
print(result["generated_code"])
```

### Q: 怎样评估模型？
**A**:
```python
from src.inference.evaluate_model import ModelEvaluator
evaluator = ModelEvaluator(generator)
results = evaluator.evaluate_on_dataset(test_data)
evaluator.print_summary(results)
```

### Q: 模型性能如何评估？
**A**: 4个指标
- JSON有效性 (能否被json.loads()解析)
- 结构匹配度 (包含必要字段程度)
- 语义相似度 (与参考代码相似程度)
- 综合评分 (加权平均)

### Q: 如何改进模型？
**A**: 三个方向
1. RAG检索 - 参考相似训练样本
2. 模板约束 - 保证结构完整
3. 数据增强 - 用模板标注训练数据

详见: [TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md](TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md)

### Q: 遇到问题怎么办？
**A**: 查看[MODEL_LOADING_SUMMARY.md#-故障排查](MODEL_LOADING_SUMMARY.md)

---

## 🚀 30秒入门

```python
# 1. 加载
from src.inference.load_model import load_model_from_drive
gen = load_model_from_drive()

# 2. 推理
result = gen.generate("Create cable")
print(result["generated_code"])

# 3. 完成 ✅
```

---

## 📊 一图流程图

```
你的Google Drive
    ↓
模型路径: /MyDrive/gis-models/codellama-gis-lora/
    ↓
加载模型: load_model_from_drive()
    ↓
推理生成: generator.generate(instruction)
    ↓
评估性能: ModelEvaluator.evaluate_on_dataset()
    ↓
查看结果: print_summary()
    ↓
改进方向: 查看技术文档 → 实施改进
```

---

## 🎯 推荐流程

### 今天（第1天）
- [ ] 运行Notebook单元格8，快速体验
- [ ] 读QUICK_REFERENCE.md，了解基础
- [ ] 评估模型性能，看JSON有效率

**目标**: 5个小时内理解模型的基本用法

### 本周（第2-3天）
- [ ] 读MODEL_LOADING_SUMMARY.md，掌握常见操作
- [ ] 读TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md，理解技术细节
- [ ] 在测试集上完整评估，了解当前性能

**目标**: 理解模型架构，识别改进机会

### 本月（第4-5周）
- [ ] 实现RAG检索增强
- [ ] 实现模板约束系统
- [ ] 重新训练并对比效果

**目标**: 显著提升模型准确性

---

## 📞 快速查询

### 我需要...的代码

| 需要 | 查看 |
|------|------|
| 加载模型 | [QUICK_REFERENCE.md](QUICK_REFERENCE.md#加载模型) |
| 推理生成 | [QUICK_REFERENCE.md](QUICK_REFERENCE.md#推理生成) |
| 评估模型 | [QUICK_REFERENCE.md](QUICK_REFERENCE.md#评估模型) |
| 修复JSON | [QUICK_REFERENCE.md](QUICK_REFERENCE.md#常用代码片段) |
| 调整参数 | [QUICK_REFERENCE.md](QUICK_REFERENCE.md#推理生成) |

### 我想了解...

| 想了解 | 查看 |
|-------|------|
| 快速开始 | [QUICK_REFERENCE.md](QUICK_REFERENCE.md) |
| 完整教程 | [MODEL_LOADING_SUMMARY.md](MODEL_LOADING_SUMMARY.md) |
| 技术架构 | [TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md](TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md) |
| 源代码 | `src/inference/` 文件夹 |
| 改进方案 | [TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md](TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md#三改进方案三层架构) |
| 全部内容 | [INDEX.md](INDEX.md) |

---

## ✅ 你现在拥有

- ✅ **模型加载模块** - 一行代码加载
- ✅ **推理函数** - 一行代码生成代码
- ✅ **评估框架** - 完整的性能评估
- ✅ **6份文档** - 从入门到精通
- ✅ **Notebook单元格** - 直接可运行
- ✅ **故障排查** - 解决常见问题
- ✅ **改进方案** - 4阶段实施路线图

---

## 🎉 现在就开始！

**选择你的方式**:

### 🟢 最快 (5分钟)
→ 运行 Notebook单元格8

### 🟡 标准 (20分钟)
→ 读QUICK_REFERENCE.md + 运行代码

### 🔴 深入 (2小时)
→ 读所有文档 + 理解架构

---

**无论你选择哪种方式，祝你使用愉快！** 🚀

有任何问题，查看对应的文档或源代码即可。

**加油！** 💪
