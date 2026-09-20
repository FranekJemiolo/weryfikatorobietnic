"""Testy jednostkowe i integracyjne dla systemu powiadomień Web Push, subskrypcji obywatelskich i webhooków NGO."""

import hashlib
import hmac
from collections.abc import Generator
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from src.api import app
from src.api.crud import (
    create_or_update_push_subscription,
    register_ngo_webhook,
    remove_push_subscription,
)
from src.database.engine import get_session, init_db
from src.database.models import (
    AlignmentStatus,
    CitizenSubscription,
    LLMEvaluation,
    NgoWebhook,
    Promise,
    PromiseStatus,
)
from src.notifications.dispatcher import (
    async_notify_promise_status_change,
    generate_hmac_signature,
    notify_promise_status_change,
    send_ngo_webhook,
)

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture(autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    init_db(test_engine)
    with Session(test_engine) as session:
        session.exec(select(CitizenSubscription)).all()
        # Wyczyść rekordy przed każdym testem
        for table in reversed(SQLModel.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()

        promise = Promise(
            id="KO-100K-042",
            party="KO",
            title="Podniesienie kwoty wolnej od podatku do 60 000 zł",
            full_text="Podniesiemy kwotę wolną od podatku do 60 tys. zł dla wszystkich.",
            category="Podatki",
            status=PromiseStatus.IN_PROGRESS,
        )
        session.add(promise)
        session.commit()

        eval_rec = LLMEvaluation(
            id=1,
            promise_id="KO-100K-042",
            bill_id="druk-124",
            alignment_status=AlignmentStatus.CZESCIOWO,
            justification="Projekt wpłynął do Sejmu, ale przesunięto vacatio legis.",
            is_approved_by_human=False,
        )
        session.add(eval_rec)
        session.commit()

    def override_get_session() -> Generator[Session, None, None]:
        with Session(test_engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    yield
    app.dependency_overrides.clear()


def test_hmac_signature_calculation() -> None:
    secret = "my_super_secret_token_123"
    payload = b'{"event":"test"}'
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    actual = generate_hmac_signature(secret, payload)
    assert actual == expected
    assert len(actual) == 64


def test_push_subscriber_and_citizen_subscription_crud() -> None:
    with Session(test_engine) as session:
        sub = create_or_update_push_subscription(
            session=session,
            endpoint="https://fcm.googleapis.com/fcm/send/abc12345",
            p256dh="BNcRdreALRF",
            auth="tBHIb",
            target_type="PROMISE",
            target_id="KO-100K-042",
        )
        assert sub.id is not None
        assert sub.target_id == "KO-100K-042"

        # Ponowna subskrypcja tego samego celu nie duplikuje rekordu
        sub2 = create_or_update_push_subscription(
            session=session,
            endpoint="https://fcm.googleapis.com/fcm/send/abc12345",
            p256dh="BNcRdreALRF",
            auth="tBHIb",
            target_type="PROMISE",
            target_id="KO-100K-042",
        )
        assert sub2.id == sub.id

        # Subskrypcja innego celu dodaje nowy wpis
        sub_mp = create_or_update_push_subscription(
            session=session,
            endpoint="https://fcm.googleapis.com/fcm/send/abc12345",
            p256dh="BNcRdreALRF",
            auth="tBHIb",
            target_type="MP",
            target_id="42",
        )
        assert sub_mp.id != sub.id

        # Usunięcie subskrypcji
        removed = remove_push_subscription(
            session=session,
            endpoint="https://fcm.googleapis.com/fcm/send/abc12345",
            target_type="PROMISE",
            target_id="KO-100K-042",
        )
        assert removed is True

        # Sprawdzenie, czy została usunięta
        stmt = select(CitizenSubscription).where(CitizenSubscription.target_id == "KO-100K-042")
        assert session.exec(stmt).first() is None


def test_ngo_webhook_registration() -> None:
    with Session(test_engine) as session:
        wh = register_ngo_webhook(
            session=session,
            organization_name="Demagog",
            target_url="https://demagog.org.pl/api/webhook",
            secret_token="secret_abc",
        )
        assert wh.id is not None
        assert wh.is_active is True

        queried = session.get(NgoWebhook, wh.id)
        assert queried is not None
        assert queried.organization_name == "Demagog"


@pytest.mark.anyio
async def test_send_ngo_webhook_with_hmac() -> None:
    webhook = NgoWebhook(
        id=1,
        organization_name="Watchdog Polska",
        target_url="https://watchdog.example.org/webhook",
        secret_token="secret_key_xyz",
        is_active=True,
    )
    payload = {"event": "promise.status_changed", "promise_id": "KO-100K-042"}

    # Mockowanie httpx.AsyncClient
    mock_response = httpx.Response(status_code=200, json={"received": True})
    with patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        success = await send_ngo_webhook(webhook, payload)
        assert success is True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        headers = call_kwargs["headers"]
        assert "X-Hub-Signature-256" in headers
        assert "X-Signature-SHA256" in headers
        assert headers["X-Hub-Signature-256"].startswith("sha256=")


@pytest.mark.anyio
async def test_async_notify_promise_status_change() -> None:
    with Session(test_engine) as session:
        # Utwórz subskrybenta
        create_or_update_push_subscription(
            session=session,
            endpoint="https://push.example.com/sub/123",
            p256dh="key123",
            auth="auth123",
            target_type="PROMISE",
            target_id="KO-100K-042",
        )
        register_ngo_webhook(
            session=session,
            organization_name="Klub Jagielloński",
            target_url="https://kj.example.org/webhook",
            secret_token="kj_secret",
        )

        with (
            patch("src.notifications.dispatcher.send_single_push", return_value=True) as mock_push,
            patch("httpx.AsyncClient.post", return_value=httpx.Response(200)),
        ):
            res = await async_notify_promise_status_change(
                promise_id="KO-100K-042",
                old_status="IN_PROGRESS",
                new_status="FULFILLED",
                llm_justification="Ustawa została opublikowana w Dz.U.",
                session=session,
            )
            assert res["subscribers_total"] >= 1
            assert res["push_sent"] >= 1
            assert res["webhooks_total"] >= 1
            assert res["webhooks_sent"] >= 1
            assert mock_push.called


def test_sync_notify_promise_status_change_wrapper() -> None:
    with Session(test_engine) as session:
        with patch(
            "src.notifications.dispatcher.async_notify_promise_status_change",
            return_value={"ok": 1},
        ):
            res = notify_promise_status_change(
                promise_id="KO-100K-042",
                old_status="NEW",
                new_status="IN_PROGRESS",
                llm_justification="Wpłynął projekt",
                session=session,
            )
            assert "ok" in res or "scheduled" in res


def test_api_subscriptions_endpoints() -> None:
    client = TestClient(app)

    # 1. Pobranie klucza VAPID
    vapid_res = client.get("/api/v1/subscriptions/vapid-key")
    assert vapid_res.status_code == 200
    assert "public_key" in vapid_res.json()

    # 2. Rejestracja subskrypcji Push
    sub_payload = {
        "subscription": {
            "endpoint": "https://updates.push.services.mozilla.com/wpush/v2/gAAAAAB",
            "keys": {
                "p256dh": "BAfL7e4f3a9...",
                "auth": "auth_key_123",
            },
        },
        "target_type": "PROMISE",
        "target_id": "KO-100K-042",
    }
    res_sub = client.post("/api/v1/subscribe", json=sub_payload)
    assert res_sub.status_code == 200
    assert res_sub.json()["success"] is True

    # 3. Odsubskrybowanie
    unsub_payload = {
        "endpoint": "https://updates.push.services.mozilla.com/wpush/v2/gAAAAAB",
        "target_type": "PROMISE",
        "target_id": "KO-100K-042",
    }
    res_unsub = client.post("/api/v1/unsubscribe", json=unsub_payload)
    assert res_unsub.status_code == 200
    assert res_unsub.json()["success"] is True

    # 4. Rejestracja webhooka NGO
    wh_payload = {
        "organization_name": "Sieć Obywatelska Watchdog",
        "target_url": "https://watchdog.org.pl/endpoint",
        "secret_token": "watchdog_secret_token",
    }
    res_wh = client.post("/api/v1/webhooks", json=wh_payload)
    assert res_wh.status_code == 200
    data_wh = res_wh.json()
    assert data_wh["organization_name"] == "Sieć Obywatelska Watchdog"
    assert data_wh["is_active"] is True

    # 5. Wyzwolenie powiadomienia w tle dla obietnicy
    notify_payload = {
        "old_status": "IN_PROGRESS",
        "new_status": "FULFILLED",
        "llm_justification": "Sejm przyjął ustawę bez poprawek.",
    }
    with (
        patch("src.notifications.dispatcher.get_engine", return_value=test_engine),
        patch("src.notifications.dispatcher.send_single_push", return_value=True),
    ):
        res_notify = client.post("/api/v1/promises/KO-100K-042/notify", json=notify_payload)
        assert res_notify.status_code == 200
        assert res_notify.json()["status"] == "queued"

        # 6. Zatwierdzenie ewaluacji przez człowieka (Human-in-the-Loop)
        res_appr = client.post("/api/v1/evaluations/1/approve")
        assert res_appr.status_code == 200
        assert res_appr.json()["is_approved_by_human"] is True
