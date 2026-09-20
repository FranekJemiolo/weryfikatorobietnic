"""Moduł generowania embeddingów wektorowych oraz wyszukiwania semantycznego (RAG).

Obsługuje generowanie wektorów semantycznych dla artykułów ustaw i obietnic wyborczych,
kalkulację podobieństwa kosinusowego oraz selekcję Top-K relewantnych przepisów dla modelu LLM.
"""

import hashlib
import math

import httpx

from src.config import settings
from src.parsers.legal_parser import ParsedProvision


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Oblicza podobieństwo kosinusowe pomiędzy dwoma wektorami wielowymiarowymi.

    Args:
        vec_a: Pierwszy wektor zmiennoprzecinkowy.
        vec_b: Drugi wektor zmiennoprzecinkowy.

    Returns:
        float: Wartość z przedziału [-1.0, 1.0].
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot_product / (norm_a * norm_b)


class EmbeddingService:
    """Usługa generująca embeddingi wektorowe dla tekstów prawnych i obietnic."""

    def __init__(self, dimension: int = 384) -> None:
        """Inicjalizuje serwis embeddingów.

        Args:
            dimension: Wymiar wektora (domyślnie 384 dla lekkich modeli wielojęzycznych).
        """
        self._dim = dimension
        self._gemini_api_key = settings.gemini_api_key
        self._openai_api_key = settings.openai_api_key

    def get_embedding(self, text: str) -> list[float]:
        """Generuje wektor embeddingu dla pojedynczego fragmentu tekstu.

        Jeśli skonfigurowano klucz zewnętrznego API (np. OpenAI / Gemini), odpytuje endpoint.
        W przeciwnym wypadku generuje deterministyczny, znormalizowany wektor cech leksykalnych.

        Args:
            text: Tekst źródłowy.

        Returns:
            list[float]: Znormalizowany wektor embeddingu.
        """
        if self._openai_api_key:
            return self._call_openai_embeddings(text)
        return self._generate_local_fallback_embedding(text)

    def get_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generuje wektory dla listy tekstów w sposób wsadowy."""
        return [self.get_embedding(t) for t in texts]

    def _call_openai_embeddings(self, text: str) -> list[float]:
        """Odpytuje endpoint text-embedding-3-small OpenAI."""
        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {self._openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"input": text[:8000], "model": "text-embedding-3-small"}
        try:
            with httpx.Client(timeout=15) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return list(data["data"][0]["embedding"])
        except Exception:
            return self._generate_local_fallback_embedding(text)

    def _generate_local_fallback_embedding(self, text: str) -> list[float]:
        """Generuje deterministyczny, znormalizowany wektor cech leksykalnych.

        Używany w środowiskach bez kluczy API, testach jednostkowych i CI/CD.
        """
        words = [w.lower().strip(".,!?:;\"'()[]{}") for w in text.split()]
        vector = [0.0] * self._dim

        for word in words:
            if not word:
                continue
            # Haszowanie słowa do indeksu i wagi
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dim
            sign = 1.0 if ((h >> 8) & 1) else -1.0
            vector[idx] += sign

        # Normalizacja L2 do jednostkowej długości
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector


class RAGMatcher:
    """Silnik dopasowania semantycznego obietnic wyborczych z artykułami ustaw."""

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        """Inicjalizuje moduł RAG.

        Args:
            embedding_service: Opcjonalna instancja serwisu embeddingów.
        """
        self._embedder = embedding_service or EmbeddingService()

    def select_top_relevant_provisions(
        self,
        promise_text: str,
        provisions: list[ParsedProvision],
        top_k: int = 5,
        min_similarity_threshold: float = 0.05,
    ) -> list[tuple[ParsedProvision, float]]:
        """Wyszukuje najbardziej relewantne artykuły ustawy dla podanej obietnicy wyborczej.

        Args:
            promise_text: Tekst deklaracji/obietnicy wyborczej.
            provisions: Lista wyodrębnionych przepisów ustawy.
            top_k: Maksymalna liczba artykułów przekazywanych do kontekstu LLM.
            min_similarity_threshold: Minimalny próg podobieństwa kosinusowego.

        Returns:
            list[tuple[ParsedProvision, float]]: Posortowana malejąco lista par (przepis, podobieństwo).
        """
        if not provisions:
            return []

        promise_vector = self._embedder.get_embedding(promise_text)
        scored_provisions: list[tuple[ParsedProvision, float]] = []

        for prov in provisions:
            # Łączymy ścieżkę kontekstową z tekstem artykułu
            combined_text = f"{prov.context_path}: {prov.text}"
            prov_vector = self._embedder.get_embedding(combined_text)
            similarity = cosine_similarity(promise_vector, prov_vector)

            if similarity >= min_similarity_threshold:
                scored_provisions.append((prov, similarity))

        # Sortowanie malejąco po podobieństwie
        scored_provisions.sort(key=lambda x: x[1], reverse=True)
        return scored_provisions[:top_k]
