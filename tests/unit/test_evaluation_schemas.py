"""Testy jednostkowe schematów Pydantic dla ewaluacji LLM."""

import pytest
from pydantic import ValidationError

from src.evaluation.schemas import PromiseEvaluation, PromiseModel


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


def test_promise_evaluation_validation_success() -> None:
    """Weryfikuje poprawną walidację obiektu oceny LLM (Structured Outputs)."""
    result = PromiseEvaluation(
        promise_id="KO-100K-001",
        project_id="10-12",
        alignment_status="CZESCIOWO",
        justification="Projekt podnosi kwotę wolną, jednak wyłącznie dla przedsiębiorców.",
        divergence_details="Wyłączenie osób zatrudnionych na umowę o pracę.",
        confidence_score=0.85,
        evaluated_provisions=["Art. 2 ust. 1", "Art. 5"],
    )
    assert result.alignment_score == 50
    assert result.alignment_status == "CZESCIOWO"
    assert result.requires_manual_review is False


def test_promise_evaluation_confidence_score_bounds() -> None:
    """Sprawdza, czy confidence_score odrzuca wartości spoza zakresu 0.0 - 1.0."""
    with pytest.raises(ValidationError):
        PromiseEvaluation(
            promise_id="P-01",
            project_id="10-1",
            alignment_status="W_PELNI",
            justification="Błędny wynik",
            confidence_score=1.5,  # Powyżej 1.0
        )

    with pytest.raises(ValidationError):
        PromiseEvaluation(
            promise_id="P-01",
            project_id="10-1",
            alignment_status="W_PELNI",
            justification="Błędny wynik",
            confidence_score=-0.2,  # Poniżej 0.0
        )


def test_promise_evaluation_manual_review_threshold() -> None:
    """Weryfikuje automatyczne flagowanie rekordu o niskiej pewności (< 0.70)."""
    low_conf = PromiseEvaluation(
        promise_id="P-02",
        project_id="10-2",
        alignment_status="CZESCIOWO",
        justification="Niejednoznaczne przepisy; możliwe różne interpretacje.",
        confidence_score=0.62,
    )
    assert low_conf.requires_manual_review is True
