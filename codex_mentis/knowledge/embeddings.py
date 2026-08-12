"""Embedding engine for semantic search — supports sentence-transformers with TF-IDF fallback."""
import os
import json
import math
import hashlib
from typing import List, Optional, Dict, Any
from collections import Counter


class EmbeddingEngine:
    """Generates text embeddings for semantic search."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", cache_dir: Optional[str] = None, db_path: Optional[str] = None):
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.db_path = db_path
        self._model = None
        self._use_transformer = None

    def embed(self, text: str) -> List[float]:
        """Generate embedding for a single text (alias for encode_single)."""
        return self.encode_single(text)

    def _try_load_model(self):
        """Try to load sentence-transformers model."""
        if self._use_transformer is not None:
            return self._use_transformer
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._use_transformer = True
            return True
        except (ImportError, Exception):
            self._use_transformer = False
            return False

    def encode(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts."""
        if self._try_load_model() and self._model is not None:
            embeddings = self._model.encode(texts, show_progress_bar=False)
            return [emb.tolist() for emb in embeddings]
        else:
            return [self._tfidf_embed(text) for text in texts]

    def encode_single(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        return self.encode([text])[0]

    def similarity(self, emb1: List[float], emb2: List[float]) -> float:
        """Compute cosine similarity between two embeddings."""
        dot = sum(a * b for a, b in zip(emb1, emb2))
        norm1 = math.sqrt(sum(a * a for a in emb1))
        norm2 = math.sqrt(sum(b * b for b in emb2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def _tfidf_embed(self, text: str, dim: int = 384) -> List[float]:
        """Simple TF-IDF-like embedding as fallback."""
        # Tokenize
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * dim

        # Count term frequencies
        tf = Counter(tokens)
        total = len(tokens)

        # Create embedding vector using hashing
        embedding = [0.0] * dim
        for token, count in tf.items():
            # TF weight
            weight = count / total
            # Log-frequency weighting
            weight = 1 + math.log(weight) if weight > 0 else 0
            # Hash token to dimensions
            hash_val = int(hashlib.md5(token.encode()).hexdigest(), 16)
            for i in range(3):
                idx = (hash_val + i) % dim
                sign = 1 if ((hash_val >> (8 + i)) & 1) else -1
                embedding[idx] += sign * weight

        # Normalize
        norm = math.sqrt(sum(x * x for x in embedding))
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer for fallback embedding."""
        import re
        text = text.lower()
        # Split on non-alphanumeric, keep math symbols
        tokens = re.findall(r"[a-z]+|[0-9]+|[αβγδεζηθικλμνξπρστυφχψω]", text)
        # Remove very common words
        stopwords = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                     "being", "have", "has", "had", "do", "does", "did", "will",
                     "would", "could", "should", "may", "might", "shall", "can",
                     "of", "in", "to", "for", "with", "on", "at", "from", "by",
                     "and", "or", "not", "but", "if", "then", "that", "this",
                     "it", "its", "as", "we", "you", "they", "he", "she"}
        return [t for t in tokens if t not in stopwords and len(t) > 1]
