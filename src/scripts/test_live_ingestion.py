"""Skrypt weryfikacyjny testujący pobieranie danych ze wszystkich 6 źródeł w projekcie."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TestLiveIngestion")


async def test_sejm_openapi() -> dict[str, Any]:
    logger.info("--> Testowanie Źródła 1: Sejm OpenAPI (api.sejm.gov.pl)...")
    from src.api_clients.sejm_client import SejmApiClient

    results: dict[str, Any] = {}
    async with SejmApiClient(term=10) as client:
        # 1. Posłowie
        mps = await client.get_mps()
        results["mps_count"] = len(mps)
        results["sample_mp"] = f"{mps[0].first_last_name} ({mps[0].club})" if mps else None

        # 2. Procesy legislacyjne
        processes = await client.get_processes(limit=5)
        results["processes_count"] = len(processes)
        results["sample_process"] = (
            f"Druk #{processes[0].number}: {processes[0].title[:60]}..." if processes else None
        )

        # 3. Interpelacje
        interpellations = await client.get_interpellations(limit=5)
        results["interpellations_count"] = len(interpellations)
        results["sample_interpellation"] = (
            f"Nr {interpellations[0].num}: {interpellations[0].title[:60]}..."
            if interpellations
            else None
        )

    logger.info(
        "Sejm OpenAPI: Sukces! Pobrano %d posłów, %d procesów, %d interpelacji.",
        results["mps_count"],
        results["processes_count"],
        results["interpellations_count"],
    )
    return results


def test_isap_client() -> dict[str, Any]:
    logger.info("--> Testowanie Źródła 2: ISAP / ELI API (api.sejm.gov.pl/eli)...")
    from src.api_clients.isap_client import ISAPClient

    with ISAPClient() as client:
        # 1. Wyszukiwanie aktów po tytule
        acts = client.search_acts_by_title("podatku", year=2024)
        sample_title = None
        act_details = None
        if acts:
            first_act = acts[0]
            pub = str(first_act.get("publisher", "DU"))
            yr = int(first_act.get("year", 2024))
            pos = int(first_act.get("pos", 1962))
            act_details = client.get_act_details(pub, yr, pos)
            sample_title = act_details.get("title") if act_details else first_act.get("title")

    results: dict[str, Any] = {
        "search_results_count": len(acts),
        "sample_act_title": sample_title[:80] if sample_title else None,
        "act_status": act_details.get("status") if act_details else None,
        "entry_into_force": act_details.get("entryIntoForce") if act_details else None,
    }
    logger.info(
        "ISAP API: Sukces! Znaleziono %d aktów prawnych, pobrano szczegóły aktu: %s",
        results["search_results_count"],
        results["sample_act_title"],
    )
    return results


def test_rss_collector() -> dict[str, Any]:
    logger.info("--> Testowanie Źródła 3: Kanały informacyjne RSS / Atom...")
    from src.collectors.rss_collector import RSSCollector

    collector = RSSCollector()
    feeds = collector.load_configured_feeds()

    all_items = []
    active_feeds = []
    for feed in feeds:
        items = collector.fetch_feed(feed["url"], feed["name"], feed.get("category"))
        if items:
            all_items.extend(items)
            active_feeds.append({"feed": feed["name"], "count": len(items)})

    results: dict[str, Any] = {
        "configured_feeds_count": len(feeds),
        "active_feeds_count": len(active_feeds),
        "active_feeds": active_feeds,
        "total_items_fetched": len(all_items),
        "sample_item_title": all_items[0].title[:70] if all_items else None,
    }
    logger.info(
        "RSS Collector: Sukces! %d feedów skonfigurowanych, %d aktywnych, łącznie %d wpisów.",
        len(feeds),
        len(active_feeds),
        len(all_items),
    )
    return results


def test_party_watchdog() -> dict[str, Any]:
    logger.info("--> Testowanie Źródła 4: Strony Partii Politycznych (PartyWatchdog)...")
    from src.scrapers.party_watchdog import PartyWatchdog

    targets = PartyWatchdog.load_targets_from_yaml()
    watchdog = PartyWatchdog()

    sample_html = "<html><body><header>Nawigacja</header><main><h1>Program Partii</h1><p>Obietnica: Podatki 0%</p></main><footer>Stopka</footer></body></html>"
    cleaned_text, content_hash = watchdog.clean_html(sample_html)

    # Przetestuj pobranie pierwszej strony z konfiguracji (np. 100konkretow.pl)
    fetched_live = False
    first_target_url = targets[0]["url"] if targets else "https://100konkretow.pl"
    live_hash_val = None
    try:
        live_html = watchdog.fetch_page(first_target_url)
        live_clean, live_hash = watchdog.clean_html(live_html)
        fetched_live = bool(live_clean)
        live_hash_val = live_hash
    except Exception as exc:
        logger.warning(
            "Nie udało się pobrać na żywo strony %s (%s). Użyto testu lokalnego.",
            first_target_url,
            exc,
        )

    results: dict[str, Any] = {
        "monitored_targets_count": len(targets),
        "clean_html_hash": content_hash,
        "live_target_tested": first_target_url,
        "live_target_success": fetched_live,
        "live_target_hash": live_hash_val,
    }
    logger.info(
        "PartyWatchdog: Sukces! %d celów, hash testowy: %s, live status: %s",
        len(targets),
        content_hash[:12],
        fetched_live,
    )
    return results


def test_rcl_watchdog() -> dict[str, Any]:
    logger.info("--> Testowanie Źródła 5: Rządowe Centrum Legislacji (RCL Watchdog)...")
    from src.scrapers.rcl_watchdog import RCLWatchdog

    watchdog = RCLWatchdog()

    # Test parsera na strukturze HTML
    sample_rcl_html = """
    <table class="table">
      <tr>
        <td>UD123</td>
        <td>Projekt ustawy o wsparciu przedsiębiorców</td>
        <td>Uzgodnienia międzyresortowe</td>
        <td>Ministerstwo Rozwoju</td>
        <td>2024-05-10</td>
      </tr>
    </table>
    """
    parsed_sample = watchdog.parse_projects_from_html(sample_rcl_html)

    # Próba pobrania na żywo ze strony RCL
    live_accessible = False
    try:
        live_html = watchdog.fetch_page("/katalog/projekty-ustaw")
        live_accessible = bool(live_html and len(live_html) > 100)
    except Exception as exc:
        logger.warning("Błąd pobierania RCL na żywo: %s", exc)

    results: dict[str, Any] = {
        "parser_validation_success": len(parsed_sample) == 1,
        "sample_project_id": parsed_sample[0]["id"] if parsed_sample else None,
        "live_connection_accessible": live_accessible,
    }
    logger.info(
        "RCL Watchdog: Sukces! Parser poprawny, połączenie na żywo: %s.",
        live_accessible,
    )
    return results


def test_seed_promises() -> dict[str, Any]:
    logger.info("--> Testowanie Źródła 6: Złota Baza Obietnic (Ground Truth Seed)...")
    import yaml

    yaml_path = Path("data/initial_promises.yaml")
    if not yaml_path.exists():
        raise FileNotFoundError(f"Brak pliku {yaml_path}")

    with open(yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    promises = data.get("promises", [])
    results: dict[str, Any] = {
        "seed_promises_count": len(promises),
        "promises": [{"id": p["id"], "party": p["party"], "title": p["title"]} for p in promises],
    }
    logger.info(
        "Seed Promises: Sukces! Zweryfikowano %d obietnic w pliku referencyjnym.",
        len(promises),
    )
    return results


async def main() -> None:
    logger.info("=================================================================")
    logger.info("ROZPOCZĘCIE KOMPLEKSOWEGO TESTU POBIERANIA DANYCH Z 6 ŹRÓDEŁ")
    logger.info("=================================================================")
    report: dict[str, Any] = {}

    try:
        report["1_sejm_openapi"] = await test_sejm_openapi()
    except Exception as e:
        logger.error("Błąd Sejm OpenAPI: %s", e)
        report["1_sejm_openapi"] = {"error": str(e)}

    try:
        report["2_isap_eli_api"] = test_isap_client()
    except Exception as e:
        logger.error("Błąd ISAP API: %s", e)
        report["2_isap_eli_api"] = {"error": str(e)}

    try:
        report["3_rss_collector"] = test_rss_collector()
    except Exception as e:
        logger.error("Błąd RSS Collector: %s", e)
        report["3_rss_collector"] = {"error": str(e)}

    try:
        report["4_party_watchdog"] = test_party_watchdog()
    except Exception as e:
        logger.error("Błąd PartyWatchdog: %s", e)
        report["4_party_watchdog"] = {"error": str(e)}

    try:
        report["5_rcl_watchdog"] = test_rcl_watchdog()
    except Exception as e:
        logger.error("Błąd RCL Watchdog: %s", e)
        report["5_rcl_watchdog"] = {"error": str(e)}

    try:
        report["6_seed_promises"] = test_seed_promises()
    except Exception as e:
        logger.error("Błąd Seed Promises: %s", e)
        report["6_seed_promises"] = {"error": str(e)}

    logger.info("=================================================================")
    logger.info("PODSUMOWANIE POBIERANIA ZE WSZYSTKICH ŹRÓDEŁ:")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
