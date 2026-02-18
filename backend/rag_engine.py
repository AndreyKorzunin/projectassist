from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from typing import List, Dict, Any
import re
import nltk
from nltk.tokenize import sent_tokenize
import warnings
import structlog

warnings.filterwarnings('ignore')
logger = structlog.get_logger()


try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)


class RAGEngine:


    def __init__(self, model_name: str = 'all-MiniLM-L6-v2'):
        logger.info("loading_embedding_model", model=model_name)
        self.embedding_model = SentenceTransformer(model_name)
        self.chunks = []
        self.chunk_embeddings = None
        self.metadata = {}
        logger.info("embedding_model_loaded")

    def index_document(self, content: Dict[str, Any], chunk_size: int = 400, overlap: int = 50) -> bool:

        self.chunks = []
        text = content.get("full_text", "")

        if not text or len(text.strip()) < 10:
            logger.warning("document_too_short")
            return False

        logger.info("indexing_document", chars=len(text))


        sentences = sent_tokenize(text)
        current_chunk = []
        current_length = 0

        for sentence in sentences:
            sentence_length = len(sentence.split())

            if current_length + sentence_length > chunk_size and current_chunk:
                chunk_text = " ".join(current_chunk)
                self.chunks.append({
                    "text": chunk_text,
                    "position": len(self.chunks),
                    "word_count": len(chunk_text.split())
                })


                overlap_sentences = current_chunk[-(overlap // 10):] if overlap > 0 else []
                current_chunk = overlap_sentences
                current_length = sum(len(s.split()) for s in overlap_sentences)

            current_chunk.append(sentence)
            current_length += sentence_length


        if current_chunk:
            chunk_text = " ".join(current_chunk)
            self.chunks.append({
                "text": chunk_text,
                "position": len(self.chunks),
                "word_count": len(chunk_text.split())
            })

        logger.info("document_split", chunks=len(self.chunks))


        if self.chunks:
            texts = [chunk["text"] for chunk in self.chunks]
            logger.info("generating_embeddings", chunks=len(texts))
            self.chunk_embeddings = self.embedding_model.encode(texts, show_progress_bar=False)
            self.metadata = content.get("metadata", {})
            logger.info("embeddings_generated")
            return True

        return False

    def search(self, query: str, top_k: int = 3, min_similarity: float = 0.3) -> List[Dict[str, Any]]:

        if self.chunk_embeddings is None or not self.chunks:
            logger.warning("no_indexed_chunks")
            return []

        logger.info("searching_query", query=query[:50])

        query_embedding = self.embedding_model.encode([query])[0]
        similarities = cosine_similarity([query_embedding], self.chunk_embeddings)[0]


        top_indices = np.argsort(similarities)[::-1]

        results = []
        for idx in top_indices:
            if similarities[idx] < min_similarity:
                break

            results.append({
                "text": self.chunks[idx]["text"],
                "relevance": float(similarities[idx]),
                "position": self.chunks[idx]["position"],
                "word_count": self.chunks[idx]["word_count"]
            })

            if len(results) >= top_k:
                break

        logger.info("search_complete", results=len(results))
        return results

    def generate_context(self, query: str, top_k: int = 3) -> str:

        results = self.search(query, top_k)

        if not results:
            return ""

        context = " ФРАГМЕНТЫ ДОКУМЕНТА:\n\n"
        for i, res in enumerate(results, 1):
            context += f"Фрагмент {i} (релевантность: {res['relevance']:.0%}):\n"
            context += f"{res['text']}\n"
            context += f"[Позиция: {res['position']}, Слов: {res['word_count']}]\n"
            context += "-" * 50 + "\n\n"

        return context.strip()

    def get_document_summary(self) -> Dict[str, Any]:

        return {
            "chunks_count": len(self.chunks),
            "total_words": sum(chunk["word_count"] for chunk in self.chunks) if self.chunks else 0,
            "indexed": self.chunk_embeddings is not None
        }