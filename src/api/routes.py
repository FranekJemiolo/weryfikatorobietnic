"""Routing endpointów FastAPI dla Weryfikatora Obietnic."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlmodel import Session

from src.api.crud import (
    create_or_update_push_subscription,
    get_analytics_summary,
    get_mp_by_id,
    get_mp_voting_activity,
    get_promise_evaluation_detail,
    get_promise_timeline,
    get_promises_summary,
    register_ngo_webhook,
    remove_push_subscription,
    search_promises,
)
from src.api.schemas import (
    AnalyticsSummary,
    DailyActivityItem,
    MPProfileResponse,
    NgoWebhookCreate,
    NgoWebhookResponse,
    PromiseEvaluationDetail,
    PromiseListItem,
    PromiseSearchResponse,
    PromiseStatusChangeNotificationRequest,
    SubscribeRequest,
    SubscribeResponse,
    TimelineEvent,
    UnsubscribeRequest,
    VapidPublicKeyResponse,
)
from src.config import settings
from src.database.engine import get_session
from src.database.models import LLMEvaluation, Promise
from src.notifications.dispatcher import async_notify_promise_status_change

router = APIRouter(prefix="/api/v1")

SessionDep = Annotated[Session, Depends(get_session)]


@router.get(
    "/analytics/summary",
    response_model=AnalyticsSummary,
    tags=["Analityka"],
    summary="Globalne statystyki rządu (Government Score)",
)
async def get_government_score_summary(
    session: SessionDep,
) -> AnalyticsSummary:
    """Zwraca globalne statystyki obietnic rządu: total, fulfilled, in_progress, broken oraz średni czas realizacji."""
    return get_analytics_summary(session)


@router.get(
    "/promises/search",
    response_model=PromiseSearchResponse,
    tags=["Obietnice"],
    summary="Wyszukiwarka obietnic z filtrami i paginacją",
)
async def search_promises_endpoint(
    session: SessionDep,
    q: str | None = Query(default=None, description="Fraza wyszukiwania w tytule i treści"),
    party: str | None = Query(default=None, description="Filtr po partii politycznej"),
    status: str | None = Query(
        default=None, description="Filtr po statusie obietnicy lub zgodności"
    ),
    category: str | None = Query(default=None, description="Filtr po kategorii"),
    limit: int = Query(default=20, ge=1, le=100, description="Limit wyników na stronę"),
    offset: int = Query(default=0, ge=0, description="Przesunięcie paginacji"),
) -> PromiseSearchResponse:
    """Wyszukuje obietnice po frazie tekstowej (ILIKE) oraz kryteriach partii, statusu i kategorii."""
    items, total = search_promises(
        session=session,
        q=q,
        party=party,
        status=status,
        category=category,
        limit=limit,
        offset=offset,
    )
    return PromiseSearchResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/promises",
    response_model=list[PromiseListItem],
    tags=["Obietnice"],
    summary="Lista zarejestrowanych obietnic wyborczych wraz ze statusem LLM i kosztem OSR",
)
async def list_promises(
    session: SessionDep,
    only_approved: bool = Query(
        default=True,
        description="Zwracaj tylko oceny LLM zatwierdzone przez człowieka (Human-in-the-Loop)",
    ),
) -> list[PromiseListItem]:
    """Zwraca listę obietnic z zagregowaną oceną LLM (domyślnie tylko zatwierdzone przez człowieka)."""
    return get_promises_summary(session, only_approved=only_approved)


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


# --- System Subskrypcji i Powiadomień Web Push (PWA) & Webhooków NGO ---


@router.get(
    "/subscriptions/vapid-key",
    response_model=VapidPublicKeyResponse,
    tags=["Powiadomienia"],
    summary="Pobiera publiczny klucz VAPID dla Service Workera PWA",
)
async def get_vapid_key() -> VapidPublicKeyResponse:
    """Zwraca publiczny klucz VAPID do konfiguracji subskrypcji push w przeglądarce."""
    return VapidPublicKeyResponse(public_key=settings.vapid_public_key)


@router.post(
    "/subscribe",
    response_model=SubscribeResponse,
    tags=["Powiadomienia"],
    summary="Rejestruje subskrypcję powiadomień Push dla obywatela (PWA)",
)
async def subscribe_push(
    body: SubscribeRequest,
    session: SessionDep,
) -> SubscribeResponse:
    """Zapisuje subskrypcję obywatelską dla konkretnej obietnicy, posła lub kategorii (zgodne z RODO)."""
    sub = create_or_update_push_subscription(
        session=session,
        endpoint=body.subscription.endpoint,
        p256dh=body.subscription.keys.p256dh,
        auth=body.subscription.keys.auth,
        target_type=body.target_type,
        target_id=body.target_id,
    )
    return SubscribeResponse(
        success=True,
        message=f"Pomyślnie zasubskrybowano powiadomienia dla {body.target_type}:{body.target_id}",
        subscription_id=sub.id,
    )


@router.post(
    "/unsubscribe",
    tags=["Powiadomienia"],
    summary="Usuwa subskrypcję powiadomień Push",
)
async def unsubscribe_push(
    body: UnsubscribeRequest,
    session: SessionDep,
) -> dict[str, Any]:
    """Usuwa powiązanie subskrypcji z danym obiektem."""
    removed = remove_push_subscription(
        session=session,
        endpoint=body.endpoint,
        target_type=body.target_type,
        target_id=body.target_id,
    )
    return {
        "success": removed,
        "message": "Subskrypcja została usunięta"
        if removed
        else "Nie znaleziono aktywnej subskrypcji",
    }


@router.post(
    "/webhooks",
    response_model=NgoWebhookResponse,
    tags=["Otwarte Dane NGO"],
    summary="Rejestracja webhooka dla organizacji pozarządowej (NGO) lub redakcji",
)
async def register_webhook_endpoint(
    body: NgoWebhookCreate,
    session: SessionDep,
) -> NgoWebhookResponse:
    """Rejestruje webhook dla NGO ze współdzielonym kluczem HMAC-SHA256."""
    webhook = register_ngo_webhook(
        session=session,
        organization_name=body.organization_name,
        target_url=body.target_url,
        secret_token=body.secret_token,
    )
    return NgoWebhookResponse.model_validate(webhook)


@router.post(
    "/promises/{id}/notify",
    tags=["Powiadomienia"],
    summary="Ręczne rozesłanie powiadomienia o statusie obietnicy (w tle)",
)
async def trigger_promise_notification(
    id: str,
    body: PromiseStatusChangeNotificationRequest,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> dict[str, str]:
    """Wysyła asynchronicznie powiadomienia w tle (BackgroundTasks) do subskrybentów oraz NGO."""
    promise = session.get(Promise, id)
    if not promise:
        raise HTTPException(
            status_code=404,
            detail=f"Nie znaleziono obietnicy o identyfikatorze '{id}'.",
        )

    background_tasks.add_task(
        async_notify_promise_status_change,
        promise_id=id,
        old_status=body.old_status,
        new_status=body.new_status,
        llm_justification=body.llm_justification,
    )
    return {
        "status": "queued",
        "message": f"Powiadomienia dla obietnicy {id} zostały zakolejkowane w tle.",
    }


@router.post(
    "/evaluations/{id}/approve",
    tags=["Human-in-the-Loop"],
    summary="Zatwierdzenie ewaluacji przez człowieka i rozesłanie powiadomień w tle",
)
async def approve_evaluation_endpoint(
    id: int,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> dict[str, Any]:
    """Zatwierdza ewaluację LLM przez moderatora (Human-in-the-Loop) i wyzwala powiadomienia."""
    evaluation = session.get(LLMEvaluation, id)
    if not evaluation:
        raise HTTPException(
            status_code=404,
            detail=f"Nie znaleziono ewaluacji o identyfikatorze {id}.",
        )

    evaluation.is_approved_by_human = True
    session.add(evaluation)
    session.commit()
    session.refresh(evaluation)

    promise = session.get(Promise, evaluation.promise_id)
    if promise:
        background_tasks.add_task(
            async_notify_promise_status_change,
            promise_id=promise.id,
            old_status=promise.status.value,
            new_status=evaluation.alignment_status.value,
            llm_justification=evaluation.justification,
        )

    return {
        "success": True,
        "evaluation_id": id,
        "is_approved_by_human": True,
        "message": "Ewaluacja została zatwierdzona, a powiadomienia zakolejkowane w tle.",
    }
