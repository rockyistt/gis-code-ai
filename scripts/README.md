# Scripts 脚本工具集

本目录包含数据处理、指令生成和Colab工具脚本。

## 📁 文件说明

### 指令生成（Qwen API）
- `generate_instructions_rules.py` - 基于规则生成指令
- `generate_instructions_weighted.py` - 加权变体生成

### 训练相关
- `quick_train.py` - 快速训练脚本

### Colab工具 🆕
- **`colab_model_utils.py`** - Google Colab模型保存/加载工具
  - 解决Drive文件同步导致的崩溃问题
  - 提供 `save_model_safely()` 和 `load_model_safely()` 函数
  - 使用方法见：[docs/COLAB_DRIVE_CRASH_FIX.md](../docs/COLAB_DRIVE_CRASH_FIX.md)

---

## 🔧 Colab模型工具使用（重要！）

如果你在Google Colab训练模型，**强烈推荐**使用这个工具避免崩溃：

### 训练后保存
```python
# 在Colab中
!wget https://raw.githubusercontent.com/YOUR_REPO/gis-code-ai/main/scripts/colab_model_utils.py

from colab_model_utils import save_model_safely

local_path, drive_path = save_model_safely(
    trainer=trainer,
    tokenizer=tokenizer,
    output_name="codellama-gis-lora"
)
```

### 新Session加载
```python
from colab_model_utils import load_model_safely

model, tokenizer = load_model_safely(
    lora_model_name="codellama-gis-lora",
    base_model_name="codellama/CodeLlama-7b-Instruct-hf",
    use_local_cache=True  # 关键！避免Drive I/O瓶颈
)
```

详细说明：[docs/COLAB_DRIVE_CRASH_FIX.md](../docs/COLAB_DRIVE_CRASH_FIX.md)

---

## 📋 Qwen指令生成准备工作

### 1. 获取DashScope API密钥

访问 [阿里云DashScope控制台](https://dashscope.console.aliyun.com/) 获取API密钥。

### 2. 设置API密钥

方式1: 环境变量 (推荐)
```bash
# Windows PowerShell
$env:DASHSCOPE_API_KEY="your-api-key-here"

# Linux/Mac
export DASHSCOPE_API_KEY="your-api-key-here"
```

方式2: 命令行参数
```bash
python scripts/generate_instructions_qwen.py --api-key your-api-key-here
```

## 🚀 使用方法

### 基础用法

```bash
# 生成所有指令 (文件级 + 步骤级)
python scripts/generate_instructions_qwen.py
```

### 测试模式

先用少量数据测试，确保一切正常:

```bash
# 只处理前2个工作流 (1个模板 + 1个普通)
python scripts/generate_instructions_qwen.py --test
```

### 只处理高质量模板

如果想先处理template目录的高质量数据:

```bash
python scripts/generate_instructions_qwen.py --templates-only
```

### 高级选项

```bash
# 跳过导航和验证步骤 (减少API调用)
python scripts/generate_instructions_qwen.py --skip-navigation

# 不包含前序步骤上下文 (每个步骤独立)
python scripts/generate_instructions_qwen.py --no-context

# 指定输入输出路径
python scripts/generate_instructions_qwen.py \
    --input data/processed/parsed_workflows.jsonl \
    --output-dir data/processed
```

## 📊 输出文件

生成的文件会保存在 `data/processed/` 目录:

- `file_level_instructions_qwen.jsonl` - 文件级指令 (完整workflow描述)
- `step_level_instructions_qwen.jsonl` - 步骤级指令 (每个步骤的详细描述)

### 文件格式示例

**文件级指令**:
```json
{
  "file_id": "template_insert_kabels_ms_ls_hs_pretty",
  "is_high_quality": true,
  "instruction": "Open editors for MS, HS, and LS cables in electrical network and create cable objects with specific coordinates and properties.",
  "provider": "qianwen",
  "test_app": "NRG Beheerkaart Elektra MS",
  "total_steps": 7
}
```

**步骤级指令**:
```json
{
  "file_id": "template_insert_kabels_ms_ls_hs_pretty",
  "step_index": 2,
  "step_type": "crud",
  "is_high_quality": true,
  "instruction": "Create an MS cable object in elektra database with 3-phase status and coordinates (186355533, 439556907).",
  "provider": "qianwen",
  "module": "Datamodel CRUD",
  "method": "Create"
}
```

## 💰 成本估算

基于Qwen API定价:
- qwen-max: ¥0.12/1000 tokens
- qwen-plus: ¥0.04/1000 tokens (推荐)

估算成本 (按qwen-plus计算):
- 平均每个workflow: ~500 tokens
- 4000个workflows: ~2M tokens
- 估计成本: ¥80

## 📈 处理进度监控

脚本会实时显示:
- ✓ 成功处理的workflow数量
- ✗ 失败的workflow (包含错误信息)
- 总步骤数统计
- 按类型分类的步骤分布

## 🐛 常见问题

### Q: API调用失败怎么办?
A: 检查:
1. API密钥是否正确
2. 网络连接是否正常
3. API配额是否充足

### Q: 处理速度太慢?
A: 可以考虑:
1. 使用 `--skip-navigation` 跳过简单步骤
2. 切换到更快的模型 (如qwen-turbo)
3. 分批处理 (先处理templates)

### Q: 内存不足?
A: 脚本采用流式处理，不会一次性加载所有数据到内存。

## 📝 下一步

生成指令后，可以:
1. 使用生成的指令训练LoRA模型
2. 构建RAG检索系统
3. 评估指令质量

参见主README的后续步骤。
