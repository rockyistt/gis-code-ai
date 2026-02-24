"""
将层次化训练数据分割为训练集和验证集

用法:
    python scripts/split_training_data.py
"""

import json
import random
from pathlib import Path
from typing import List, Dict

# 配置
INPUT_FILE = Path("data/processed/training_data_combined.json")
OUTPUT_DIR = Path("data/processed")
TRAIN_FILE = OUTPUT_DIR / "training_data_train.json"
VAL_FILE = OUTPUT_DIR / "training_data_val.json"
STATS_FILE = OUTPUT_DIR / "split_stats.json"
VAL_RATIO = 0.1  # 10%验证集
RANDOM_SEED = 42

def split_by_file_id(data: List[Dict], val_ratio: float = 0.1) -> tuple:
    """
    按file_id分割数据，确保同一个文件的所有步骤都在同一个集合中
    
    Args:
        data: 训练数据列表
        val_ratio: 验证集比例
    
    Returns:
        (train_data, val_data) 元组
    """
    # 按file_id分组
    file_groups = {}
    for sample in data:
        file_id = sample["metadata"]["file_id"]
        if file_id not in file_groups:
            file_groups[file_id] = []
        file_groups[file_id].append(sample)
    
    # 获取所有file_id并打乱
    file_ids = list(file_groups.keys())
    random.seed(RANDOM_SEED)
    random.shuffle(file_ids)
    
    # 计算验证集大小
    num_val_files = max(1, int(len(file_ids) * val_ratio))
    val_file_ids = set(file_ids[:num_val_files])
    
    # 分割数据
    train_data = []
    val_data = []
    
    for file_id, samples in file_groups.items():
        if file_id in val_file_ids:
            val_data.extend(samples)
        else:
            train_data.extend(samples)
    
    return train_data, val_data


def main():
    print("=" * 60)
    print("分割层次化训练数据")
    print("=" * 60)
    
    # 检查输入文件
    if not INPUT_FILE.exists():
        print(f"❌ 输入文件不存在: {INPUT_FILE}")
        return
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 读取数据
    print(f"\n📖 读取数据: {INPUT_FILE}")
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)
    
    print(f"✅ 总样本数: {len(data)}")
    
    # 统计file数量
    file_ids = set(sample["metadata"]["file_id"] for sample in data)
    print(f"✅ 总文件数: {len(file_ids)}")
    
    # 分割数据
    print(f"\n🔀 分割数据 (验证集比例: {VAL_RATIO*100:.1f}%)")
    train_data, val_data = split_by_file_id(data, val_ratio=VAL_RATIO)
    
    print(f"✅ 训练集: {len(train_data)} 样本")
    print(f"✅ 验证集: {len(val_data)} 样本")
    
    # 验证集文件统计
    train_files = set(s["metadata"]["file_id"] for s in train_data)
    val_files = set(s["metadata"]["file_id"] for s in val_data)
    print(f"✅ 训练集文件: {len(train_files)}")
    print(f"✅ 验证集文件: {len(val_files)}")
    
    # 确保没有重叠
    overlap = train_files & val_files
    if overlap:
        print(f"⚠️  警告: {len(overlap)} 个文件同时出现在训练集和验证集")
    else:
        print("✅ 训练集和验证集无重叠")
    
    # 保存数据
    print(f"\n💾 保存训练集: {TRAIN_FILE}")
    with TRAIN_FILE.open("w", encoding="utf-8") as f:
        json.dump(train_data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 保存验证集: {VAL_FILE}")
    with VAL_FILE.open("w", encoding="utf-8") as f:
        json.dump(val_data, f, ensure_ascii=False, indent=2)
    
    # 保存统计信息
    stats = {
        "input_file": str(INPUT_FILE),
        "total_samples": len(data),
        "total_files": len(file_ids),
        "train_samples": len(train_data),
        "train_files": len(train_files),
        "val_samples": len(val_data),
        "val_files": len(val_files),
        "val_ratio": VAL_RATIO,
        "overlap_files": len(overlap) if overlap else 0
    }
    
    print(f"💾 保存统计信息: {STATS_FILE}")
    with STATS_FILE.open("w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    # 显示示例
    print("\n" + "=" * 60)
    print("训练集示例:")
    print("=" * 60)
    print(json.dumps(train_data[0], ensure_ascii=False, indent=2)[:500] + "...")
    
    print("\n" + "=" * 60)
    print("✅ 分割完成！")
    print("=" * 60)
    print(f"训练集: {TRAIN_FILE} ({len(train_data)} 样本, {len(train_files)} 文件)")
    print(f"验证集: {VAL_FILE} ({len(val_data)} 样本, {len(val_files)} 文件)")
    

if __name__ == "__main__":
    main()
