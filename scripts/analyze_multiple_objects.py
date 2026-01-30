"""
分析"multiple objects"指令的问题并提供改进建议
"""
import json
from collections import Counter

print("🔍 分析 'multiple objects' 问题")
print("=" * 80)

# 1. 统计"multiple objects"出现频率
print("\n1️⃣ 统计指令模糊度")
print("-" * 80)

multiple_objects_count = 0
specific_objects_count = 0
total_count = 0

multiple_examples = []

with open('data/processed/file_level_instructions_anonymized.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        data = json.loads(line)
        instruction = data.get('instruction', '')
        total_count += 1
        
        if 'multiple objects' in instruction:
            multiple_objects_count += 1
            if len(multiple_examples) < 5:
                multiple_examples.append({
                    'file_id': data.get('file_id'),
                    'instruction': instruction,
                    'objects': data.get('objects', []),
                    'total_steps': data.get('total_steps', 0)
                })
        else:
            specific_objects_count += 1

print(f"总指令数: {total_count}")
print(f"模糊指令 ('multiple objects'): {multiple_objects_count} ({multiple_objects_count/total_count:.1%})")
print(f"具体指令 (列出对象名): {specific_objects_count} ({specific_objects_count/total_count:.1%})")

# 2. 分析"multiple objects"案例的实际内容
print("\n\n2️⃣ 'multiple objects' 案例详细分析")
print("-" * 80)

# 读取mapping和workflows
with open('data/processed/file_id_mapping.json', 'r', encoding='utf-8') as f:
    mapping = json.load(f)
reverse_mapping = {v: k for k, v in mapping.items()}

workflows = {}
with open('data/processed/parsed_workflows.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        wf = json.loads(line)
        workflows[wf['file_id']] = wf

for i, example in enumerate(multiple_examples, 1):
    print(f"\n案例 {i}: {example['file_id']}")
    print(f"当前指令: {example['instruction']}")
    print(f"实际对象列表: {example['objects']}")
    print(f"对象数量: {len(example['objects'])}")
    print(f"总步骤数: {example['total_steps']}")
    
    # 获取原始workflow
    original_id = reverse_mapping.get(example['file_id'])
    if original_id and original_id in workflows:
        wf = workflows[original_id]
        
        # 统计CRUD操作分布
        action_counts = Counter()
        object_actions = {}  # {object_name: [actions]}
        
        for step in wf.get('steps', []):
            obj = step.get('object', '')
            method = step.get('method', '')
            
            if method in ['Create', 'Update', 'Delete']:
                action_counts[method] += 1
                if obj not in object_actions:
                    object_actions[obj] = []
                object_actions[obj].append(method)
        
        print(f"\n  操作统计:")
        for action, count in action_counts.items():
            print(f"    {action}: {count}次")
        
        print(f"\n  每个对象的操作:")
        for obj, actions in sorted(object_actions.items()):
            unique_actions = list(set(actions))
            print(f"    {obj}: {', '.join(unique_actions)}")
        
        # 建议的更好指令
        main_objects = list(object_actions.keys())[:3]  # 取前3个主要对象
        if len(main_objects) > 0:
            actions = example['instruction'].split('**')[1].split('**')[0] if '**' in example['instruction'] else ''
            suggested = f"Workflow: **{actions}** {', '.join(main_objects)} in {wf.get('database', 'elektra')} in {wf.get('test_app', '')}"
            print(f"\n  🎯 建议改进指令:")
            print(f"    {suggested}")

# 3. 提出指令生成规则改进建议
print("\n\n3️⃣ 指令生成规则改进建议")
print("=" * 80)

print("""
❌ 当前问题:
   - 当对象数量 > 3 时，自动使用 "multiple objects"
   - 导致指令过于模糊，无法区分不同workflow

✅ 改进方案:

方案1: 列出前N个主要对象（推荐）
   规则: 始终列出最重要的2-4个对象，即使总数很多
   示例: "create E Stationcomplex, E MS Aardingstrafo FP, E HS Aardingstrafo FP (and 2 more)"
   
方案2: 基于操作频率动态选择
   规则: 列出操作次数最多的3个对象
   示例: "create/update E MS Installatie FP (5 ops), E Stationcomplex (3 ops), E MS Rail FP (2 ops)"
   
方案3: 按对象重要性分层
   规则: 主对象 + 次要对象
   示例: "create E Stationcomplex and related MS/HS infrastructure objects"
   
方案4: 添加对象类别总结
   规则: 识别对象类别（如所有MS相关、所有HS相关）
   示例: "create MS and HS station infrastructure (5 objects)"

🎯 推荐实施: 方案1 + 方案4 结合
   - 优先列出前3个最重要对象
   - 如果还有更多，添加类别总结
   - 示例: "create E Stationcomplex, E MS Aardingstrafo FP, and other MS/HS infrastructure"
""")

# 4. 代码实现建议
print("\n4️⃣ 代码修改建议")
print("=" * 80)

print("""
修改位置: scripts/generate_instructions_weighted.py 
          或 src/data_processing/instruction_generator.py

当前逻辑 (WeightedInstructionGenerator.generate_file_instruction):
```python
# 如果对象数量 > 3, 使用 "multiple objects"
if len(unique_objects) > 3:
    object_str = "multiple objects"
else:
    object_str = ", ".join([f"*{obj}*" for obj in unique_objects[:3]])
```

改进逻辑:
```python
def format_objects_list(objects, max_display=3):
    \"\"\"智能格式化对象列表\"\"\"
    if len(objects) <= max_display:
        # 对象少，全部列出
        return ", ".join([f"*{obj}*" for obj in objects])
    else:
        # 对象多，列出前N个 + 总数提示
        main_objects = ", ".join([f"*{obj}*" for obj in objects[:max_display]])
        remaining = len(objects) - max_display
        
        # 可选: 添加类别识别
        categories = identify_object_categories(objects)
        if categories:
            return f"{main_objects} and {remaining} more {categories} objects"
        else:
            return f"{main_objects} (and {remaining} more objects)"

def identify_object_categories(objects):
    \"\"\"识别对象所属类别\"\"\"
    categories = set()
    for obj in objects:
        if 'MS' in obj:
            categories.add('MS')
        if 'HS' in obj:
            categories.add('HS')
        if 'LS' in obj:
            categories.add('LS')
        if 'Station' in obj or 'Installatie' in obj:
            categories.add('infrastructure')
    
    return '/'.join(sorted(categories)) if categories else None
```

使用示例:
```python
objects = ['E Stationcomplex', 'E MS Aardingstrafo FP', 'E HS Aardingstrafo FP', 
           'E HS Aardingstrafo', 'E MS Aardingstrafo']

# 当前输出: "multiple objects"
# 改进输出: "*E Stationcomplex*, *E MS Aardingstrafo FP*, *E HS Aardingstrafo FP* (and 2 more MS/HS objects)"
```
""")

print("\n" + "=" * 80)
print("✅ 分析完成！建议优先实施方案1，可显著提升指令质量")
print("=" * 80)
