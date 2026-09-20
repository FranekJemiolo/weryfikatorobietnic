"""Testy jednostkowe schematów Pydantic dla ewaluacji LLM."""

import pytest
from pydantic import ValidationError

from src.evaluation.schemas import AlignmentStatus, EvaluationResult, PromiseModel


def test_promise_model_valid() -> None:
    """Weryfikuje poprawną walidację obietnicy wyborczej."""
    promise = PromiseModel(
        promise_id="KO-100K-001",
        party_id="KO",
        category="Podatki",
        title="Kwota wolna od podatku 60 tys. zł",
        raw_text="Podniesiemy kwotę wolną od podatku do 60 tysięcy złotych.",
        source_document="100_konkretow.pdf",
        quantifiable_metrics={"kwota_pln": 60000},
    )
    assert promise.promise_id == "KO-100K-001"
    assert promise.quantifiable_metrics["kwota_pln"] == 60000


def test_evaluation_result_validation_success() -> None:
    """Weryfikuje poprawną walidację obiektu oceny LLM."""
    result = EvaluationResult(
        summary_pl="Projekt podnosi kwotę wolną, jednak wyłącznie dla przedsiębiorców.",
        alignment_status=AlignmentStatus.CZESCIOWO_ZREALIZOWANA,
        alignment_score=45,
        divergence_analysis="Wyłączenie osób zatrudnionych na umowę o pracę.",
        budget_impact_summary="Szacowany koszt dla budżetu: 15 mld PLN.",
        evaluated_provisions=["Art. 2 ust. 1", "Art. 5"],
    )
    assert result.alignment_score == 45
    assert result.alignment_status == AlignmentStatus.CZESCIOWO_ZREALIZOWANA


def test_evaluation_result_score_bounds() -> None:
    """Sprawdza, czy alignment_score odrzuca wartości spoza zakresu 0-100."""
    with pytest.raises(ValidationError):
        EvaluationResult(
            summary_pl="Błędny wynik",
            alignment_status=AlignmentStatus.W_PELNI_ZREALIZOWANA,
            alignment_score=150,  # Powyżej 100
        )

    with pytest.raises(ValidationError):
        EvaluationResult(
            summary_pl="Błędny wynik",
            alignment_status=AlignmentStatus.W_PELNI_ZREALIZOWANA,
            alignment_score=-5,  # Poniżej 0
        )
