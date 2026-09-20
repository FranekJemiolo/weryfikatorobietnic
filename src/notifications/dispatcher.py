"""Silnik powiadomień Web Push (PWA) oraz webhooków dla organizacji NGO i dziennikarzy.

Moduł odpowiada za:
1. Identyfikację obywateli subskrybujących daną obietnicę lub kategorię (zgodność z RODO / brak PII).
2. Wysyłkę powiadomień Web Push w standardzie PWA za pomocą biblioteki pywebpush w tle.
3. Bezpieczne rozsyłanie zdarzeń do zarejestrowanych NgoWebhook z weryfikacją sygnatury HMAC-SHA256.
"""

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]
from sqlmodel import Session, select

from src.config import settings
from src.database.engine import get_engine
from src.database.models import (
    CitizenSubscription,
    NgoWebhook,
    Promise,
    PushSubscriber,
    SubscriptionTargetType,
)

logger = logging.getLogger("src.notifications.dispatcher")


def generate_hmac_signature(secret: str, payload_bytes: bytes) -> str:
    """Generuje heksadecymalny podpis kryptograficzny HMAC-SHA256 dla ładunku webhooka."""
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def send_single_push(
    endpoint: str,
    p256dh: str,
    auth: str,
    payload_str: str,
    vapid_private_key: str,
    vapid_claims_sub: str,
) -> bool:
    """Synchroniczny pojedynczy strzał Web Push za pomocą pywebpush (wykonywany w wątku roboczym)."""
    sub_info = {
        "endpoint": endpoint,
        "keys": {
            "p256dh": p256dh,
            "auth": auth,
        },
    }
    try:
        webpush(
            subscription_info=sub_info,
            data=payload_str,
            vapid_private_key=vapid_private_key,
            vapid_claims={"sub": vapid_claims_sub},
            ttl=86400,
            timeout=10,
        )
        return True
    except WebPushException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        if status_code in (404, 410):
            logger.info(
                "Subskrypcja Push wygasła w przeglądarce (HTTP %s): %s", status_code, endpoint
            )
        else:
            logger.warning("Błąd pywebpush dla %s: %s", endpoint, exc)
        return False
    except Exception as exc:
        logger.warning("Nieoczekiwany błąd wysyłki push do %s: %s", endpoint, exc)
        return False


async def send_push_notification(
    subscriber: PushSubscriber,
    payload: dict[str, Any],
    session: Session | None = None,
) -> bool:
    """Asynchroniczne wysłanie powiadomienia Web Push do subskrybenta z automatycznym czyszczeniem wygasłych tokenów."""
    payload_str = json.dumps(payload, ensure_ascii=False)
    success = await asyncio.to_thread(
        send_single_push,
        subscriber.endpoint_url,
        subscriber.p256dh_key,
        subscriber.auth_key,
        payload_str,
        settings.vapid_private_key,
        settings.vapid_claims_email,
    )

    if not success and session is not None:
        # Usuń martwego subskrybenta z bazy, aby nie wysyłać kolejnych nieudanych requestów
        try:
            db_sub = session.get(PushSubscriber, subscriber.id)
            if db_sub:
                session.delete(db_sub)
                session.commit()
                logger.info("Usunięto nieaktywnego subskrybenta Push ID=%s", subscriber.id)
        except Exception as err:
            logger.error("Błąd podczas usuwania martwego subskrybenta: %s", err)

    return success


async def send_ngo_webhook(
    webhook: NgoWebhook,
    payload: dict[str, Any],
    client: httpx.AsyncClient | None = None,
) -> bool:
    """Asynchroniczne wysłanie ładunku JSON do NGO z nagłówkiem HMAC-SHA256."""
    payload_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    signature = generate_hmac_signature(webhook.secret_token, payload_bytes)

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "WeryfikatorObietnic-Webhook/1.0 (+https://weryfikatorobietnic.pl)",
        "X-Hub-Signature-256": f"sha256={signature}",
        "X-Signature-SHA256": signature,
        "X-Event-Type": "promise.status_changed",
    }

    own_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=8.0)
        own_client = True

    try:
        response = await client.post(webhook.target_url, content=payload_bytes, headers=headers)
        if response.is_success:
            logger.info(
                "Pomyślnie dostarczono webhook do NGO '%s' (%s): HTTP %s",
                webhook.organization_name,
                webhook.target_url,
                response.status_code,
            )
            return True
        logger.warning(
            "Webhook do NGO '%s' zwrócił błąd HTTP %s: %s",
            webhook.organization_name,
            response.status_code,
            response.text[:200],
        )
        return False
    except Exception as exc:
        logger.warning(
            "Nieudane połączenie z webhookiem NGO '%s' (%s): %s",
            webhook.organization_name,
            webhook.target_url,
            exc,
        )
        return False
    finally:
        if own_client:
            await client.aclose()


async def async_notify_promise_status_change(
    promise_id: str,
    old_status: str,
    new_status: str,
    llm_justification: str,
    session: Session | None = None,
) -> dict[str, int]:
    """Asynchroniczny dispatcher rozsyłający zdarzenie zmiany statusu obietnicy do obywateli (Push) oraz NGO (Webhooki)."""
    close_session = False
    if session is None:
        session = Session(get_engine())
        close_session = True

    try:
        promise = session.get(Promise, promise_id)
        promise_title = promise.title if promise else f"Obietnica {promise_id}"
        promise_category = promise.category if promise else ""

        # 1. Identyfikacja subskrybentów danej obietnicy lub jej kategorii
        stmt = (
            select(PushSubscriber)
            .join(CitizenSubscription)
            .where(
                (
                    (CitizenSubscription.target_type == SubscriptionTargetType.PROMISE)
                    & (CitizenSubscription.target_id == promise_id)
                )
                | (
                    (CitizenSubscription.target_type == SubscriptionTargetType.CATEGORY)
                    & (CitizenSubscription.target_id == promise_category)
                )
            )
            .distinct()
        )
        subscribers = list(session.exec(stmt).all())

        # 2. Identyfikacja aktywnych webhooków NGO
        webhooks_stmt = select(NgoWebhook).where(NgoWebhook.is_active == True)  # noqa: E712
        webhooks = list(session.exec(webhooks_stmt).all())

        # 3. Przygotowanie payloadu dla Web Push (PWA)
        push_body = (
            f"{promise_title} przeszła do statusu: {new_status}. Werdykt AI: {llm_justification}"
        )
        if len(push_body) > 200:
            push_body = push_body[:197] + "..."

        push_payload = {
            "title": f"ZMIANA: {promise_title[:50]}",
            "body": push_body,
            "icon": "/icon-192x192.png",
            "badge": "/icon-192x192.png",
            "data": {
                "promise_id": promise_id,
                "old_status": old_status,
                "new_status": new_status,
                "url": f"/promises/{promise_id}",
            },
        }

        # 4. Przygotowanie payloadu dla NGO Webhooków
        ngo_payload = {
            "event": "promise.status_changed",
            "timestamp": datetime.now(UTC).isoformat(),
            "promise_id": promise_id,
            "promise_title": promise_title,
            "category": promise_category,
            "old_status": old_status,
            "new_status": new_status,
            "llm_justification": llm_justification,
            "url": f"https://weryfikatorobietnic.pl/promises/{promise_id}",
        }

        # 5. Równoległa wysyłka powiadomień Push (w puli wątków dla pywebpush)
        push_success_count = 0
        if subscribers:
            push_tasks = [
                send_push_notification(sub, push_payload, session=session) for sub in subscribers
            ]
            push_results = await asyncio.gather(*push_tasks, return_exceptions=True)
            push_success_count = sum(1 for res in push_results if res is True)

        # 6. Równoległa wysyłka webhooków do NGO
        webhook_success_count = 0
        if webhooks:
            async with httpx.AsyncClient(timeout=8.0) as http_client:
                webhook_tasks = [
                    send_ngo_webhook(wh, ngo_payload, client=http_client) for wh in webhooks
                ]
                webhook_results = await asyncio.gather(*webhook_tasks, return_exceptions=True)
                webhook_success_count = sum(1 for res in webhook_results if res is True)

        logger.info(
            "Rozesłano powiadomienia dla obietnicy %s: %d/%d Push, %d/%d Webhooki NGO",
            promise_id,
            push_success_count,
            len(subscribers),
            webhook_success_count,
            len(webhooks),
        )

        return {
            "subscribers_total": len(subscribers),
            "push_sent": push_success_count,
            "webhooks_total": len(webhooks),
            "webhooks_sent": webhook_success_count,
        }
    finally:
        if close_session:
            session.close()


def notify_promise_status_change(
    promise_id: str,
    old_status: str,
    new_status: str,
    llm_justification: str,
    session: Session | None = None,
) -> dict[str, int]:
    """Synchroniczny wrapper do notify_promise_status_change pod BackgroundTasks FastAPI lub Airflow Tasks."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # Jesteśmy w pętli zdarzeń, ale chcemy uruchomić zadanie w tle
        # Tworzymy zadanie asynchroniczne bez blokowania
        _ = asyncio.ensure_future(
            async_notify_promise_status_change(
                promise_id=promise_id,
                old_status=old_status,
                new_status=new_status,
                llm_justification=llm_justification,
                session=session,
            )
        )
        return {"scheduled": 1}

    # Wywołanie poza pętlą zdarzeń (np. proces robotniczy Airflow lub skrypt CLI)
    return asyncio.run(
        async_notify_promise_status_change(
            promise_id=promise_id,
            old_status=old_status,
            new_status=new_status,
            llm_justification=llm_justification,
            session=session,
        )
    )
