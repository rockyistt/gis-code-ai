# 数据目录说明

## 📁 目录结构

### `data/raw/`
存放**原始 GIS 测试 JSON 文件**。

- **格式**：扁平化的 JSON 文件，包含测试步骤序列
- **来源**：从 GIS 应用（如 NRG Beheerkaart）导出的测试工作流
- **注意**：`template/` 文件夹中的 JSON 文件质量最高，处理时会特别标注

示例文件结构：
```json
{
  "testenvs0": ["TST"],
  "testapps0": ["NRG Beheerkaart Elektra MS"],
  "teststeps0": [7],
  "testdbs0_0": ":elektra",
  "testobjs0_0": "E MS Kabel",
  "testmodules0_0": "Editor(s)",
  "testmethodes0_0": "Open Object",
  ...
}
```

### `data/processed/`
存放**处理后的结构化数据**，用于后续的 RAG 检索和模型训练。

处理后的文件：

1. **`parsed_workflows.jsonl`** - 结构化的工作流
   - 将扁平化 JSON 转换为层次化结构
   - 标注高质量数据（来自 template 文件夹）
   - 每行一个完整的 workflow

2. **`file_level_instructions_openai.jsonl`** - 文件级指令（OpenAI 生成）
   - 描述整个工作流的目标（英文）
   - 用于 RAG 检索：用户输入 → 检索相似工作流

3. **`file_level_instructions_qianwen.jsonl`** - 文件级指令（通义千问生成）
   - 同上，用于对比不同模型效果

4. **`step_level_instructions_openai.jsonl`** - 步骤级指令（OpenAI 生成）
   - 描述每个步骤的具体操作（英文）
   - 用于模型训练：指令 → 代码对

5. **`step_level_instructions_qianwen.jsonl`** - 步骤级指令（通义千问生成）
   - 同上，用于对比

## 🔄 数据处理流程

```
原始数据 (raw/)
    ↓
解析器 (workflow_parser.py)
    ↓
结构化数据 (parsed_workflows.jsonl)
    ↓
指令生成器 (instruction_generator.py)
    ↓  ↓
OpenAI  Qianwen
    ↓  ↓
file_level + step_level 指令
```

## 🚀 运行数据处理

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置 API keys
cp configs/example_config.yaml configs/local_config.yaml
# 编辑 local_config.yaml，填入你的 API keys

# 3. 设置环境变量（或在代码中传入）
export OPENAI_API_KEY="sk-..."
export DASHSCOPE_API_KEY="sk-..."

# 4. 运行完整流程
python src/data_processing/run_pipeline.py

# 5. 测试（处理前 2 个文件）
python src/data_processing/run_pipeline.py --max-workflows 2
```

## ⚠️ 注意事项

- **API 成本**：OpenAI GPT-4 和通义千问都会产生费用，建议先用 `--max-workflows` 测试
- **大文件**：请勿将大数据集直接提交到 Git，使用 `.gitignore` 已忽略 `raw/` 目录
- **数据质量**：优先使用 `template/` 文件夹中的高质量数据进行模型训练
