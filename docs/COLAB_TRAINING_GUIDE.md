# Google Colab 训练指南

## 🚀 快速开始

### 1. 打开Colab Notebook

点击下面的链接在Google Colab中打开训练脚本：

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/YOUR_USERNAME/gis-code-ai/blob/main/notebooks/Train_GIS_Model_Colab.ipynb)

### 2. 设置GPU运行时

在Colab中：
1. 点击 `Runtime` → `Change runtime type`
2. 选择 `Hardware accelerator` → `GPU`
3. GPU类型选择：
   - **T4**（免费）- 约4-6小时训练时间
   - **A100**（Colab Pro）- 约1-2小时训练时间

### 3. 准备数据

有三种方式上传数据：

#### 方式A：从GitHub克隆（推荐）
```bash
# 在Colab中运行
!git clone https://github.com/YOUR_USERNAME/gis-code-ai.git
%cd gis-code-ai
```

#### 方式B：从Google Drive
```python
# 先将数据上传到Google Drive
from google.colab import drive
drive.mount('/content/drive')

# 复制数据
!cp /content/drive/MyDrive/gis-data/*.jsonl data/processed/
```

#### 方式C：手动上传
```python
from google.colab import files
uploaded = files.upload()  # 选择文件上传
```

### 4. 运行Notebook

按顺序执行Notebook中的所有单元格：

1. ✅ 检查GPU
2. ✅ 安装依赖
3. ✅ 挂载Google Drive
4. ✅ 上传/准备数据
5. ✅ 准备训练数据
6. ✅ 训练模型（这一步最耗时）
7. ✅ 测试模型
8. ✅ 保存到Google Drive

## 📊 训练配置

### 默认配置（适用于T4 GPU）

```python
NUM_EPOCHS = 3
BATCH_SIZE = 4
GRADIENT_ACCUMULATION = 4
LEARNING_RATE = 2e-4
LORA_R = 64
```

**有效batch size** = BATCH_SIZE × GRADIENT_ACCUMULATION = 16

### A100 GPU配置（更快）

```python
NUM_EPOCHS = 3
BATCH_SIZE = 8
GRADIENT_ACCUMULATION = 2
LEARNING_RATE = 2e-4
```

### 快速测试配置

```python
NUM_EPOCHS = 1
BATCH_SIZE = 2
GRADIENT_ACCUMULATION = 2
# 在准备数据时添加：max_samples=1000
```

## 💾 保存模型

模型会自动保存到Google Drive：
```
/content/drive/MyDrive/gis-models/qwen-gis-lora/
```

包含：
- `adapter_config.json` - LoRA配置
- `adapter_model.bin` - LoRA权重
- `training_info.json` - 训练信息
- `tokenizer_config.json`, `special_tokens_map.json` - Tokenizer配置

## 📥 下载模型

### 方法1：直接从Google Drive下载

1. 训练完成后，访问Google Drive
2. 找到 `MyDrive/gis-models/qwen-gis-lora/`
3. 右键下载整个文件夹

### 方法2：在Colab中打包下载

```python
# 打包模型
!cd /content/drive/MyDrive/gis-models && zip -r qwen-gis-lora.zip qwen-gis-lora/

# 下载
from google.colab import files
files.download('/content/drive/MyDrive/gis-models/qwen-gis-lora.zip')
```

## 🔧 常见问题

### Q1: CUDA Out of Memory

**症状**：训练时报错 `CUDA out of memory`

**解决方案**：
```python
# 方案1：减小batch size
BATCH_SIZE = 2
GRADIENT_ACCUMULATION = 8

# 方案2：减小max_length
MAX_LENGTH = 1024

# 方案3：减小LoRA秩
LORA_R = 32
```

### Q2: 训练中断/断开连接

**预防措施**：
- 使用Colab Pro（连接更稳定）
- 定期保存checkpoint（已自动配置 `save_steps=500`）
- 保持浏览器标签页活跃

**恢复训练**：
```python
# 从checkpoint恢复
trainer = Trainer(...)
trainer.train(resume_from_checkpoint=True)
```

### Q3: 数据文件未找到

**检查清单**：
```python
import os
print(os.listdir('data/processed/'))  # 查看文件
```

确保存在：
- `step_level_instructions_weighted_variants_marked.jsonl`
- `parsed_workflows.jsonl`

### Q4: 训练速度慢

**优化建议**：
- 确认使用GPU：`!nvidia-smi`
- 使用A100 GPU（Colab Pro）
- 增大batch size（如果显存允许）
- 减少logging频率：`logging_steps=50`

### Q5: 模型效果不好

**改进方法**：
1. 增加训练轮数：`NUM_EPOCHS = 5`
2. 使用更多数据（去掉max_samples限制）
3. 调整学习率：`LEARNING_RATE = 1e-4` 或 `5e-4`
4. 增大LoRA秩：`LORA_R = 128`

## 📈 监控训练

### 查看训练日志

训练过程中会显示：
```
Step 10/1000 | Loss: 2.543 | LR: 0.0002 | Speed: 2.3 steps/s
Step 20/1000 | Loss: 2.134 | LR: 0.0002 | Speed: 2.4 steps/s
...
```

### 理解Loss

- **初始Loss**: 通常在2-4之间
- **训练中**: 应该逐渐下降
- **收敛**: 最终在0.5-1.5之间
- **过拟合**: 如果train loss很低但val loss很高

### 使用TensorBoard（可选）

```python
# 在training_args中修改
report_to="tensorboard"

# 在另一个cell中启动
%load_ext tensorboard
%tensorboard --logdir /content/drive/MyDrive/gis-models/qwen-gis-lora/logs
```

## 🎯 训练完成后

### 1. 测试模型

在Notebook的测试单元格中运行：
```python
test_instruction = "Create a new MS cable object"
# 查看生成结果
```

### 2. 本地使用

下载模型后，在本地使用：
```python
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

# 加载基座模型
base_model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen2.5-Coder-7B-Instruct",
    device_map="auto",
    torch_dtype=torch.float16
)

# 加载LoRA adapter
model = PeftModel.from_pretrained(base_model, "path/to/qwen-gis-lora")
tokenizer = AutoTokenizer.from_pretrained("path/to/qwen-gis-lora")

# 推理
model.eval()
# ...
```

### 3. 评估模型

```bash
# 在本地运行
python examples/evaluate_model.py \
  --model-path models/qwen-gis-lora \
  --test-file data/training/training_data_val.json
```

## 💰 成本估算

### Colab免费版
- GPU: T4（16GB）
- 限制: 12小时/会话
- 成本: **免费**
- 训练时间: 4-6小时
- 适用: 测试和小规模训练

### Colab Pro ($9.99/月)
- GPU: T4/A100
- 限制: 24小时/会话
- 训练时间: 1-2小时（A100）
- 适用: 完整训练

### Colab Pro+ ($49.99/月)
- GPU: A100（40GB）
- 限制: 更长会话时间
- 适用: 大规模训练

## 📚 推荐阅读

- [Google Colab使用指南](https://colab.research.google.com/notebooks/intro.ipynb)
- [LoRA原理解析](https://arxiv.org/abs/2106.09685)
- [Qwen2.5-Coder模型文档](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct)

## 🆘 获取帮助

如果遇到问题：
1. 查看本指南的常见问题部分
2. 检查Colab的输出日志
3. 在GitHub上提Issue
4. 查阅Transformers和PEFT文档

---

**🎉 祝训练顺利！**
