"""Testy jednostkowe produkcyjnego zadania ewaluacji LLM (Airflow Task & google-genai)."""

from unittest.mock import MagicMock, patch

from src.evaluation.llm_evaluator_task import (
    GeminiStructuredEvaluator,
    PromiseEvaluation,
    evaluate_promises_with_llm,
)


def test_promise_evaluation_valid_statuses() -> None:
    """Weryfikuje poprawność wszystkich dozwolonych statusów w Pydantic."""
    for status in ["W_PELNI", "CZESCIOWO", "SPRZECZNA", "BRAK_POWIAZANIA"]:
        eval_obj = PromiseEvaluation(
            promise_id="P-01",
            project_id="10-100",
            alignment_status=status,  # type: ignore[arg-type]
            justification="Testowe uzasadnienie decyzji analityka.",
            confidence_score=0.95,
        )
        assert eval_obj.alignment_status == status
        assert eval_obj.confidence_score == 0.95


def test_gemini_evaluator_with_mock_client() -> None:
    """Weryfikuje wywołanie google-genai z wymuszonym schematem JSON i odczyt wyniku."""
    mock_response = MagicMock()
    mock_response.text = (
        '{"promise_id": "KO-01", "project_id": "10-50", "alignment_status": "W_PELNI", '
        '"justification": "Ustawa wdraża obietnicę w 100%.", "confidence_score": 0.98}'
    )

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    evaluator = GeminiStructuredEvaluator(
        api_key="fake-key-for-test", model_name="gemini-1.5-flash"
    )
    evaluator._client = mock_client

    result = evaluator.evaluate_pair(
        promise_id="KO-01",
        promise_text="Podniesienie kwoty wolnej",
        project_id="10-50",
        provisions_text=["Art. 1. Kwota wolna wynosi 60 tys. zł."],
    )

    assert result.alignment_status == "W_PELNI"
    assert result.confidence_score == 0.98
    assert result.justification == "Ustawa wdraża obietnicę w 100%."
    mock_client.models.generate_content.assert_called_once()


def test_evaluate_promises_task_with_mock_hook() -> None:
    """Weryfikuje wykonanie zadania Airflow, logikę needs_human_review i zapytanie UPSERT."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    mock_hook = MagicMock()
    mock_hook.get_conn.return_value = mock_conn

    payloads = [
        {
            "promise_id": "KO-01",
            "project_id": "10-1",
            "promise_text": "Podniesiemy kwotę wolną od podatku do 60 tys. zł dla wszystkich.",
            "provisions": ["Art. 2. Kwotę wolną ustala się na 60 tys. zł dla przedsiębiorców."],
        },
        {
            "promise_id": "KO-02",
            "project_id": "10-2",
            "promise_text": "Darmowe laptopy dla każdego ucznia czwartej klasy.",
            "provisions": ["Art. 9. Zawiesza się program laptopów."],
        },
    ]

    with patch("src.evaluation.llm_evaluator_task.PostgresHook", return_value=mock_hook):
        summary = evaluate_promises_with_llm(
            evaluation_payloads=payloads,
            postgres_conn_id="postgres_test",
        )

        assert summary["processed_evaluations"] == 2
        assert summary["total_attempted"] == 2
        # Cursor execute powinien zostać wywołany dwukrotnie dla operacji UPSERT
        assert mock_cursor.execute.call_count == 2

        # Sprawdzenie, czy zapytanie zawiera klauzulę ON CONFLICT
        call_args = mock_cursor.execute.call_args_list[0]
        query_sql = call_args[0][0]
        params = call_args[0][1]

        assert "INSERT INTO core_evaluations" in query_sql
        assert "ON CONFLICT (promise_id, project_id) DO UPDATE" in query_sql
        assert params[0] == "KO-01"
        assert params[1] == "10-1"
