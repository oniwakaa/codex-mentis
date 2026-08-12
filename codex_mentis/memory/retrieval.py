import math
import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from codex_mentis.memory.store import MemoryStore, cosine_similarity

class BM25Scorer:
    def __init__(self, corpus: List[Dict[str, Any]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus = corpus
        self.N = len(corpus)
        self.avgdl = sum(len(self._tokenize(d["content"])) for d in corpus) / self.N if self.N > 0 else 0.0
        
        # Document term frequencies and lengths
        self.doc_tfs = []
        self.doc_lens = []
        self.df = {} # term to doc frequency
        
        for doc in corpus:
            tokens = self._tokenize(doc["content"])
            self.doc_lens.append(len(tokens))
            
            tf = {}
            for tok in tokens:
                tf[tok] = tf.get(tok, 0) + 1
            self.doc_tfs.append(tf)
            
            for tok in tf.keys():
                self.df[tok] = self.df.get(tok, 0) + 1
                
    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\w+", text.lower())
        
    def idf(self, term: str) -> float:
        n_q = self.df.get(term, 0)
        # BM25 standard IDF with smoothing
        return math.log((self.N - n_q + 0.5) / (n_q + 0.5) + 1.0)
        
    def score(self, query: str, doc_idx: int) -> float:
        q_terms = self._tokenize(query)
        tf = self.doc_tfs[doc_idx]
        doc_len = self.doc_lens[doc_idx]
        
        score = 0.0
        for term in q_terms:
            if term not in self.df:
                continue
            f_q = tf.get(term, 0)
            idf_q = self.idf(term)
            
            numerator = f_q * (self.k1 + 1)
            denominator = f_q + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl) if self.avgdl > 0 else 1.0)
            score += idf_q * (numerator / denominator)
        return score

class MemoryRetriever:
    def __init__(self, store: MemoryStore):
        self.store = store

    def search(
        self, 
        query: str, 
        top_k: int = 5, 
        filters: Optional[Dict[str, Any]] = None,
        hybrid_alpha: float = 0.5,
        current_topic: Optional[str] = None,
        topic_boost: float = 0.15,
        recency_bias: float = 0.1
    ) -> List[Dict[str, Any]]:
        """
        Run hybrid search (BM25 + vector similarity) over all matching memories,
        applying topic boost, recency bias, and filters.
        """
        layer_filter = filters.get("layer") if filters else None
        topic_filter = filters.get("topic") if filters else None
        
        candidates = self.store.list_memories(layer=layer_filter, topic=topic_filter)
        if not candidates:
            return []
            
        # Compute vector similarities
        query_vector = self.store.get_embedding(query)
        vector_scores = []
        for cand in candidates:
            sim = cosine_similarity(query_vector, cand.embedding)
            vector_scores.append(sim)
            
        # Compute BM25 scores
        corpus = [{"content": cand.content} for cand in candidates]
        bm25_scorer = BM25Scorer(corpus)
        bm25_scores = [bm25_scorer.score(query, idx) for idx in range(len(candidates))]
        
        # Normalize scores to [0.0, 1.0] for fair combination
        max_vec = max(vector_scores) if vector_scores else 1.0
        min_vec = min(vector_scores) if vector_scores else 0.0
        vec_range = max_vec - min_vec
        
        max_bm25 = max(bm25_scores) if bm25_scores else 1.0
        min_bm25 = min(bm25_scores) if bm25_scores else 0.0
        bm25_range = max_bm25 - min_bm25
        
        results = []
        now = datetime.now()
        
        for idx, cand in enumerate(candidates):
            norm_vec = (vector_scores[idx] - min_vec) / vec_range if vec_range > 0 else vector_scores[idx]
            norm_bm25 = (bm25_scores[idx] - min_bm25) / bm25_range if bm25_range > 0 else bm25_scores[idx]
            
            # Linear combination
            base_score = hybrid_alpha * norm_vec + (1.0 - hybrid_alpha) * norm_bm25
            
            # Topic boost
            boost_val = 0.0
            if current_topic and cand.topic.lower() == current_topic.lower():
                boost_val += topic_boost
            elif topic_filter and cand.topic.lower() == topic_filter.lower():
                boost_val += topic_boost
                
            # Recency bias
            recency_score = 0.0
            if cand.timestamp:
                try:
                    days_elapsed = (now - cand.timestamp).days
                    recency_score = 1.0 / (1.0 + 0.05 * max(0, days_elapsed))
                except Exception:
                    pass
                    
            final_score = base_score * (1.0 + boost_val) + recency_bias * recency_score
            
            # Custom metadata filters
            keep = True
            if filters:
                for k, v in filters.items():
                    if k not in ("layer", "topic"):
                        if cand.metadata.get(k) != v:
                            keep = False
                            
            if keep:
                results.append({
                    "id": cand.id,
                    "layer": cand.layer,
                    "content": cand.content,
                    "topic": cand.topic,
                    "timestamp": cand.timestamp.strftime("%Y-%m-%d %H:%M:%S") if cand.timestamp else "",
                    "metadata": cand.metadata,
                    "score": final_score
                })
                
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_relevant_context(self, query: str, max_tokens: int = 1500) -> str:
        """
        Finds relevant context and formats it as a single string,
        respecting the token limit (estimating 4 characters per token).
        """
        max_chars = max_tokens * 4
        mems = self.search(query, top_k=6)
        
        if not mems:
            return "No relevant memories found."

        context_lines = []
        current_len = 0
        
        for m in mems:
            score_pct = m["score"] * 100
            block = (
                f"--- Memory Block (Layer: {m['layer']}, Topic: {m['topic']}, Relevance: {score_pct:.1f}%) ---\n"
                f"{m['content']}\n"
                f"Timestamp: {m['timestamp']}\n"
                f"Metadata: {m['metadata']}\n"
            )
            
            if current_len + len(block) > max_chars:
                remaining = max_chars - current_len
                if remaining > 100:
                    context_lines.append(block[:remaining] + "... [TRUNCATED DUE TO CONTEXT LIMIT]")
                break
                
            context_lines.append(block)
            current_len += len(block)
            
        return "\n".join(context_lines)
