#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
api_server.py - Flask API 服务器

将本地模型部署为 Web API 服务，便于远程调用。

使用方法：
    # 启动服务器
    python api_server.py
    
    # 默认监听 http://localhost:5000
    
调用示例：
    curl -X POST http://localhost:5000/api/infer \\
      -H "Content-Type: application/json" \\
      -d '{"instruction": "Open the editor", "threshold": 0.8}'
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any
import sys
from datetime import datetime
import traceback

from flask import Flask, request, jsonify
from flask_cors import CORS

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================
# 配置
# ============================================================

# Flask 应用配置
FLASK_ENV = "production"
HOST = "0.0.0.0"
PORT = 5000
DEBUG = False

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================
# 初始化 Flask 应用
# ============================================================

app = Flask(__name__)
CORS(app)  # 启用跨域请求

# 全局推理引擎
inferencer = None
config = None

# ============================================================
# 初始化函数
# ============================================================

def load_config():
    """加载本地配置文件"""
    config_path = PROJECT_ROOT / "configs" / "local_config.json"
    
    if not config_path.exists():
        logger.warning("配置文件不存在，使用默认配置")
        return {
            "model": {
                "local_path": "./models/step-level-model-865",
                "device": "auto",
            },
            "rag": {
                "index_path": "./data/processed/rag_index",
                "threshold": 0.8,
                "enabled": True,
            },
            "inference": {
                "max_tokens": 1024,
            },
            "api": {
                "host": "0.0.0.0",
                "port": 5000,
                "debug": False,
                "max_workers": 4,
            }
        }
    
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
        logger.info(f"配置文件已加载: {config_path}")
        return cfg


def initialize_inferencer():
    """初始化推理引擎（在启动时执行一次）"""
    global inferencer, config
    
    logger.info("初始化推理引擎...")
    
    try:
        from src.inference import HybridInferencer
        
        config = load_config()
        
        inferencer = HybridInferencer(
            model_path=config["model"]["local_path"],
            rag_index_path=config["rag"]["index_path"],
            use_rag=config["rag"].get("enabled", True),
            device=config["model"].get("device", "auto"),
        )
        
        logger.info("✅ 推理引擎已就绪")
        return True
    
    except Exception as e:
        logger.error(f"❌ 推理引擎初始化失败: {e}")
        logger.error(traceback.format_exc())
        return False


# ============================================================
# API 路由
# ============================================================

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "inferencer": "ready" if inferencer else "not ready"
    }), 200


@app.route('/api/infer', methods=['POST'])
def api_infer():
    """推理端点"""
    if inferencer is None:
        return jsonify({
            "error": "推理引擎未就绪",
            "status": "error"
        }), 503
    
    try:
        # 获取请求数据
        data = request.get_json()
        
        if not data or 'instruction' not in data:
            return jsonify({
                "error": "缺少必要字段: instruction",
                "status": "error"
            }), 400
        
        instruction = data.get('instruction', '').strip()
        rag_threshold = data.get('threshold', config.get('rag', {}).get('threshold', 0.8))
        max_tokens = data.get('max_tokens', config.get('inference', {}).get('max_tokens', 1024))
        return_details = data.get('return_details', False)
        
        # 验证参数
        if not instruction:
            return jsonify({
                "error": "指令不能为空",
                "status": "error"
            }), 400
        
        if not 0.0 <= rag_threshold <= 1.0:
            return jsonify({
                "error": "threshold 必须在 0.0 到 1.0 之间",
                "status": "error"
            }), 400
        
        # 执行推理
        logger.info(f"推理请求: {instruction[:50]}...")
        
        result = inferencer.infer(
            instruction,
            rag_threshold=rag_threshold,
            max_tokens=max_tokens,
            return_details=return_details
        )
        
        # 构建响应
        response = {
            "status": "success",
            "instruction": instruction,
            "source": result['source'],
            "confidence": result['confidence'],
            "result": result['result'],
            "explanation": result['explanation'],
            "timestamp": datetime.now().isoformat()
        }
        
        if return_details and result.get('rag_details'):
            response['rag_details'] = result['rag_details']
        
        logger.info(f"推理完成: {result['source']}")
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"❌ 推理出错: {e}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route('/api/batch', methods=['POST'])
def api_batch_infer():
    """批量推理端点"""
    if inferencer is None:
        return jsonify({
            "error": "推理引擎未就绪",
            "status": "error"
        }), 503
    
    try:
        # 获取请求数据
        data = request.get_json()
        
        if not data or 'instructions' not in data:
            return jsonify({
                "error": "缺少必要字段: instructions (list)",
                "status": "error"
            }), 400
        
        instructions = data.get('instructions', [])
        rag_threshold = data.get('threshold', config.get('rag', {}).get('threshold', 0.8))
        
        if not isinstance(instructions, list) or not instructions:
            return jsonify({
                "error": "instructions 必须是非空列表",
                "status": "error"
            }), 400
        
        # 执行批量推理
        logger.info(f"批量推理请求: {len(instructions)} 条指令")
        
        results = inferencer.batch_infer(
            instructions,
            rag_threshold=rag_threshold,
            return_details=False
        )
        
        # 统计
        rag_count = sum(1 for r in results if r['source'] == 'rag')
        model_count = sum(1 for r in results if r['source'] == 'model')
        
        # 构建响应
        response = {
            "status": "success",
            "total": len(instructions),
            "rag_count": rag_count,
            "model_count": model_count,
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
        logger.info(f"批量推理完成: RAG {rag_count}, 模型 {model_count}")
        
        return jsonify(response), 200
    
    except Exception as e:
        logger.error(f"❌ 批量推理出错: {e}")
        logger.error(traceback.format_exc())
        
        return jsonify({
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }), 500


@app.route('/api/config', methods=['GET'])
def api_get_config():
    """获取当前配置"""
    if config is None:
        return jsonify({"error": "配置未加载"}), 503
    
    # 隐藏敏感信息
    safe_config = {
        "model": {
            "local_path": config.get('model', {}).get('local_path'),
            "device": config.get('model', {}).get('device'),
        },
        "rag": {
            "enabled": config.get('rag', {}).get('enabled'),
            "threshold": config.get('rag', {}).get('threshold'),
        },
        "inference": {
            "max_tokens": config.get('inference', {}).get('max_tokens'),
        }
    }
    
    return jsonify(safe_config), 200


@app.route('/api/status', methods=['GET'])
def api_get_status():
    """获取系统状态"""
    return jsonify({
        "status": "ready" if inferencer else "not ready",
        "rag_available": inferencer.rag_available if inferencer else False,
        "device": config.get('model', {}).get('device') if config else None,
        "timestamp": datetime.now().isoformat()
    }), 200


@app.route('/api/docs', methods=['GET'])
def api_docs():
    """API 文档"""
    docs = {
        "title": "GIS 推理 API",
        "version": "1.0.0",
        "base_url": f"http://{request.host}",
        "endpoints": [
            {
                "name": "健康检查",
                "method": "GET",
                "path": "/health",
                "description": "检查 API 服务状态"
            },
            {
                "name": "单条推理",
                "method": "POST",
                "path": "/api/infer",
                "description": "执行单条指令推理",
                "request": {
                    "instruction": "str (必填) - 输入指令",
                    "threshold": "float (可选) - RAG 相似度阈值 (0.0-1.0), 默认 0.8",
                    "max_tokens": "int (可选) - 最大生成长度，默认 1024",
                    "return_details": "bool (可选) - 是否返回详细信息，默认 false"
                },
                "response": {
                    "status": "success/error",
                    "source": "rag/model/error",
                    "confidence": "float",
                    "result": "dict/str",
                    "explanation": "str"
                }
            },
            {
                "name": "批量推理",
                "method": "POST",
                "path": "/api/batch",
                "description": "执行批量指令推理",
                "request": {
                    "instructions": "list[str] (必填) - 指令列表",
                    "threshold": "float (可选) - RAG 相似度阈值，默认 0.8"
                },
                "response": {
                    "status": "success/error",
                    "total": "int",
                    "rag_count": "int",
                    "model_count": "int",
                    "results": "list[dict]"
                }
            },
            {
                "name": "获取配置",
                "method": "GET",
                "path": "/api/config",
                "description": "获取当前系统配置"
            },
            {
                "name": "获取状态",
                "method": "GET",
                "path": "/api/status",
                "description": "获取系统运行状态"
            },
            {
                "name": "API 文档",
                "method": "GET",
                "path": "/api/docs",
                "description": "获取此文档"
            }
        ],
        "examples": [
            {
                "title": "单条推理",
                "curl": '''curl -X POST http://localhost:5000/api/infer \\
  -H "Content-Type: application/json" \\
  -d '{"instruction": "Open the editor", "threshold": 0.8}' '''
            },
            {
                "title": "批量推理",
                "curl": '''curl -X POST http://localhost:5000/api/batch \\
  -H "Content-Type: application/json" \\
  -d '{"instructions": ["Open editor", "Create cable"], "threshold": 0.8}' '''
            }
        ]
    }
    
    return jsonify(docs), 200


# ============================================================
# 错误处理
# ============================================================

@app.errorhandler(404)
def not_found(e):
    """404 错误处理"""
    return jsonify({
        "error": "端点未找到",
        "status": "error",
        "path": request.path,
        "available_endpoints": ["/health", "/api/infer", "/api/batch", "/api/docs"]
    }), 404


@app.errorhandler(405)
def method_not_allowed(e):
    """405 错误处理"""
    return jsonify({
        "error": "方法不允许",
        "status": "error",
        "method": request.method,
        "path": request.path
    }), 405


@app.errorhandler(500)
def internal_error(e):
    """500 错误处理"""
    logger.error(f"内部错误: {e}")
    return jsonify({
        "error": "内部服务器错误",
        "status": "error"
    }), 500


# ============================================================
# 启动脚本
# ============================================================

def main():
    global config
    
    print("\n" + "="*70)
    print("  🚀 GIS 推理 API 服务器")
    print("="*70)
    
    # 初始化
    print("\n  🔧 初始化中...")
    
    if not initialize_inferencer():
        print("\n  ❌ 初始化失败！")
        sys.exit(1)
    
    # 获取配置
    config_api = config.get('api', {})
    host = config_api.get('host', HOST)
    port = config_api.get('port', PORT)
    debug = config_api.get('debug', DEBUG)
    
    # 打印信息
    print(f"\n  ✅ 服务器信息:")
    print(f"     • 地址: http://{host}:{port}")
    print(f"     • API 文档: http://{host}:{port}/api/docs")
    print(f"     • 健康检查: http://{host}:{port}/health")
    print(f"     • 调试模式: {'启用' if debug else '禁用'}")
    
    print(f"\n  🎯 快速测试:")
    print(f"     curl http://{host}:{port}/health")
    
    print(f"\n  📚 示例请求:")
    print(f"     curl -X POST http://{host}:{port}/api/infer \\\\")
    print(f"       -H 'Content-Type: application/json' \\\\")
    print(f"       -d '{{\"instruction\": \"Open the editor\"}}'")
    
    print(f"\n  {'='*70}\n")
    print(f"  按 Ctrl+C 停止服务器\n")
    
    # 启动服务器
    try:
        app.run(
            host=host,
            port=port,
            debug=debug,
            use_reloader=False  # 避免双次初始化
        )
    except KeyboardInterrupt:
        print(f"\n\n  👋 服务器已停止")
    except Exception as e:
        print(f"\n  ❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
