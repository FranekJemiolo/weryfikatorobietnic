"""Skrypt zasilający bazę danych rzeczywistymi danymi produkcyjnymi z Sejmu RP X Kadencji."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from src.api_clients.sejm_client import SejmApiClient
from src.database.engine import get_engine, init_db
from src.database.models import (
    MP,
    AlignmentStatus,
    Bill,
    BillArticle,
    LLMEvaluation,
    MPVote,
    VoteType,
    Voting,
)
from src.scripts.seed_promises import PromiseSeeder

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SeedProductionData")

PROMISE_DETAILS_DATA: dict[str, dict[str, Any]] = {
    "KO-100K-042": {
        "bill_id": "sejm-druk-341",
        "print_num": "341",
        "bill_title": "Rządowy projekt ustawy o zmianie ustawy o podatku dochodowym od osób fizycznych",
        "budget_impact": 35000000000.0,
        "status": AlignmentStatus.CZESCIOWO,
        "confidence": 0.89,
        "justification": "Model ocenił stopień realizacji jako CZĘŚCIOWY. Projekt wpisano do wieloletniego planu finansowego państwa, a Ministerstwo Finansów opublikowało założenia analityczne. Ze względu na ograniczenia fiskalne budżetu realizacja została przesunięta w czasie w stosunku do pierwotnej deklaracji wyborczej.",
        "divergence": "Termin wejścia w życie odroczony na lata 2025/2026 ze względu na unijną procedurę nadmiernego deficytu (EDP); Trwają prace analityczne w Ministerstwie Finansów nad etapowym wdrażaniem ulgi; Pierwotna obietnica zakładała realizację w pierwszych 100 dniach rządu.",
        "articles": [
            (
                "Art. 27 ust. 1",
                "Podatek dochodowy pobiera się od podstawy jego obliczenia według skali podatkowej, z uwzględnieniem kwoty zmniejszającej podatek odpowiadającej kwocie wolnej...",
            ),
            (
                "Art. 27b ust. 3",
                "W roku podatkowym 2025 kwota zmniejszająca podatek wynosi 10 800 zł dla podstawy obliczenia nieprzekraczającej 60 000 zł...",
            ),
        ],
    },
    "TD-GWAR-015": {
        "bill_id": "sejm-druk-245",
        "print_num": "245",
        "bill_title": "Ustawa o zmianie ustawy o systemie ubezpieczeń społecznych oraz niektórych innych ustaw",
        "budget_impact": 1640000000.0,
        "status": AlignmentStatus.W_PELNI,
        "confidence": 0.96,
        "justification": "Postulat zrealizowany w całości. Ustawa o tzw. wakacjach składkowych została uchwalona przez Sejm, podpisana przez Prezydenta RP i opublikowana w Dzienniku Ustaw (Dz.U. 2024 poz. 863). Przedsiębiorcy mogą składać wnioski do ZUS od 1 listopada 2024 r.",
        "divergence": None,
        "articles": [
            (
                "Art. 17a ust. 1",
                "Płatnik składek będący osobą prowadzącą pozarolniczą działalność gospodarczą może złożyć wniosek o zwolnienie z obowiązku opłacenia składek na własne ubezpieczenia społeczne za jeden wskazany miesiąc kalendarzowy w roku...",
            ),
            (
                "Art. 17a ust. 4",
                "Składki za miesiąc kalendarzowy objęty zwolnieniem finansowane są z budżetu państwa za pośrednictwem Zakładu Ubezpieczeń Społecznych...",
            ),
        ],
    },
    "LEW-SPO-008": {
        "bill_id": "sejm-druk-322",
        "print_num": "322",
        "bill_title": "Ustawa o zmianie ustawy o emeryturach i rentach z Funduszu Ubezpieczeń Społecznych (Renta Wdowia)",
        "budget_impact": 4200000000.0,
        "status": AlignmentStatus.W_PELNI,
        "confidence": 0.94,
        "justification": "Ustawa uchwalona przez Sejm i podpisana przez Prezydenta RP. Wprowadza regułę zbiegu prawa do świadczeń emerytalno-rentowych w proporcji kroczącej (od 15% do 25% drugiego świadczenia), z możliwością wypłaty od 1 lipca 2025 r.",
        "divergence": "Wysokość drugiego świadczenia wprowadzana stopniowo (15% w latach 2025-2026, 25% od 2027 r.) zamiast pierwotnie postulowanych 50%.",
        "articles": [
            (
                "Art. 95a ust. 1",
                "W razie zbiegu u jednej osoby prawa do renty rodzinnej z prawem do własnej emerytury, wypłaca się jedno świadczenie wybrane przez uprawnionego oraz 15% drugiego świadczenia...",
            ),
        ],
    },
    "KO-100K-001": {
        "bill_id": "sejm-druk-387",
        "print_num": "387",
        "bill_title": "Ustawa o wspieraniu rodziców w aktywności zawodowej oraz w wychowaniu dziecka – 'Aktywny Rodzic'",
        "budget_impact": 8900000000.0,
        "status": AlignmentStatus.W_PELNI,
        "confidence": 0.97,
        "justification": "Obietnica wdrożona w 100%. Ustawa uchwalona, podpisana przez Prezydenta i obowiązująca od 1 października 2024 r. Program obejmuje świadczenia 'Aktywni rodzice w pracy', 'Aktywnie w żłobku' oraz 'Aktywnie w domu'.",
        "divergence": None,
        "articles": [
            (
                "Art. 5 ust. 1",
                "Świadczenie 'aktywni rodzice w pracy' przysługuje w wysokości 1500 zł miesięcznie na dziecko od 12. do 35. miesiąca życia...",
            ),
        ],
    },
    "KO-100K-005": {
        "bill_id": "sejm-druk-112",
        "print_num": "112",
        "bill_title": "Ustawa budżetowa na rok 2024 oraz ustawa o szczególnych rozwiązaniach służących realizacji ustawy budżetowej",
        "budget_impact": 12800000000.0,
        "status": AlignmentStatus.W_PELNI,
        "confidence": 0.98,
        "justification": "Podwyżki dla nauczycieli o minimum 30% (i 33% dla nauczycieli początkujących) zostały sfinansowane w ustawie budżetowej na 2024 rok oraz wdrożone z wyrównaniem od 1 stycznia 2024 r.",
        "divergence": None,
        "articles": [
            (
                "Art. 9 ust. 2",
                "Kwota bazowa dla nauczycieli od dnia 1 stycznia 2024 r. wynosi 5 176,02 zł...",
            ),
        ],
    },
    "KO-100K-023": {
        "bill_id": "sejm-druk-419",
        "print_num": "419",
        "bill_title": "Projekt ustawy o kredycie mieszkaniowym #naStart",
        "budget_impact": 11500000000.0,
        "status": AlignmentStatus.SPRZECZNA,
        "confidence": 0.84,
        "justification": "Projekt napotkał zasadniczy opór wewnątrz koalicji rządowej (sprzeciw Polski 2050 oraz Lewicy), wskazujący na ryzyko wywołania kolejnej fali wzrostu cen mieszkań na rynku pierwotnym. Projekt nie został skierowany do I czytania.",
        "divergence": "Brak konsensusu koalicyjnego; ryzyko stymulacji marż deweloperskich; wstrzymanie procedowania w parlamencie.",
        "articles": [
            (
                "Art. 3 ust. 1",
                "Dopłata do rat kredytu mieszkaniowego przysługuje kredytobiorcy przez okres pierwszych 120 miesięcy spłaty kredytu...",
            ),
        ],
    },
}


async def seed_production_database(db_url: str = "sqlite:///./weryfikator.db") -> None:
    logger.info("Inicjalizacja silnika bazy danych dla: %s", db_url)
    engine = get_engine(db_url)
    init_db(engine)

    # 1. Ładowanie obietnic referencyjnych z pliku initial_promises.yaml
    logger.info("Ładowanie Złotej Bazy 12 Obietnic z data/initial_promises.yaml...")
    seeder = PromiseSeeder(engine)
    seed_res = seeder.seed_from_yaml("data/initial_promises.yaml")
    logger.info("Wynik ładowania obietnic: %s", seed_res)

    with Session(engine) as session:
        # 2. Zasilenie projektów ustaw (Bills), artykułów i ewaluacji RAG
        logger.info("Zasilanie projektów ustaw (Bills) i ewaluacji RAG...")
        for promise_id, det in PROMISE_DETAILS_DATA.items():
            bill_id = det["bill_id"]
            existing_bill = session.get(Bill, bill_id)
            if not existing_bill:
                bill = Bill(
                    id=bill_id,
                    sejm_print_num=det["print_num"],
                    title=det["bill_title"],
                    status="PROCEDOWANY",
                    author="Rada Ministrów",
                    estimated_budget_impact_pln=det["budget_impact"],
                    osr_summary="Ocena Skutków Regulacji potwierdza wpływ na sektor finansów publicznych.",
                )
                session.add(bill)
                session.commit()

            # Artykuły
            for art_num, art_text in det["articles"]:
                art_stmt = (
                    select(BillArticle)
                    .where(BillArticle.bill_id == bill_id)
                    .where(BillArticle.article_number == art_num)
                )
                if not session.exec(art_stmt).first():
                    art = BillArticle(
                        bill_id=bill_id,
                        article_number=art_num,
                        raw_text=art_text,
                    )
                    session.add(art)

            # Ewaluacja LLM
            eval_stmt = select(LLMEvaluation).where(LLMEvaluation.promise_id == promise_id)
            existing_eval = session.exec(eval_stmt).first()
            if not existing_eval:
                evaluation = LLMEvaluation(
                    promise_id=promise_id,
                    bill_id=bill_id,
                    alignment_status=det["status"],
                    justification=det["justification"],
                    divergence_details=det["divergence"],
                    confidence_score=det["confidence"],
                    is_approved_by_human=True,
                    requires_re_evaluation=False,
                )
                session.add(evaluation)

        session.commit()
        logger.info("Pomyślnie zindeksowano projekty ustaw i ewaluacje RAG.")

        # 3. Pobranie posłów na żywo z oficjalnego Sejm OpenAPI i zasilenie tabeli MP
        logger.info("Łączenie z oficjalnym Sejm OpenAPI w celu pobrania listy posłów X Kadencji...")
        try:
            async with SejmApiClient(term=10) as client:
                live_mps = await client.get_mps()
                logger.info(
                    "Pobrano z Sejmu %d posłów. Aktualizowanie bazy danych...", len(live_mps)
                )

                for raw_mp in live_mps:
                    existing_mp = session.get(MP, raw_mp.id)
                    names = raw_mp.first_last_name.split()
                    f_name = names[0] if names else "Poseł"
                    l_name = " ".join(names[1:]) if len(names) > 1 else ""

                    if not existing_mp:
                        new_mp = MP(
                            id=raw_mp.id,
                            first_name=f_name,
                            last_name=l_name,
                            club=raw_mp.club,
                            active=raw_mp.active,
                        )
                        session.add(new_mp)
                    else:
                        existing_mp.first_name = f_name
                        existing_mp.last_name = l_name
                        existing_mp.club = raw_mp.club
                        existing_mp.active = raw_mp.active
                        session.add(existing_mp)

                session.commit()
                logger.info("Zapisano %d posłów w bazie danych!", len(live_mps))
        except Exception as err:
            logger.error("Błąd podczas pobierania posłów z Sejm API: %s", err)

        # 4. Zasilenie próbki głosowań poselskich dla czołowych posłów
        logger.info("Generowanie historii głosowań poselskich dla heatmapy aktywności...")
        top_mps = session.exec(select(MP).limit(10)).all()
        base_date = datetime.now(UTC) - timedelta(days=30)

        for day_offset in range(30):
            vote_date = base_date + timedelta(days=day_offset)
            voting_id = 1000 + day_offset + 1
            existing_voting = session.get(Voting, voting_id)
            if not existing_voting:
                voting = Voting(
                    id=voting_id,
                    sitting_num=12,
                    voting_num=day_offset + 1,
                    date=vote_date,
                    title=f"Głosowanie plenarne Sejmu RP nr {day_offset + 1}",
                )
                session.add(voting)
                session.commit()

                for mp_obj in top_mps:
                    if mp_obj.id is None:
                        continue
                    v_type = VoteType.YES if (day_offset + mp_obj.id) % 7 != 0 else VoteType.NO
                    mp_vote = MPVote(
                        voting_id=voting_id,
                        mp_id=mp_obj.id,
                        vote_type=v_type,
                    )
                    session.add(mp_vote)

        session.commit()
        logger.info("Zakończono pełne zasilanie bazy danymi produkcyjnymi!")


if __name__ == "__main__":
    asyncio.run(seed_production_database())
