# 快速指南：无API生成指令

## ✅ 已验证可用！

你现在可以**完全不需要任何API**就能生成训练数据了！

## 🚀 一键运行

### 生成所有数据（推荐）

```powershell
# 使用增强规则方法生成全部4012个工作流的指令
python scripts/generate_instructions_rules.py --method enhanced
```

**预计时间**：约5-10秒  
**成本**：完全免费  
**质量**：评分0.643（已验证，质量不错）

### 生成示例

#### 文件级指令示例：
```json
{
  "file_id": "template_insert_kabels_ms_ls_hs_pretty",
  "is_high_quality": true,
  "instruction": "Workflow for NRG Beheerkaart Elektra MS: create E MS Kabel, E HS Kabel, E LS Kabel in elektra",
  "provider": "rule_enhanced",
  "test_app": "NRG Beheerkaart Elektra MS",
  "total_steps": 7
}
```

#### 步骤级指令示例：
```
1. Open E MS Kabel object in elektra dataset
2. Navigate to Object Editor tab
3. Create a new E MS Kabel object with 6 attributes in elektra database
4. Open E HS Kabel object in elektra dataset
5. Create a new E HS Kabel object with 6 attributes in elektra database
```

## 📊 三种方法对比

### 1. enhanced（增强规则 - 推荐⭐）
```powershell
python scripts/generate_instructions_rules.py --method enhanced
```
- **评分**: 0.643（最高）
- **特点**: 包含详细信息（数据库、属性数量等）
- **速度**: 5,201 workflows/秒
- **推荐用于**: 生产环境

### 2. basic（基础规则 - 简洁）
```powershell
python scripts/generate_instructions_rules.py --method basic
```
- **评分**: 0.556
- **特点**: 简洁快速，只包含核心信息
- **速度**: 2,794 workflows/秒
- **推荐用于**: 快速原型

### 3. context（上下文感知 - 友好）
```powershell
python scripts/generate_instructions_rules.py --method context
```
- **评分**: 0.524
- **特点**: 使用友好术语（如"Medium Voltage Cable"）
- **速度**: 4,887 workflows/秒
- **推荐用于**: 面向用户的场景

## 🎯 下一步

### 1. 生成全部数据
```powershell
cd "C:\Luqi's internship\Github\gis-code-ai"
python scripts/generate_instructions_rules.py --method enhanced
```

### 2. 查看结果
```powershell
# 查看生成的文件
ls data\processed\*rule_enhanced*

# 查看前几行
Get-Content data\processed\file_level_instructions_rule_enhanced.jsonl -First 3
```

### 3. 验证数据
```powershell
# 统计生成的指令数量
(Get-Content data\processed\file_level_instructions_rule_enhanced.jsonl | Measure-Object -Line).Lines
(Get-Content data\processed\step_level_instructions_rule_enhanced.jsonl | Measure-Object -Line).Lines
```

应该看到：
- 文件级：4012条
- 步骤级：约40,000条

### 4. 准备训练数据

生成的文件已经是JSONL格式，可以直接用于训练！

格式：
```json
{
  "instruction": "用户指令",
  "input": "上下文（步骤级才有）",
  "output": "对应的JSON代码"
}
```

## 💡 小贴士

### 只想测试？
```powershell
# 只处理前10个工作流
python scripts/generate_instructions_rules.py --method enhanced --max-workflows 10
```

### 想要最高质量？

**混合策略**：
1. 用规则生成全部数据（5秒）
2. 手动标注12个高质量模板（1小时）
3. 用手动标注的作为验证集
4. 用规则生成的作为训练集

```powershell
# 第1步：规则生成
python scripts/generate_instructions_rules.py --method enhanced

# 第2步：手动优化高质量样本（可选）
# 编辑 data/processed/file_level_instructions_rule_enhanced.jsonl
# 找到 "is_high_quality": true 的12条记录
# 手动改进它们的instruction字段
```

### 不同方法混合使用？

生成多个版本进行对比：
```powershell
python scripts/generate_instructions_rules.py --method basic
python scripts/generate_instructions_rules.py --method enhanced
python scripts/generate_instructions_rules.py --method context
```

然后对比输出文件，选择最适合的。

## ❓ 常见问题

### Q: 质量够用吗？
A: 根据评估报告，增强规则方法的综合评分0.643，描述质量0.513，业务逻辑识别0.479。这个质量足够用于初步训练，后续可以迭代优化。

### Q: 比API差多少？
A: Qwen API大约能达到0.7-0.8分，但需要付费且较慢。规则方法免费且极快，性价比更高。

### Q: 能改进规则吗？
A: 可以！编辑 `scripts/generate_instructions_rules.py`，修改模板规则即可。

### Q: 需要安装额外的包吗？
A: 不需要！只用到Python标准库和tqdm（项目已有）。

## 🎉 总结

你现在有了一个**完全免费、极快、质量不错**的指令生成方案！

```
✅ 无需API密钥
✅ 无需GPU
✅ 无需网络
✅ 5-10秒生成全部数据
✅ 质量评分0.643（可用水平）
```

**立即开始**：
```powershell
python scripts/generate_instructions_rules.py --method enhanced
```
