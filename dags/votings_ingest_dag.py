"""DAG Apache Airflow: Wsadowa ingestia wyników głosowań sejmowych i powiązań imiennych.

Pobiera strukturę posiedzeń, listę głosowań oraz kaskadowo głosy imienne każdego posła.
Zasila tabelę główną parliamentary_votings oraz relację n:m parliamentary_mp_votes.
"""

from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

try:
    from airflow.decorators import dag, task
except ImportError:

    class MockTask:
        def __init__(self, name: str) -> None:
            self.name = name

        def __rshift__(self, other: Any) -> Any:
            return other

        def __lshift__(self, other: Any) -> Any:
            return other

    def dag(*args: Any, **kwargs: Any):  # type: ignore[no-redef]
        def decorator(f: Any) -> Any:
            return f

        return decorator

    def task(*args: Any, **kwargs: Any):  # type: ignore[no-redef]
        def decorator(f: Any) -> Any:
            def wrapper(*call_args: Any, **call_kwargs: Any) -> MockTask:
                return MockTask(f.__name__)

            wrapper.__name__ = f.__name__
            wrapper.__doc__ = f.__doc__
            return wrapper

        return decorator


from psycopg.types.json import Jsonb

from src.collectors.sejm_api import SejmClient
from src.config import settings
from src.core.database import db_manager
from src.models.sejm_api import SejmSingleMPVoteRaw, SejmVotingRaw


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    reraise=True,
)
def fetch_voting_with_retry(
    client: SejmClient, sitting: int, voting_num: int, term: int
) -> dict[str, Any]:
    """Pobiera imienny protokół głosowania z mechanizmem retry."""
    return client.get_voting_details(sitting=sitting, voting_number=voting_num, term=term)


@dag(
    dag_id="votings_ingest_dag",
    schedule_interval="0 2 * * *",  # Raz dziennie w nocy (batch po posiedzeniach)
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["sejm", "votings", "mp", "accountability"],
    doc_md=__doc__,
)
def votings_ingestion_pipeline() -> None:
    """Potok orkiestracji pobierający i normalizujący imienne wyniki głosowań sejmowych."""

    @task(task_id="discover_votings_to_sync")
    def discover_votings_to_sync() -> list[dict[str, Any]]:
        """Wykrywa listę głosowań do zsynchronizowania dla bieżącej kadencji."""
        client = SejmClient()
        term = settings.default_sejm_term

        # Pobieramy ostatnie głosowania z Sejm API
        endpoint = f"term{term}/votings"
        try:
            recent_votings = client._get(endpoint)
        except Exception:
            return []

        if not isinstance(recent_votings, list):
            return []

        votings_summary: list[dict[str, Any]] = []
        for item in recent_votings[:50]:  # Limit do 50 najnowszych posiedzeń/głosowań
            sitting = item.get("sitting")
            voting_num = item.get("votingNumber")
            if sitting and voting_num:
                votings_summary.append(
                    {
                        "term": term,
                        "sitting": int(sitting),
                        "voting_number": int(voting_num),
                        "voting_id": f"{term}-{sitting}-{voting_num}",
                    }
                )

        return votings_summary

    @task(task_id="ingest_voting_details_and_mp_votes")
    def ingest_voting_details_and_mp_votes(votings: list[dict[str, Any]]) -> dict[str, int]:
        """Pobiera głosy imienne i zapisuje strukturę n:m (voting_id <-> mp_id <-> vote_type)."""
        client = SejmClient()
        inserted_votings = 0
        inserted_mp_votes = 0

        for v in votings:
            term = v["term"]
            sitting = v["sitting"]
            voting_num = v["voting_number"]
            voting_id = v["voting_id"]

            try:
                raw_data = fetch_voting_with_retry(client, sitting, voting_num, term)
                validated_voting = SejmVotingRaw.model_validate(raw_data)

                # 1. Zapis surowego ładunku do warstwy stagingowej
                db_manager.insert_raw_sejm_record(
                    endpoint="votings",
                    term=term,
                    external_id=voting_id,
                    payload=raw_data,
                )

                # 2. Zapis rekordu głosowania do tabeli parliamentary_votings
                voting_query = """
                    INSERT INTO parliamentary_votings (
                        voting_id, term, sitting, voting_number, date, title, topic,
                        total_voted, votes_yes, votes_no, votes_abstain, votes_absent, mp_votes
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (voting_id) DO UPDATE SET
                        title = EXCLUDED.title,
                        topic = EXCLUDED.topic,
                        total_voted = EXCLUDED.total_voted,
                        votes_yes = EXCLUDED.votes_yes,
                        votes_no = EXCLUDED.votes_no,
                        votes_abstain = EXCLUDED.votes_abstain,
                        votes_absent = EXCLUDED.votes_absent,
                        mp_votes = EXCLUDED.mp_votes;
                """
                with db_manager.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            voting_query,
                            (
                                voting_id,
                                term,
                                sitting,
                                voting_num,
                                validated_voting.date,
                                validated_voting.title,
                                validated_voting.topic,
                                validated_voting.total_voted,
                                validated_voting.yes,
                                validated_voting.no,
                                validated_voting.abstain,
                                validated_voting.not_participating,
                                Jsonb([vote.model_dump() for vote in validated_voting.votes]),
                            ),
                        )

                        # 3. Zapis relacji n:m do parliamentary_mp_votes
                        mp_vote_query = """
                            INSERT INTO parliamentary_mp_votes (
                                voting_id, mp_id, mp_name, club, vote_type
                            )
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (voting_id, mp_id) DO UPDATE SET
                                mp_name = EXCLUDED.mp_name,
                                club = EXCLUDED.club,
                                vote_type = EXCLUDED.vote_type;
                        """
                        for vote_item in validated_voting.votes:
                            vote_model = SejmSingleMPVoteRaw.model_validate(vote_item)
                            cur.execute(
                                mp_vote_query,
                                (
                                    voting_id,
                                    vote_model.mp_id,
                                    vote_model.first_last_name or f"Poseł #{vote_model.mp_id}",
                                    vote_model.club or "NIEZRZESZONY",
                                    vote_model.normalized_vote().value,
                                ),
                            )
                            inserted_mp_votes += 1

                    conn.commit()
                inserted_votings += 1
            except Exception:
                continue

        return {
            "synced_votings": inserted_votings,
            "synced_individual_votes": inserted_mp_votes,
        }

    discovered = discover_votings_to_sync()
    ingest_voting_details_and_mp_votes(discovered)


votings_dag = votings_ingestion_pipeline()
