"""
脱敏脚本：将file_id转换为匿名序号
将原始的file_id映射为file_id_001, file_id_002等格式
"""

import json
import os
from pathlib import Path
from collections import OrderedDict

def anonymize_file_ids():
    """
    脱敏数据中的file_ids，将具体的文件夹和文件名替换为序号
    """
    data_dir = Path("data/processed")
    
    # 输入文件
    parsed_workflows_path = data_dir / "parsed_workflows.jsonl"
    file_level_instructions_path = data_dir / "file_level_instructions_weighted_variants_marked.jsonl"
    
    # 输出文件
    anonymized_workflows_path = data_dir / "parsed_workflows_anonymized.jsonl"
    anonymized_instructions_path = data_dir / "file_level_instructions_anonymized.jsonl"
    anonymized_mapping_path = data_dir / "file_id_mapping.json"
    
    # 第1步：读取parsed_workflows.jsonl并收集所有唯一的file_ids
    print("Step 1: 收集所有唯一的file_ids...")
    file_ids_set = OrderedDict()  # 保持顺序
    
    if not parsed_workflows_path.exists():
        print(f"ERROR: {parsed_workflows_path} not found!")
        return
    
    with open(parsed_workflows_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            try:
                workflow = json.loads(line.strip())
                original_file_id = workflow.get("file_id", "")
                if original_file_id and original_file_id not in file_ids_set:
                    file_ids_set[original_file_id] = None
            except json.JSONDecodeError as e:
                print(f"Warning: 第 {i} 行无法解析: {e}")
    
    print(f"找到 {len(file_ids_set)} 个唯一的file_ids")
    
    # 第2步：创建file_id映射 (原始file_id -> 序号file_id)
    print("\nStep 2: 创建file_id映射...")
    file_id_mapping = {}
    for idx, original_file_id in enumerate(file_ids_set.keys(), 1):
        anonymized_id = f"file_id_{idx:05d}"  # file_id_00001, file_id_00002 等
        file_id_mapping[original_file_id] = anonymized_id
        if idx <= 10 or idx % 100 == 0:  # 打印前10个和每100个
            print(f"  {original_file_id:50s} -> {anonymized_id}")
    
    # 第3步：脱敏parsed_workflows.jsonl
    print(f"\nStep 3: 脱敏 {parsed_workflows_path}...")
    with open(parsed_workflows_path, 'r', encoding='utf-8') as fin, \
         open(anonymized_workflows_path, 'w', encoding='utf-8') as fout:
        for i, line in enumerate(fin, 1):
            try:
                workflow = json.loads(line.strip())
                original_file_id = workflow.get("file_id", "")
                workflow["file_id"] = file_id_mapping.get(original_file_id, original_file_id)
                fout.write(json.dumps(workflow, ensure_ascii=False) + "\n")
            except json.JSONDecodeError as e:
                print(f"Warning: 第 {i} 行无法解析: {e}")
    
    print(f"✓ 已脱敏 {i} 行到 {anonymized_workflows_path}")
    
    # 第4步：脱敏file_level_instructions_weighted_variants_marked.jsonl（如果存在）
    print(f"\nStep 4: 脱敏 {file_level_instructions_path}...")
    if file_level_instructions_path.exists():
        instruction_count = 0
        with open(file_level_instructions_path, 'r', encoding='utf-8') as fin, \
             open(anonymized_instructions_path, 'w', encoding='utf-8') as fout:
            for i, line in enumerate(fin, 1):
                try:
                    instruction = json.loads(line.strip())
                    original_file_id = instruction.get("file_id", "")
                    
                    # 尝试直接映射，如果失败则尝试添加文件夹前缀
                    if original_file_id in file_id_mapping:
                        instruction["file_id"] = file_id_mapping[original_file_id]
                    else:
                        # 尝试寻找匹配的带有文件夹前缀的key
                        found = False
                        for full_file_id, anonymized_id in file_id_mapping.items():
                            if full_file_id.endswith("/" + original_file_id) or full_file_id.split('/')[-1] == original_file_id:
                                instruction["file_id"] = anonymized_id
                                found = True
                                break
                        if not found:
                            # 如果还是没找到，保持原值
                            instruction["file_id"] = original_file_id
                    
                    fout.write(json.dumps(instruction, ensure_ascii=False) + "\n")
                    instruction_count += 1
                except json.JSONDecodeError as e:
                    print(f"Warning: 第 {i} 行无法解析: {e}")
        
        print(f"✓ 已脱敏 {instruction_count} 行到 {anonymized_instructions_path}")
    else:
        print(f"! {file_level_instructions_path} 不存在，跳过")
    
    # 第5步：保存映射表
    print(f"\nStep 5: 保存映射表...")
    with open(anonymized_mapping_path, 'w', encoding='utf-8') as f:
        json.dump(file_id_mapping, f, ensure_ascii=False, indent=2)
    print(f"✓ 映射表已保存到 {anonymized_mapping_path}")
    
    # 统计信息
    print("\n" + "="*60)
    print("脱敏完成统计：")
    print(f"  原始file_ids数量: {len(file_id_mapping)}")
    print(f"  脱敏后的workflow文件: {anonymized_workflows_path}")
    print(f"  脱敏后的instruction文件: {anonymized_instructions_path}")
    print(f"  映射表: {anonymized_mapping_path}")
    print("="*60)
    
    return file_id_mapping

if __name__ == "__main__":
    anonymize_file_ids()
