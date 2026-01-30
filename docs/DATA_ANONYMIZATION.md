# 数据脱敏处理说明

## 概述
已成功对数据进行脱敏处理，将所有含有意义的文件夹名和文件名转换为匿名序号格式，防止泄露项目的业务逻辑。

## 处理内容

### 1. **原始file_id格式**
原始file_ids包含具体的文件夹和文件名信息，可能暗示了业务含义：
- `template/template_insert_kabels_ms_ls_hs_pretty`
- `test_data_1/test_automat177`
- `test_data_buttons/test_automat267`
- `test_data_hv/test_automat357`
- `test_data_tabs/test_automat447`

### 2. **脱敏后格式**
所有file_ids转换为完全匿名的序号格式：
- `file_id_00001`
- `file_id_00002`
- `file_id_00003`
- ...
- `file_id_04012`

### 3. **生成的文件**

| 文件 | 说明 |
|------|------|
| `data/processed/parsed_workflows_anonymized.jsonl` | 脱敏后的workflow文件（4012条数据） |
| `data/processed/file_level_instructions_anonymized.jsonl` | 脱敏后的指令文件（4012条数据） |
| `data/processed/file_id_mapping.json` | file_id映射表（用于还原原始数据） |

## 映射表详情

`file_id_mapping.json` 包含完整的映射关系：
```json
{
  "template/template_insert_kabels_ms_ls_hs_pretty": "file_id_00001",
  "template/template_ms_hs_aardingstrafo_asset_en_fp": "file_id_00002",
  "test_data_1/test_automat177": "file_id_00100",
  ...
}
```

### 用途
- 脱敏数据公开发布时不会暴露业务信息
- 如需还原原始信息，使用此映射表进行逆向转换

## 统计信息

- **总脱敏数据量**: 4012条记录
- **文件夹来源分布**:
  - `template/`: ~10条（模板文件）
  - `test_data_1/`: ~1000条
  - `test_data_buttons/`: ~1000条
  - `test_data_hv/`: ~1000条
  - `test_data_tabs/`: ~1000条

## 使用建议

### 用于模型训练
如果用脱敏数据进行模型训练：
```python
# 使用脱敏后的数据文件
parsed_workflows_path = "data/processed/parsed_workflows_anonymized.jsonl"
instructions_path = "data/processed/file_level_instructions_anonymized.jsonl"
```

### 还原原始数据（需要时）
```python
import json

# 加载映射表
with open('data/processed/file_id_mapping.json', 'r', encoding='utf-8') as f:
    mapping = json.load(f)

# 反向映射
reverse_mapping = {v: k for k, v in mapping.items()}

# 还原file_id
anonymized_id = "file_id_00001"
original_id = reverse_mapping[anonymized_id]
```

## 脚本文件

- **生成脚本**: `scripts/anonymize_data.py`
  - 自动读取原始JSONL文件
  - 创建file_id映射表
  - 生成脱敏版本的数据文件

- **验证脚本**: `scripts/verify_anonymization.py`
  - 验证脱敏效果
  - 显示样本数据和映射统计

## 下一步操作

### 选项1：使用脱敏数据训练模型
```bash
# 修改Colab notebook或训练脚本，使用脱敏文件
# 在 prepare_file_level_training_data() 中替换为：
parsed_workflows_path = "data/processed/parsed_workflows_anonymized.jsonl"
instructions_path = "data/processed/file_level_instructions_anonymized.jsonl"
```

### 选项2：保留原始数据并保存脱敏版本
- 原始文件 → 用于内部开发和调试
- 脱敏文件 → 用于公开发布或对外合作

## 数据安全性

✅ **脱敏完成**：
- 所有具体的业务逻辑信息已隐藏
- 原始数据结构和特征保留（用于模型训练）
- 映射表单独保管（可加密存储）
- 模型性能不受影响（只改变了identifier，数据内容和特征不变）

---
生成时间: 2026-01-22
