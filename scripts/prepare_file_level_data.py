#!/usr/bin/env python3
"""
简单处理：parsed_workflows.jsonl -> file_level_data.jsonl
只添加正确的file_id (file_000001, file_000002, ...)
"""

import json
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 输入输出路径
INPUT_FILE = Path('data/processed/parsed_workflows.jsonl')
OUTPUT_FILE = Path('data/processed/file_level_data.jsonl')

def main():
    logger.info(f'读取 {INPUT_FILE}...')
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as infile, \
         open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
        
        for idx, line in enumerate(infile, 1):
            workflow = json.loads(line)
            
            # 添加file_id字段（以原始parsed_workflows中的顺序）
            workflow['file_id'] = f'file_{idx:06d}'
            
            # 写入
            outfile.write(json.dumps(workflow, ensure_ascii=False) + '\n')
    
    logger.info(f'✅ 完成: {OUTPUT_FILE} ({idx} 条记录)')

if __name__ == '__main__':
    main()
