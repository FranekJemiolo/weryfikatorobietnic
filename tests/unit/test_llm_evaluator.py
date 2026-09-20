"""Testy jednostkowe modułu LLMEvaluator (Structured Outputs)."""

from src.evaluation.llm_client import LLMEvaluator
from src.evaluation.schemas import PromiseEvaluation
from src.parsers.legal_parser import ParsedProvision


def test_llm_evaluator_no_provisions() -> None:
    """Weryfikuje zachowanie ewaluatora w przypadku braku pasujących przepisów."""
    evaluator = LLMEvaluator()
    result = evaluator.evaluate(
        promise_id="P-01",
        promise_text="Wprowadzenie zerowego VAT na żywność",
        project_id="10-1",
        provisions=[],
    )

    assert isinstance(result, PromiseEvaluation)
    assert result.alignment_status == "BRAK_POWIAZANIA"
    assert result.alignment_score == 0
    assert result.confidence_score == 1.0
    assert result.requires_manual_review is False


def test_llm_evaluator_heuristic_full_match() -> None:
    """Sprawdza klasyfikację pełnej realizacji obietnicy."""
    evaluator = LLMEvaluator()
    provisions = [
        ParsedProvision(
            article="Art. 2",
            text="Podnosi się kwotę wolną od podatku dochodowego do sumy 60 tys. zł dla wszystkich pracujących.",
            context_path="Rozdział 1 > Art. 2",
        )
    ]
    result = evaluator.evaluate(
        promise_id="KO-01",
        promise_text="Podniesiemy kwotę wolną od podatku do 60 tys. zł dla wszystkich pracujących.",
        project_id="10-45",
        provisions=provisions,
    )

    assert result.alignment_status == "W_PELNI"
    assert result.alignment_score == 100
    assert result.confidence_score >= 0.70
    assert result.requires_manual_review is False


def test_llm_evaluator_heuristic_partial_match_with_exclusion() -> None:
    """Sprawdza wykrywanie wyłączeń i status CZESCIOWO z obniżoną oceną."""
    evaluator = LLMEvaluator()
    provisions = [
        ParsedProvision(
            article="Art. 5",
            text="Podnosi się kwotę wolną od podatku do 60 tys. zł z wyjątkiem osób zatrudnionych na umowę o pracę.",
            context_path="Rozdział 2 > Art. 5",
        )
    ]
    result = evaluator.evaluate(
        promise_id="KO-02",
        promise_text="Podniesiemy kwotę wolną od podatku do 60 tys. zł dla wszystkich.",
        project_id="10-88",
        provisions=provisions,
    )

    assert result.alignment_status == "CZESCIOWO"
    assert result.alignment_score == 50
    assert result.divergence_details is not None
    assert "wyłączające" in result.divergence_details or "klauzule" in result.divergence_details
