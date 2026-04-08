#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
02_build_rag.py — 构建步骤级 RAG 知识库

数据源 : 865 条唯一 (instruction → step_data) 对
功能   :
  1. 从 step_level_instructions.jsonl + step_level_data.jsonl 提取 865 条唯一对
  2. 使用 sentence-transformers 对每条 instruction 生成语义向量
  3. 保存索引到 data/processed/rag_index/ (embeddings.npy + metadata.jsonl)
  4. StepRAG 类提供 retrieve(query, top_k) 混合相似度检索

检索流程:
  用户输入 (任意自然语言)
      ↓  embed
  query_vector
      ↓  dense cosine similarity  (权重 α=0.7)
      +
  keyword_overlap_score           (权重 1-α=0.3)
   └─ 利用 keyword_weights 中各词的重要性权重:
       动作词 3.0 > 对象名 2.0 > 数据库 1.8 > 方法变体 1.6 > ID 1.4
      ↓  hybrid score = α*cosine + (1-α)*keyword_overlap
  top-k 最相似的 (instruction, step_data) 对
"""

import json
import logging
import os
import re
import numpy as np
from pathlib import Path
from typing import Any, Dict, List, Tuple

# 屏蔽 transformers 尝试加载 TensorFlow backend（避免 tf_env 中的冲突）
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_JAX", "0")
os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ============================================================
# 配置
# ============================================================
EMBED_MODEL  = "all-MiniLM-L6-v2"   # 80 MB, 英文优化, 384 维, 支持短句
HYBRID_ALPHA = 0.70                  # 混合评分权重: α*dense + (1-α)*keyword_overlap

DATA_DIR  = Path("data/processed")
INDEX_DIR = DATA_DIR / "rag_index"
EMBED_FILE = INDEX_DIR / "embeddings.npy"
META_FILE  = INDEX_DIR / "metadata.jsonl"

# ============================================================
# 数据加载
# ============================================================

def load_unique_pairs() -> List[Dict[str, Any]]:
    """
    从 step_level_instructions.jsonl + step_level_data.jsonl 提取唯一 instruction-step 对。
    以 instruction 文本去重，每条 instruction 只保留首次出现的 step。
    返回列表, 每项包含完整字段供 RAG 索引使用。
    """
    instr_path = DATA_DIR / "step_level_instructions.jsonl"
    data_path  = DATA_DIR / "step_level_data.jsonl"

    logger.info("加载 step_level_instructions.jsonl ...")
    instrs: Dict[Tuple, Dict] = {}
    with open(instr_path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            instrs[(r["file_id"], r["step_index"])] = r

    logger.info("加载 step_level_data.jsonl ...")
    data_rows: Dict[Tuple, Dict] = {}
    with open(data_path, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            data_rows[(r["file_id"], r["step_index"])] = r

    # 去重：每条 instruction 只保留首次出现的 step_data
    seen_instructions: Dict[str, bool] = {}
    pairs: List[Dict[str, Any]] = []

    for key, instr_row in instrs.items():
        instruction = instr_row["instruction"]
        if instruction in seen_instructions:
            continue
        seen_instructions[instruction] = True

        step = data_rows.get(key, {})
        pairs.append({
            "instruction": instruction,
            "module":      step.get("module", ""),
            "method":      step.get("method", ""),
            "object":      step.get("object", ""),
            "database":    step.get("database", "").replace(":", "").strip(),
            "command":     step.get("command", ""),
            "object_id":   step.get("object_id", ""),
            "test_data":   step.get("test_data", {}),
            "keyword_weights": instr_row.get("keyword_weights", {}),
            "context":         instr_row.get("context", {}),
        })

    logger.info(f"提取唯一 instruction-step 对: {len(pairs)} 条")
    return pairs


# ============================================================
# StepRAG 类
# ============================================================

class StepRAG:
    """
    步骤级语义检索器。

    用法:
        # 首次构建索引
        rag = StepRAG()
        pairs = load_unique_pairs()
        rag.build(pairs)

        # 之后直接加载
        rag = StepRAG()
        rag.load()

        # 检索
        results = rag.retrieve("open the high-voltage cable editor", top_k=3)
    """

    def __init__(self, model_name: str = EMBED_MODEL, alpha: float = HYBRID_ALPHA):
        self.model_name  = model_name
        self.alpha       = alpha       # 混合评分中 dense cosine 的权重
        self._model      = None        # lazy-loaded sentence-transformers model
        self.embeddings: np.ndarray | None = None   # shape (N, D)
        self.metadata:   List[Dict]         = []

    # ----------------------------------------------------------------
    # 模型懒加载
    # ----------------------------------------------------------------
    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"加载 embedding 模型: {self.model_name} ...")
            self._model = SentenceTransformer(self.model_name)
            logger.info("模型加载完成")
        return self._model

    # ----------------------------------------------------------------
    # 构建索引
    # ----------------------------------------------------------------
    def build(self, pairs: List[Dict[str, Any]]) -> None:
        """
        计算所有 instruction 的嵌入向量，保存索引到磁盘。
        """
        if not pairs:
            raise ValueError("pairs 列表为空，无法构建索引")

        INDEX_DIR.mkdir(parents=True, exist_ok=True)

        instructions = [p["instruction"] for p in pairs]
        logger.info(f"计算 {len(instructions)} 条 instruction 的嵌入向量 ...")

        model = self._get_model()
        vecs = model.encode(
            instructions,
            batch_size=128,
            show_progress_bar=True,
            normalize_embeddings=True,   # L2 归一化 → cosine = dot product
        )
        self.embeddings = np.array(vecs, dtype=np.float32)  # (N, 384)
        self.metadata   = pairs

        # 保存
        np.save(EMBED_FILE, self.embeddings)
        with open(META_FILE, "w", encoding="utf-8") as f:
            for item in self.metadata:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        logger.info(f"索引已保存:")
        logger.info(f"  {EMBED_FILE}  ({self.embeddings.shape})")
        logger.info(f"  {META_FILE}   ({len(self.metadata)} 条)")

    # ----------------------------------------------------------------
    # 加载索引
    # ----------------------------------------------------------------
    def load(self) -> None:
        """从磁盘加载已保存的索引。"""
        if not EMBED_FILE.exists() or not META_FILE.exists():
            raise FileNotFoundError(
                f"索引文件不存在，请先调用 build() 构建索引。\n"
                f"  {EMBED_FILE}\n  {META_FILE}"
            )
        self.embeddings = np.load(EMBED_FILE).astype(np.float32)
        self.metadata   = []
        with open(META_FILE, encoding="utf-8") as f:
            for line in f:
                self.metadata.append(json.loads(line))
        logger.info(f"索引已加载: {len(self.metadata)} 条, 向量维度 {self.embeddings.shape[1]}")

    # ----------------------------------------------------------------
    # 关键词加权重叠评分
    # ----------------------------------------------------------------
    @staticmethod
    def _keyword_overlap_score(query_lower: str, keyword_weights: Dict) -> float:
        """
        计算用户 query 与文档关键词权重的加权命中率。

        修复点:
          P1 — 词边界匹配：用 re.search(r'\\b...\\b') 替代 substring，
               防止 "get" 误命中 "together"，"open" 误命中 "reopen" 等。
          P2+P3 — [ID] 从分子和分母中同时排除：
               分母只统计「可匹配」的关键词（真实词 + [DB:xxx]），
               使 ID 的 1.4 权重不会系统性压低含 ID 步骤的得分。

        算法:
          scoreable = keywords 中排除 [ID] 的条目
          分母 = scoreable 条目权重之和
          对每个 scoreable 词:
            - [DB:xxx] → 提取数据库名，词边界匹配
            - 普通词   → 词边界匹配（大小写不敏感）
          score = 命中权重之和 / 分母  ∈ [0, 1]
        """
        keywords = keyword_weights.get("keywords", [])
        if not keywords:
            return 0.0
        
        # P2+P3: 排除虚拟 token [ID]，分母同样不计入
        scoreable = [(kw, w) for kw, w in keywords if kw != "[ID]"]
        if not scoreable:
            return 0.0

        total_weight = sum(w for _, w in scoreable)
        if total_weight == 0:
            return 0.0

        matched_weight = 0.0
        for kw, weight in scoreable:
            if kw.startswith("[DB:") and kw.endswith("]"):
                db_name = kw[4:-1].lower()
                # P1: 词边界匹配数据库名
                if db_name and re.search(r"\b" + re.escape(db_name) + r"\b", query_lower):
                    matched_weight += weight
            else:
                # P1: 词边界匹配，避免短词误命中长词
                if re.search(r"\b" + re.escape(kw.lower()) + r"\b", query_lower):
                    matched_weight += weight

        return matched_weight / total_weight

    # ----------------------------------------------------------------
    # 混合检索（dense cosine + keyword overlap）
    # ----------------------------------------------------------------
    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        混合语义检索：α * cosine_similarity + (1-α) * keyword_overlap_score

        Args:
            query   : 用户输入的自然语言指令（中英文均可）
            top_k   : 返回结果数量

        Returns:
            list of dict sorted by hybrid score (descending), 每项包含:
              - score         : 混合评分 (0.0 ~ 1.0)
              - score_dense   : 纯 cosine 相似度
              - score_keyword : 关键词加权命中率
              - instruction   : 匹配到的规范指令
              - module / method / object / database / command / object_id / test_data
        """
        if self.embeddings is None:
            raise RuntimeError("索引未加载。请先调用 build() 或 load()。")

        model = self._get_model()
        q_vec = model.encode([query], normalize_embeddings=True)  # (1, D)
        q_vec = np.array(q_vec, dtype=np.float32)

        # 1. Dense cosine scores（L2 归一化后等同于 dot product）
        dense_scores = (self.embeddings @ q_vec.T).squeeze()   # (N,)

        # 2. Keyword overlap scores（利用预存的 keyword_weights）
        query_lower = query.lower()
        kw_scores = np.array([
            self._keyword_overlap_score(query_lower, meta.get("keyword_weights", {}))
            for meta in self.metadata
        ], dtype=np.float32)                                    # (N,)

        # 3. 混合评分
        hybrid_scores = self.alpha * dense_scores + (1.0 - self.alpha) * kw_scores

        # 4. 取 top_k
        top_k = min(top_k, len(hybrid_scores))
        top_indices = np.argpartition(hybrid_scores, -top_k)[-top_k:]
        top_indices = top_indices[np.argsort(hybrid_scores[top_indices])[::-1]]

        results = []
        for idx in top_indices:
            entry = self.metadata[idx].copy()
            entry["score"]         = float(hybrid_scores[idx])
            entry["score_dense"]   = float(dense_scores[idx])
            entry["score_keyword"] = float(kw_scores[idx])
            results.append(entry)

        return results

    # ----------------------------------------------------------------
    # 检索并格式化显示
    # ----------------------------------------------------------------
    def retrieve_and_display(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """检索并打印可读结果（含混合分拆），同时返回结果列表。"""
        results = self.retrieve(query, top_k=top_k)
        print(f'\n{"="*66}')
        print(f'Query : "{query}"')
        print(f'alpha = {self.alpha}  (dense:{self.alpha:.2f} + keyword:{1-self.alpha:.2f})')
        print(f'{"="*66}')
        for rank, r in enumerate(results, 1):
            print(f"  #{rank}  hybrid={r['score']:.4f}  "
                  f"(dense={r['score_dense']:.3f}  kw={r['score_keyword']:.3f})")
            print(f"       instruction : {r['instruction']}")
            print(f"       module      : {r['module']}  /  method: {r['method']}")
            print(f"       object      : {r['object']}  |  database: {r['database']}")
            if r.get("object_id"):
                print(f"       object_id   : {r['object_id']}")
        return results

    # ----------------------------------------------------------------
    # 相似度阈值过滤（用于判断 query 是否超出知识库覆盖范围）
    # ----------------------------------------------------------------
    def is_in_scope(self, query: str, threshold: float = 0.45) -> Tuple[bool, float]:
        """
        判断 query 是否在知识库覆盖范围内。
        使用混合评分（alpha * dense + (1-alpha) * keyword_overlap）。
        返回 (in_scope: bool, best_hybrid_score: float)。
        建议先调用 calibrate_threshold() 获得数据驱动的阈值，再传入 threshold。
        """
        results = self.retrieve(query, top_k=1)
        best_score = results[0]["score"] if results else 0.0
        return best_score >= threshold, best_score

    # ----------------------------------------------------------------
    # P5: 数据驱动的阈值校准
    # ----------------------------------------------------------------
    def calibrate_threshold(self, percentile: float = 5.0) -> float:
        """
        基于索引内部分布，估算合理的 is_in_scope 阈值。

        方法：
          对索引中每条 instruction，以它自身作为 query，
          找到其「最佳非自身邻居」的 hybrid 分数。
          收集所有 N 条这样的分数，取第 percentile 百分位作为阈值。

          原理：合法域内 query 的得分应 ≥ 域内任意两文档之间的相互相似度；
          设阈值在该分布的低端（默认第 5 百分位），可以让绝大多数
          真实相关 query 通过，同时过滤明显无关的 query。

        Args:
            percentile: 取分布的第几百分位，默认 5.0

        Returns:
            建议的 threshold 值
        """
        if self.embeddings is None:
            raise RuntimeError("索引未加载，请先调用 build() 或 load()。")

        n = len(self.metadata)
        # Dense 相似度矩阵 (N, N)：已 L2 归一化，直接矩阵乘
        sim_matrix = self.embeddings @ self.embeddings.T   # (N, N)

        cross_scores: List[float] = []
        for i in range(n):
            query_lower = self.metadata[i]["instruction"].lower()
            dense_row = sim_matrix[i].copy()               # (N,)

            kw_row = np.array([
                self._keyword_overlap_score(
                    query_lower, self.metadata[j].get("keyword_weights", {})
                )
                for j in range(n)
            ], dtype=np.float32)

            hybrid_row = self.alpha * dense_row + (1.0 - self.alpha) * kw_row
            hybrid_row[i] = -1.0          # 排除自身
            cross_scores.append(float(hybrid_row.max()))

        threshold = float(np.percentile(cross_scores, percentile))
        logger.info(
            f"阈值校准 (第{percentile}%位): {threshold:.4f}  "
            f"[min={min(cross_scores):.4f}  "
            f"median={float(np.median(cross_scores)):.4f}  "
            f"max={max(cross_scores):.4f}]"
        )
        return threshold


# ============================================================
# 主程序
# ============================================================

def main():
    logger.info("=" * 60)
    logger.info("步骤级 RAG 知识库构建")
    logger.info("=" * 60)

    # 1. 提取 865 条唯一对
    pairs = load_unique_pairs()

    # 2. 构建并保存索引
    rag = StepRAG(model_name=EMBED_MODEL)
    rag.build(pairs)

    # 3. 验证：重新加载并测试检索
    logger.info("\n验证：重新加载索引并测试检索 ...")
    rag2 = StepRAG(model_name=EMBED_MODEL)
    rag2.load()

    # P5: 数据驱动阈值校准
    logger.info("\n校准 is_in_scope 阈值 ...")
    threshold = rag2.calibrate_threshold(percentile=5.0)
    print(f"\n>> 建议阈值 (第5百分位): {threshold:.4f}  （将用于以下测试）")

    test_queries = [
        # 英文近似查询
        "open the MS cable editor",
        "create a new kabel object in elektra",
        "click the delete button",
        "verify a station field value",
        "run a datamodel check in the database",
        "select the first item in the hierarchy viewer",
        # 中文查询（测试跨语言语义）
        "open the cable",
        "delete an object",
        # 超出范围的查询
        "please send me an email",
    ]

    print()
    for q in test_queries:
        in_scope, score = rag2.is_in_scope(q, threshold=threshold)
        scope_label = "IN SCOPE " if in_scope else "OUT OF SCOPE"
        results = rag2.retrieve(q, top_k=2)
        print(f'[{scope_label}]  hybrid={score:.3f}  query="{q}"')
        for r in results:
            print(f'   >> hybrid={r["score"]:.3f}  '
                  f'dense={r["score_dense"]:.3f}  kw={r["score_keyword"]:.3f}  '
                  f'"{r["instruction"][:60]}"')
        print()


if __name__ == "__main__":
    main()
