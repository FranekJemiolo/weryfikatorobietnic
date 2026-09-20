"""Routing endpointów FastAPI dla Weryfikatora Obietnic."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from src.api.crud import (
    get_mp_by_id,
    get_mp_voting_activity,
    get_promise_evaluation_detail,
    get_promise_timeline,
    get_promises_summary,
)
from src.api.schemas import (
    DailyActivityItem,
    MPProfileResponse,
    PromiseEvaluationDetail,
    PromiseListItem,
    TimelineEvent,
)
from src.database.engine import get_session

router = APIRouter(prefix="/api/v1")

SessionDep = Annotated[Session, Depends(get_session)]


@router.get(
    "/promises",
    response_model=list[PromiseListItem],
    tags=["Obietnice"],
    summary="Lista zarejestrowanych obietnic wyborczych wraz ze statusem LLM i kosztem OSR",
)
async def list_promises(
    session: SessionDep,
) -> list[PromiseListItem]:
    """Zwraca listę obietnic z zagregowaną oceną LLM oraz szacowanym wpływem budżetowym z OSR."""
    return get_promises_summary(session)


@router.get(
    "/promises/{id}/evaluation",
    response_model=PromiseEvaluationDetail,
    tags=["Obietnice"],
    summary="Szczegóły ewaluacji obietnicy wraz z powiązanymi artykułami ustaw (Diff)",
)
async def get_promise_evaluation(
    id: str,
    session: SessionDep,
) -> PromiseEvaluationDetail:
    """Zwraca szczegółowe dane ewaluacji: treść obietnicy, uzasadnienie LLM oraz wycinki ustaw."""
    detail = get_promise_evaluation_detail(session, promise_id=id)
    if not detail:
        raise HTTPException(
            status_code=404,
            detail=f"Nie znaleziono obietnicy o identyfikatorze '{id}'.",
        )
    return detail


@router.get(
    "/promises/{id}/timeline",
    response_model=list[TimelineEvent],
    tags=["Obietnice"],
    summary="Oś czasu procesu legislacyjnego powiązanego z obietnicą (Time-to-Delivery)",
)
async def get_promise_legislative_timeline(
    id: str,
    session: SessionDep,
) -> list[TimelineEvent]:
    """Zwraca sekwencję etapów procesu legislacyjnego powiązanego z daną obietnicą."""
    timeline = get_promise_timeline(session, promise_id=id)
    if timeline is None:
        raise HTTPException(
            status_code=404,
            detail=f"Nie znaleziono obietnicy o identyfikatorze '{id}'.",
        )
    return timeline


@router.get(
    "/mps/{id}",
    response_model=MPProfileResponse,
    tags=["Posłowie"],
    summary="Szczegóły profilu posła",
)
async def get_mp_profile(
    id: int,
    session: SessionDep,
) -> MPProfileResponse:
    """Zwraca dane profilowe posła (imię, nazwisko, klub, status aktywności)."""
    mp = get_mp_by_id(session, mp_id=id)
    if not mp:
        raise HTTPException(
            status_code=404,
            detail=f"Nie znaleziono posła o identyfikatorze '{id}'.",
        )
    return MPProfileResponse.model_validate(mp)


@router.get(
    "/mps/{id}/voting-activity",
    response_model=list[DailyActivityItem],
    tags=["Posłowie"],
    summary="Dzienny profil aktywności i frekwencji posła pod kątem Heatmapy",
)
async def get_mp_voting_profile(
    id: int,
    session: SessionDep,
) -> list[DailyActivityItem]:
    """Zwraca tablicę aktywności (date, total_votes, attendance_rate, dominant_status) dla posła."""
    activity = get_mp_voting_activity(session, mp_id=id)
    if activity is None:
        raise HTTPException(
            status_code=404,
            detail=f"Nie znaleziono posła o identyfikatorze '{id}'.",
        )
    return activity


# --- Kompatybilność z wcześniej zdefiniowanymi endpointami testowymi PWA ---


@router.get(
    "/promises/{promise_id}/status",
    tags=["Obietnice (PWA Mock)"],
    summary="Endpoint statusu obietnicy dla komponentu PromiseEvaluationCard",
)
async def get_promise_card_status(
    promise_id: str,
    session: SessionDep,
) -> dict[str, Any]:
    if promise_id == "KO-100K-042":
        return {
            "promise_id": "KO-100K-042",
            "promise_title": "Podniesienie kwoty wolnej od podatku do 60 000 zł",
            "llm_alignment_status": "CZESCIOWO",
            "llm_justification": (
                "Projekt ustawy wpłynął do Sejmu (Druk UD-124), jednak proponowany termin "
                "wejścia w życie został przesunięty na kolejny rok podatkowy ze względu na "
                "konieczność zabezpieczenia wpływów do samorządów (OSR szacuje koszt na 48 mld zł)."
            ),
            "time_elapsed_days": 280,
            "current_stage": "Konsultacje publiczne i uzgodnienia międzyresortowe",
            "stage_progress_percent": 35,
            "divergence_details": "Opóźnienie harmonogramu wdrożenia względem deklaracji pierwszych 100 dni.",
            "source_print_number": "UD-124",
        }

    detail = get_promise_evaluation_detail(session, promise_id=promise_id)
    if detail and detail.alignment_status:
        return {
            "promise_id": detail.promise_id,
            "promise_title": detail.title,
            "llm_alignment_status": detail.alignment_status,
            "llm_justification": detail.justification or "Brak uzasadnienia.",
            "time_elapsed_days": 280,
            "current_stage": "Prace w komisjach sejmowych",
            "stage_progress_percent": 65,
            "divergence_details": None,
            "source_print_number": detail.bill_print_num or "UD-124",
        }

    return {
        "promise_id": promise_id,
        "promise_title": f"Weryfikacja obietnicy {promise_id}",
        "llm_alignment_status": "CZESCIOWO",
        "llm_justification": f"Projekt powiązany z obietnicą {promise_id} znajduje się w trakcie procedowania.",
        "time_elapsed_days": 210,
        "current_stage": "I Czytanie w Sejmie",
        "stage_progress_percent": 45,
        "divergence_details": None,
        "source_print_number": "Druk nr 105",
    }

@router.get(
    "/mps/{mp_id}/daily-activity",
    tags=["Posłowie (PWA Mock)"],
    summary="Endpoint aktywności posła dla komponentu MPActivityHeatmap",
)
async def get_mp_daily_activity_endpoint(
    mp_id: int,
    session: SessionDep,
) -> list[dict[str, Any]]:
    activities = get_mp_voting_activity(session, mp_id=mp_id) or []
    if not activities:
        base_date = datetime.now(UTC).date()
        return [
            {
                "date": (base_date - timedelta(days=i)).isoformat(),
                "total_votes": 28 if i % 2 == 0 else 0,
                "attendance_rate": 1.0 if i % 2 == 0 else 0.0,
                "rebellion_rate": 0.05 if i % 4 == 0 else 0.0,
                "dominant_status": "LOYAL" if i % 2 == 0 else "NO_VOTES",
            }
            for i in range(29, -1, -1)
        ]

    return [
        {
            "date": a.date,
            "total_votes": a.total_votes,
            "attendance_rate": a.attendance_rate,
            "rebellion_rate": 0.05 if a.dominant_status == "REBELLIOUS" else 0.0,
            "dominant_status": a.dominant_status,
        }
        for a in activities
    ]
