#!/usr/bin/env python3
"""
简单处理：parsed_workflows.jsonl -> step_level_data.jsonl
为每个step添加 file_id 和 step_index
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
OUTPUT_FILE = Path('data/processed/step_level_data.jsonl')

def main():
    logger.info(f'读取 {INPUT_FILE}...')
    
    total_steps = 0
    
    with open(INPUT_FILE, 'r', encoding='utf-8') as infile, \
         open(OUTPUT_FILE, 'w', encoding='utf-8') as outfile:
        
        for file_idx, line in enumerate(infile, 1):
            workflow = json.loads(line)
            file_id = f'file_{file_idx:06d}'
            
            steps = workflow.get('steps', [])
            for step_idx, step in enumerate(steps):
                # 添加file_id和step_index
                step['file_id'] = file_id
                step['step_index'] = step_idx
                
                # 写入
                outfile.write(json.dumps(step, ensure_ascii=False) + '\n')
                total_steps += 1
    
    logger.info(f'✅ 完成: {OUTPUT_FILE} ({total_steps} 条记录)')

if __name__ == '__main__':
    main()
