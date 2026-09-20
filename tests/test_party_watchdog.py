"""Testy jednostkowe modułu PartyWatchdog i detekcji cichych zmian w obietnicach."""

from sqlmodel import Session, create_engine, select

from src.database.engine import init_db
from src.database.models import Promise, PromiseRevision
from src.scrapers.party_watchdog import PartyWatchdog


def test_party_watchdog_clean_html_and_hash() -> None:
    """Weryfikuje oczyszczanie kodu HTML z nawigacji i szumu oraz determinizm hasha SHA-256."""
    html_raw = """
    <!DOCTYPE html>
    <html>
      <head><title>Program Partii</title></head>
      <body>
        <nav><a href="/">Menu Główne</a></nav>
        <header>Baner wyborczy</header>
        <main>
          <h1>Nasze Konkrety na 100 dni</h1>
          <article>
            <p>Wprowadzimy kwotę wolną 60 000 zł dla wszystkich pracujących.</p>
          </article>
        </main>
        <footer>Prawa autorskie &copy; 2024</footer>
        <script>console.log('tracker');</script>
      </body>
    </html>
    """
    watchdog = PartyWatchdog()
    clean_text, content_hash = watchdog.clean_html(html_raw)

    assert "Menu Główne" not in clean_text
    assert "Prawa autorskie" not in clean_text
    assert "tracker" not in clean_text
    assert "Nasze Konkrety na 100 dni" in clean_text
    assert "kwotę wolną 60 000 zł" in clean_text
    assert len(content_hash) == 64  # SHA-256 hex string


def test_party_watchdog_silent_change_detection() -> None:
    """Weryfikuje cykl życia rewizji: stan początkowy -> cicha zmiana -> brak zmian."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    init_db(engine)

    watchdog = PartyWatchdog(engine=engine)
    promise_id = "KO-100K-042"
    url = "https://koalicjaobywatelska.pl/program-podatkowy"

    v1_html = "<main><p>Podniesiemy kwotę wolną do 60 000 zł w 100 dni.</p></main>"
    v2_html_modified = "<main><p>Podniesiemy kwotę wolną do 60 000 zł do końca kadencji.</p></main>"

    # KROK 1: Pierwsze pobranie (Initial)
    res1 = watchdog.check_and_update(url=url, promise_id=promise_id, html_content=v1_html)
    assert res1["is_initial"] is True
    assert res1["is_changed"] is False

    with Session(engine) as session:
        revisions = session.exec(
            select(PromiseRevision).where(PromiseRevision.promise_id == promise_id)
        ).all()
        assert len(revisions) == 1
        p = session.get(Promise, promise_id)
        assert p is not None

    # KROK 2: Kolejne pobranie bez zmian
    res2 = watchdog.check_and_update(url=url, promise_id=promise_id, html_content=v1_html)
    assert res2["is_initial"] is False
    assert res2["is_changed"] is False

    with Session(engine) as session:
        revisions = session.exec(
            select(PromiseRevision).where(PromiseRevision.promise_id == promise_id)
        ).all()
        assert len(revisions) == 1  # Liczba rewizji bez zmian

    # KROK 3: Wykrycie cichej modyfikacji treści (Silent Change)
    res3 = watchdog.check_and_update(url=url, promise_id=promise_id, html_content=v2_html_modified)
    assert res3["is_initial"] is False
    assert res3["is_changed"] is True

    with Session(engine) as session:
        revisions = session.exec(
            select(PromiseRevision).where(PromiseRevision.promise_id == promise_id)
        ).all()
        assert len(revisions) == 2
        assert revisions[0].content_hash != revisions[1].content_hash
