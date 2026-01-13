# 模型训练指南

## 📋 概述

本指南介绍如何使用准备好的指令数据训练GIS代码生成模型。

## 🎯 训练流程

### 方式1：快速开始（推荐）⚡

使用快速训练脚本，自动完成所有步骤：

```bash
# 测试模式（快速验证流程，小数据集）
python scripts/quick_train.py --test

# 完整训练
python scripts/quick_train.py --full
```

### 方式2：分步执行 📝

#### 步骤1：准备训练数据

```bash
python src/training/prepare_training_data.py \
  --instructions data/processed/step_level_instructions_weighted_variants_marked.jsonl \
  --workflows data/processed/parsed_workflows.jsonl \
  --output data/training/training_data.json \
  --split-ratio 0.9
```

**参数说明：**
- `--instructions`: 指令文件路径
- `--workflows`: 原始工作流文件（包含JSON代码）
- `--output`: 输出文件路径
- `--split-ratio`: 训练/验证集划分比例（默认0.9）
- `--max-samples`: 限制样本数量（用于测试）
- `--keep-markers`: 保留权重标记（默认移除）

**输出文件：**
- `data/training/training_data_train.json` - 训练集
- `data/training/training_data_val.json` - 验证集
- `data/training/training_data_stats.json` - 统计信息

#### 步骤2：训练模型

```bash
python src/training/train_lora.py \
  --model-name Qwen/Qwen2.5-Coder-7B-Instruct \
  --train-file data/training/training_data_train.json \
  --val-file data/training/training_data_val.json \
  --output-dir models/qwen-gis-lora \
  --num-epochs 3 \
  --batch-size 4 \
  --learning-rate 2e-4
```

**关键参数：**
- `--model-name`: 基座模型名称
- `--num-epochs`: 训练轮数
- `--batch-size`: 批次大小
- `--gradient-accumulation-steps`: 梯度累积步数
- `--learning-rate`: 学习率
- `--lora-r`: LoRA秩（默认64）
- `--use-4bit`: 使用4-bit量化（节省显存）

## 💻 硬件要求

### 最低配置
- **GPU**: NVIDIA GPU with 16GB VRAM（如RTX 3090, A4000）
- **RAM**: 32GB
- **存储**: 50GB

### 推荐配置
- **GPU**: NVIDIA GPU with 24GB+ VRAM（如RTX 4090, A5000, A100）
- **RAM**: 64GB
- **存储**: 100GB

### 云端训练（推荐）☁️
- **Google Colab Pro**: T4/A100 GPU
- **Kaggle**: P100/T4 GPU（免费）
- **AWS/Azure/阿里云**: 按需租用GPU实例

## 🔧 配置文件

训练配置保存在 `configs/training_config.yaml`：

```yaml
# 模型配置
model_name_or_path: "Qwen/Qwen2.5-Coder-7B-Instruct"
use_4bit: true

# LoRA配置
lora_r: 64
lora_alpha: 16
lora_dropout: 0.05

# 训练配置
num_train_epochs: 3
per_device_train_batch_size: 4
learning_rate: 2.0e-4
```

## 📊 训练数据格式

训练数据采用Alpaca格式：

```json
{
  "instruction": "Create a new MS cable object at coordinates (186355533, 439556907)",
  "input": "Application: PowerGrid | Step 1 of 5 | Database: ND",
  "output": "{\n  \"module\": \"Create\",\n  \"method\": \"Create\",\n  ...JSON代码...\n}"
}
```

## 📈 监控训练

### 训练日志

训练过程中会输出：
- Loss（损失）
- Learning rate（学习率）
- Steps/second（训练速度）

### TensorBoard（可选）

```bash
# 修改train_lora.py中的report_to="tensorboard"
tensorboard --logdir models/qwen-gis-lora/runs
```

### Weights & Biases（可选）

```bash
# 安装wandb
pip install wandb

# 修改train_lora.py中的report_to="wandb"
wandb login
```

## 🎯 训练技巧

### 1. 快速验证流程

先用小数据集验证训练流程是否正常：

```bash
python src/training/prepare_training_data.py --max-samples 1000
python src/training/train_lora.py --num-epochs 1 --save-steps 50
```

### 2. 调整batch size

如果显存不足，可以：
- 减小 `--batch-size`（如改为2）
- 增加 `--gradient-accumulation-steps`（如改为8）
- 保持有效batch size = batch_size × gradient_accumulation_steps

### 3. 学习率调优

建议尝试的学习率范围：
- 1e-4（保守）
- 2e-4（默认）
- 5e-4（激进）

### 4. LoRA参数调优

- **lora_r**: 64（默认）或 128（更强表达能力，但更慢）
- **lora_alpha**: 通常设为 lora_r 的 1/4 或 1/2

## 🚀 训练后步骤

### 1. 模型评估

```bash
python examples/evaluate_model.py \
  --model-path models/qwen-gis-lora \
  --test-file data/training/training_data_val.json
```

### 2. 推理测试

```bash
python examples/demo_inference.py \
  --model-path models/qwen-gis-lora \
  --instruction "Create a new MS cable object"
```

### 3. 部署模型

训练好的模型可以：
- 集成到Web界面（Gradio/Streamlit）
- 部署为API服务（FastAPI）
- 打包为离线工具

## ❓ 常见问题

### Q1: CUDA out of memory
**解决方案：**
- 使用 `--use-4bit` 量化
- 减小 `--batch-size`
- 减小 `--max-length`
- 使用更小的模型（如Qwen2.5-Coder-3B）

### Q2: 训练太慢
**解决方案：**
- 使用更强的GPU
- 增加 `--batch-size`（如果显存允许）
- 减少 `--save-steps` 和 `--logging-steps`

### Q3: Loss不下降
**检查：**
- 学习率是否合适
- 数据是否有问题
- 是否过拟合（对比train和val loss）

### Q4: 模型生成质量差
**改进方法：**
- 增加训练数据量
- 调整LoRA参数（增大lora_r）
- 训练更多轮次
- 检查数据质量

## 📚 参考资源

- [Qwen2.5-Coder模型卡](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct)
- [LoRA论文](https://arxiv.org/abs/2106.09685)
- [Hugging Face Transformers文档](https://huggingface.co/docs/transformers)
- [PEFT库文档](https://huggingface.co/docs/peft)

## 💬 需要帮助？

遇到问题可以：
1. 查看日志文件
2. 检查GitHub Issues
3. 查阅相关文档
