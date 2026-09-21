#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rag_utils.py — RAG 工具模块（简化版）

这是从 scripts/02_build_rag.py 提取的核心 RAG 类，
用于在推理系统中进行高效的语义检索。

核心功能:
  • 使用预计算的向量索引进行快速检索
  • 混合评分：密集相似度 (0.7) + 关键词重叠 (0.3)
  • 支持中英文指令
"""

import json
import logging
import os
import re
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ============================================================
# 配置
# ============================================================
EMBED_MODEL = "all-MiniLM-L6-v2"   # 轻量级嵌入模型
HYBRID_ALPHA = 0.70                # 混合评分权重

# ============================================================
# RAG 类
# ============================================================

class StepRAG:
    """
    步骤级语义检索器（生产版本）
    
    用法:
        rag = StepRAG()
        rag.load(rag_index_dir)
        
        results = rag.retrieve("open the editor", top_k=3)
        for r in results:
            print(f"相似度: {r['score']:.4f}, 指令: {r['instruction']}")
    """
    
    def __init__(self, model_name: str = EMBED_MODEL, alpha: float = HYBRID_ALPHA):
        self.model_name = model_name
        self.alpha = alpha
        self._model = None
        self.embeddings: np.ndarray | None = None
        self.metadata: List[Dict] = []
    
    def _get_model(self):
        """懒加载 embedding 模型"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"加载 embedding 模型: {self.model_name} ...")
                self._model = SentenceTransformer(self.model_name)
                logger.info("✅ 模型加载完成")
            except ImportError:
                logger.error("❌ 未安装 sentence-transformers，请运行: pip install sentence-transformers")
                raise
        return self._model
    
    def load(self, rag_index_dir: str | Path) -> None:
        """加载预建的 RAG 索引"""
        rag_index_dir = Path(rag_index_dir)
        embed_file = rag_index_dir / "embeddings.npy"
        meta_file = rag_index_dir / "metadata.jsonl"
        
        if not embed_file.exists() or not meta_file.exists():
            raise FileNotFoundError(
                f"RAG 索引文件不存在:\n"
                f"  {embed_file}\n"
                f"  {meta_file}\n"
                f"请先运行 scripts/02_build_rag.py 构建索引"
            )
        
        logger.info("加载 RAG 索引...")
        
        # 加载向量
        self.embeddings = np.load(embed_file).astype(np.float32)
        
        # 加载元数据
        self.metadata = []
        with open(meta_file, "r", encoding="utf-8") as f:
            for line in f:
                self.metadata.append(json.loads(line))
        
        logger.info(
            f"✅ 索引加载完成: {len(self.metadata)} 条记录, "
            f"向量维度 {self.embeddings.shape[1]}"
        )
    
    @staticmethod
    def _keyword_overlap_score(query_lower: str, keyword_weights: Dict) -> float:
        """计算关键词加权重叠评分"""
        keywords = keyword_weights.get("keywords", [])
        if not keywords:
            return 0.0
        
        # 排除虚拟 token [ID]
        scoreable = [(kw, w) for kw, w in keywords if kw != "[ID]"]
        if not scoreable:
            return 0.0
        
        total_weight = sum(w for _, w in scoreable)
        if total_weight == 0:
            return 0.0
        
        matched_weight = 0.0
        for kw, weight in scoreable:
            if kw.startswith("[DB:") and kw.endswith("]"):
                # 数据库字段匹配
                db_name = kw[4:-1].lower()
                if db_name and re.search(r"\b" + re.escape(db_name) + r"\b", query_lower):
                    matched_weight += weight
            else:
                # 普通关键词匹配
                if re.search(r"\b" + re.escape(kw.lower()) + r"\b", query_lower):
                    matched_weight += weight
        
        return matched_weight / total_weight
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        混合语义检索
        
        Args:
            query: 查询指令
            top_k: 返回结果数
        
        Returns:
            结果列表，每项包含:
              - score: 混合相似度分数
              - score_dense: 向量相似度
              - score_keyword: 关键词重叠分数
              - instruction, module, method, object, database, 等
        """
        if self.embeddings is None:
            raise RuntimeError("索引未加载。请先调用 load() 方法。")
        
        model = self._get_model()
        
        # 1. 计算查询向量
        q_vec = model.encode([query], normalize_embeddings=True)
        q_vec = np.array(q_vec, dtype=np.float32)
        
        # 2. 计算密集相似度
        dense_scores = (self.embeddings @ q_vec.T).squeeze()
        
        # 3. 计算关键词重叠分数
        query_lower = query.lower()
        kw_scores = np.array([
            self._keyword_overlap_score(query_lower, meta.get("keyword_weights", {}))
            for meta in self.metadata
        ], dtype=np.float32)
        
        # 4. 混合评分
        hybrid_scores = self.alpha * dense_scores + (1.0 - self.alpha) * kw_scores
        
        # 5. 取 top_k
        top_k = min(top_k, len(hybrid_scores))
        top_indices = np.argpartition(hybrid_scores, -top_k)[-top_k:]
        top_indices = top_indices[np.argsort(hybrid_scores[top_indices])[::-1]]
        
        # 6. 构建结果
        results = []
        for idx in top_indices:
            entry = self.metadata[idx].copy()
            entry["score"] = float(hybrid_scores[idx])
            entry["score_dense"] = float(dense_scores[idx])
            entry["score_keyword"] = float(kw_scores[idx])
            results.append(entry)
        
        return results
    
    def retrieve_and_display(self, query: str, top_k: int = 3) -> List[Dict]:
        """检索并打印可读结果"""
        results = self.retrieve(query, top_k=top_k)
        
        print(f'\n{"="*66}')
        print(f'Query: "{query}"')
        print(f'alpha = {self.alpha:.2f}  (dense: {self.alpha:.2f} + keyword: {1-self.alpha:.2f})')
        print(f'{"="*66}')
        
        for rank, r in enumerate(results, 1):
            print(f"  #{rank}  hybrid={r['score']:.4f}  "
                  f"(dense={r['score_dense']:.3f}  kw={r['score_keyword']:.3f})")
            print(f"       instruction: {r['instruction']}")
            print(f"       module: {r['module']}  /  method: {r['method']}")
            print(f"       object: {r['object']}  |  database: {r['database']}")
        
        return results


# ============================================================
# 简化 API
# ============================================================

def load_rag(rag_index_dir: str | Path) -> StepRAG:
    """加载 RAG 索引"""
    rag = StepRAG()
    rag.load(rag_index_dir)
    return rag


# ============================================================
# 使用示例
# ============================================================

if __name__ == "__main__":
    # 配置 RAG 索引路径
    RAG_INDEX_DIR = "data/processed/rag_index"
    
    # 加载 RAG
    rag = load_rag(RAG_INDEX_DIR)
    
    # 测试查询
    test_queries = [
        "Open E MS Installatie of station 6 002 005",
        "Create a new cable",
        "verify high voltage connections",
    ]
    
    print("\n" + "="*70)
    print("🎯 RAG 检索测试")
    print("="*70)
    
    for query in test_queries:
        rag.retrieve_and_display(query, top_k=3)
