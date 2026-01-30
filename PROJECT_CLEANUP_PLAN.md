# 项目清理计划

## 📊 项目结构概览

### ✅ 核心保留文件

#### 1️⃣ **核心数据** (data/)
```
data/
├── raw/                           ✅ 保留（原始数据源）
│   ├── template/                  ✅ 高质量模板
│   └── test_data_*/               ✅ 测试数据
└── processed/                     
    ├── parsed_workflows_anonymized.jsonl              ✅ 核心（匿名化工作流）
    ├── step_level_instructions_weighted_variants_marked.jsonl  ✅ 核心（Step级指令+权重）
    ├── file_level_instructions_anonymized.jsonl      ⚠️ 待重新生成
    ├── file_id_mapping.json                          ✅ 核心（匿名映射）
    ├── data_summary.json                             ✅ 保留（数据统计）
    └── evaluation/                                   ⚠️ 旧评估结果，可删除
```

#### 2️⃣ **核心代码** (src/, scripts/)
```
src/
├── data_processing/
│   ├── workflow_parser.py         ✅ 核心（JSON解析）
│   ├── instruction_generator.py   ⚠️ 旧版，待更新
│   ├── analyze_data.py            ✅ 保留（数据分析）
│   └── __pycache__/               ❌ 删除
├── training/
│   ├── train_lora.py              ✅ 核心（LoRA训练）
│   ├── prepare_training_data.py   ⚠️ 待更新（层次化）
│   └── Train_GIS_Model_Colab.ipynb ✅ 保留（Colab笔记本）
└── inference/
    └── evaluate_model.py          ✅ 保留

scripts/
├── generate_instructions_weighted.py    ✅ 核心（Step级生成）
├── analyze_multiple_objects.py          ✅ 核心（问题分析）
├── anonymize_data.py                    ✅ 核心（数据匿名化）
├── aggregate_step_to_file_instructions.py  ⚠️ 待创建
└── quick_train.py                       ✅ 保留
```

#### 3️⃣ **核心文档** (docs/)
```
docs/
├── HIERARCHICAL_TRAINING_STRATEGY.md    ✅ 核心（训练策略）
├── DATA_ANONYMIZATION.md                ✅ 核心（数据处理）
├── INDEX.md                             ✅ 核心（文档索引）
├── COLAB_TRAINING_GUIDE.md              ✅ 保留（训练指南）
└── COLAB_MODEL_INFERENCE_GUIDE.md       ✅ 保留（推理指南）
```

#### 4️⃣ **训练模型** (model/)
```
model/
└── codellama-gis-lora/
    ├── adapter_config.json        ✅ 保留
    ├── adapter_model.safetensors  ✅ 保留
    ├── training_info.json         ✅ 保留
    └── checkpoint-*/              ⚠️ 中间检查点，可删除
```

---

## ❌ 待删除文件

### 🗑️ 非核心/重复/过时文件

#### 1. **处理后数据中的旧版本**
```bash
data/processed/
├── file_level_instructions_weighted.jsonl              ❌ 旧版（有"multiple objects"问题）
├── file_level_instructions_weighted_variants_marked.jsonl  ❌ 旧版
├── step_level_instructions_weighted.jsonl              ❌ 旧版（无variants标记）
├── temp_other_input.jsonl                              ❌ 临时文件
├── sample_workflow.json                                ❌ 示例文件
├── empty_steps_analysis.json                           ❌ 旧分析
└── evaluation/                                         ❌ 旧评估结果
```

#### 2. **文档中的过时/重复内容**
```bash
docs/
├── COLAB_CUDA_FIX.md                    ❌ 临时问题修复
├── COLAB_DRIVE_CRASH_FIX.md             ❌ 临时问题修复
├── DRIVE_CRASH_DIAGRAM.md               ❌ 临时问题图示
├── FIX_MODEL_LOADING_ERROR.md           ❌ 临时问题修复
├── COMPLETION_SUMMARY.md                ❌ 阶段性总结（已过时）
├── corrected_workflow_evaluation.md     ❌ 旧评估报告
├── INSTRUCTION_GENERATION_ALTERNATIVES.md  ❌ 旧方案对比
├── INSTRUCTION_GENERATION_EVOLUTION.md   ❌ 历史演进（已归档）
├── INSTRUCTION_METHODS_COMPARISON.md     ❌ 方法对比（已决策）
├── MODEL_LOADING_SUMMARY.md             ❌ 问题修复总结
├── PROJECT_ROADMAP.md                   ❌ 旧路线图
├── RULE_METHODS_OUTPUT_COMPARISON.md    ❌ 输出对比
├── RULE_TO_WEIGHT_DECISION_PROCESS.md   ❌ 决策过程
├── RULE_TO_WEIGHT_EVOLUTION.md          ❌ 演进历史
├── TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md ❌ 技术总结（已过时）
├── TRAINING_APPROACH_COMPARISON.md      ❌ 训练方法对比
├── TRAINING_GUIDE.md                    ❌ 旧训练指南
├── WEIGHTS_IMPLEMENTATION_GUIDE.md      ❌ 实施指南（已完成）
├── WEIGHTS_IN_COLAB_TRAINING.md         ❌ Colab训练说明
├── GOOGLE_DRIVE_MODEL_GUIDE.md          ❌ Drive使用说明
├── QUICK_MODEL_LOADING_GUIDE.md         ❌ 快速加载指南
├── QUICK_REFERENCE.md                   ❌ 快速参考
└── QUICK_START_NO_API.md                ❌ 无API快速开始
```

#### 3. **Python缓存和临时文件**
```bash
**/__pycache__/                          ❌ 所有Python缓存
**/*.pyc                                 ❌ 编译文件
```

#### 4. **根目录临时文件**
```bash
analyze_parser_stats.py                  ❌ 临时分析脚本
diagnose_colab.py                        ❌ 临时诊断脚本
diagnose_lora.py                         ❌ 临时诊断脚本
update_notebook.py                       ❌ 临时更新脚本
load_model_local.py                      ❌ 临时测试脚本
NOTEBOOK_REVIEW.md                       ❌ 笔记本评审
```

#### 5. **训练检查点**
```bash
model/codellama-gis-lora/
├── checkpoint-1200/                     ❌ 中间检查点
└── checkpoint-1365/                     ❌ 中间检查点
```

---

## 📋 清理执行计划

### 阶段1：备份重要数据（安全第一）
```bash
# 创建备份
mkdir backup_20260126
cp data/processed/parsed_workflows_anonymized.jsonl backup_20260126/
cp data/processed/step_level_instructions_weighted_variants_marked.jsonl backup_20260126/
cp data/processed/file_id_mapping.json backup_20260126/
```

### 阶段2：删除非核心文件

#### 2.1 删除data/processed中的旧版本
```bash
rm data/processed/file_level_instructions_weighted.jsonl
rm data/processed/file_level_instructions_weighted_variants_marked.jsonl
rm data/processed/step_level_instructions_weighted.jsonl
rm data/processed/temp_other_input.jsonl
rm data/processed/sample_workflow.json
rm data/processed/empty_steps_analysis.json
rm -r data/processed/evaluation
```

#### 2.2 删除过时文档
```bash
cd docs
rm COLAB_CUDA_FIX.md COLAB_DRIVE_CRASH_FIX.md DRIVE_CRASH_DIAGRAM.md
rm FIX_MODEL_LOADING_ERROR.md COMPLETION_SUMMARY.md
rm corrected_workflow_evaluation.md
rm INSTRUCTION_GENERATION_ALTERNATIVES.md INSTRUCTION_GENERATION_EVOLUTION.md
rm INSTRUCTION_METHODS_COMPARISON.md MODEL_LOADING_SUMMARY.md
rm PROJECT_ROADMAP.md RULE_METHODS_OUTPUT_COMPARISON.md
rm RULE_TO_WEIGHT_DECISION_PROCESS.md RULE_TO_WEIGHT_EVOLUTION.md
rm TECHNICAL_SUMMARY_AND_IMPROVEMENTS.md TRAINING_APPROACH_COMPARISON.md
rm TRAINING_GUIDE.md WEIGHTS_IMPLEMENTATION_GUIDE.md
rm WEIGHTS_IN_COLAB_TRAINING.md GOOGLE_DRIVE_MODEL_GUIDE.md
rm QUICK_MODEL_LOADING_GUIDE.md QUICK_REFERENCE.md QUICK_START_NO_API.md
```

#### 2.3 删除根目录临时文件
```bash
rm analyze_parser_stats.py
rm diagnose_colab.py
rm diagnose_lora.py
rm update_notebook.py
rm load_model_local.py
rm NOTEBOOK_REVIEW.md
```

#### 2.4 删除Python缓存
```bash
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
```

#### 2.5 删除中间检查点
```bash
rm -rf model/codellama-gis-lora/checkpoint-1200
rm -rf model/codellama-gis-lora/checkpoint-1365
```

### 阶段3：验证核心文件完整性
```bash
# 检查核心数据
ls -lh data/processed/parsed_workflows_anonymized.jsonl
ls -lh data/processed/step_level_instructions_weighted_variants_marked.jsonl
ls -lh data/processed/file_id_mapping.json

# 检查核心代码
ls src/data_processing/workflow_parser.py
ls scripts/generate_instructions_weighted.py
ls scripts/analyze_multiple_objects.py
ls src/training/train_lora.py

# 检查核心文档
ls docs/HIERARCHICAL_TRAINING_STRATEGY.md
ls docs/DATA_ANONYMIZATION.md
ls docs/INDEX.md

# 检查模型
ls model/codellama-gis-lora/adapter_model.safetensors
```

---

## 📊 清理后的项目结构

```
gis-code-ai/
├── data/
│   ├── raw/                                  ✅ 原始数据
│   └── processed/
│       ├── parsed_workflows_anonymized.jsonl
│       ├── step_level_instructions_weighted_variants_marked.jsonl
│       ├── file_level_instructions_anonymized.jsonl  (旧版)
│       ├── file_id_mapping.json
│       └── data_summary.json
├── src/
│   ├── data_processing/
│   │   ├── workflow_parser.py
│   │   ├── instruction_generator.py
│   │   └── analyze_data.py
│   ├── training/
│   │   ├── train_lora.py
│   │   ├── prepare_training_data.py
│   │   └── Train_GIS_Model_Colab.ipynb
│   └── inference/
│       └── evaluate_model.py
├── scripts/
│   ├── generate_instructions_weighted.py
│   ├── analyze_multiple_objects.py
│   ├── anonymize_data.py
│   └── quick_train.py
├── model/
│   └── codellama-gis-lora/
│       ├── adapter_config.json
│       ├── adapter_model.safetensors
│       └── training_info.json
├── docs/
│   ├── HIERARCHICAL_TRAINING_STRATEGY.md
│   ├── DATA_ANONYMIZATION.md
│   ├── INDEX.md
│   ├── COLAB_TRAINING_GUIDE.md
│   └── COLAB_MODEL_INFERENCE_GUIDE.md
├── configs/
│   └── training_config.yaml
├── README.md
└── requirements.txt
```

---

## ✅ 清理后的好处

1. **空间节省**：删除~50个过时文档，节约数MB空间
2. **代码清晰**：只保留核心代码，减少混淆
3. **版本明确**：删除旧版数据文件，避免误用
4. **文档精简**：只保留当前方案相关文档

---

## 🎯 下一步行动

### 立即任务
1. ✅ 执行备份
2. ✅ 执行删除命令
3. ✅ 验证核心文件完整性

### 后续任务
1. ⚠️ 创建 `scripts/aggregate_step_to_file_instructions.py`
2. ⚠️ 更新 `src/training/prepare_training_data.py`（层次化）
3. ⚠️ 重新生成 `file_level_instructions_aggregated.jsonl`
4. ⚠️ 构建层次化训练数据
5. ⚠️ 使用新数据重新训练模型

---

## 📝 清理日志

**日期**: 2026-01-26  
**执行人**: AI Assistant  
**清理文件数**: ~60个  
**节省空间**: 待确认  
**核心文件保留**: 100%  
