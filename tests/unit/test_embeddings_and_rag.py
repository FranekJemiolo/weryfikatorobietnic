"""Testy jednostkowe modułu RAGMatcher i obliczania podobieństwa wektorowego."""

from src.evaluation.embeddings import EmbeddingService, RAGMatcher, cosine_similarity
from src.parsers.legal_parser import ParsedProvision


def test_cosine_similarity_edge_cases() -> None:
    """Weryfikuje matematyczną poprawność podobieństwa kosinusowego."""
    # Identyczne wektory
    assert abs(cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0]) - 1.0) < 1e-6
    # Prostopadłe wektory
    assert abs(cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-6
    # Puste lub niezgodne wymiary
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0


def test_embedding_service_deterministic_output() -> None:
    """Sprawdza powtarzalność generowanych embeddingów lokalnych."""
    service = EmbeddingService(dimension=64)
    text = "Podniesienie kwoty wolnej od podatku"
    v1 = service.get_embedding(text)
    v2 = service.get_embedding(text)

    assert len(v1) == 64
    assert v1 == v2


def test_rag_matcher_top_k_selection() -> None:
    """Weryfikuje poprawne wyłanianie najbardziej relewantnych artykułów."""
    provisions = [
        ParsedProvision(
            article="Art. 1",
            text="Ustawa określa zadania Krajowej Administracji Skarbowej.",
            context_path="Rozdział 1 > Art. 1",
        ),
        ParsedProvision(
            article="Art. 21",
            text="Podnosi się kwotę wolną od podatku dochodowego do sumy 60000 zł rocznie.",
            context_path="Rozdział 3: Podatek Dochodowy > Art. 21",
        ),
        ParsedProvision(
            article="Art. 99",
            text="Traci moc ustawa o opłatach abonamentowych za radioodbiorniki.",
            context_path="Rozdział 9: Przepisy Końcowe > Art. 99",
        ),
    ]

    matcher = RAGMatcher()
    promise = "Podniesiemy kwotę wolną od podatku do 60 tysięcy złotych."
    top_matches = matcher.select_top_relevant_provisions(promise, provisions, top_k=1)

    assert len(top_matches) == 1
    best_provision, score = top_matches[0]
    assert best_provision.article == "Art. 21"
    assert score > 0.0
