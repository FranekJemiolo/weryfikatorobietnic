"""Testy integralności definicji DAG-ów Apache Airflow."""

import importlib

import pytest


@pytest.mark.parametrize(
    "dag_module_name",
    [
        "dags.system_healthcheck_dag",
        "dags.sejm_ingest_dag",
        "dags.votings_ingest_dag",
        "dags.party_watchdog_dag",
        "dags.llm_evaluation_dag",
        "dags.document_processing_dag",
        "dags.evaluation_dag",
        "dags.isap_sync_dag",
    ],
)
def test_dag_import_and_integrity(dag_module_name: str) -> None:
    """Sprawdza, czy każdy zdefiniowany DAG importuje się bezbłędnie i nie zawiera błędów składniowych."""
    module = importlib.import_module(dag_module_name)
    assert module is not None
