"""Testy jednostkowe silnika ewaluacyjnego RAG (PromiseEvaluator)."""

from sqlmodel import Session, create_engine

from src.ai.evaluator import PromiseEvaluationSchema, PromiseEvaluator
from src.database.engine import init_db
from src.database.models import AlignmentStatus, Bill, BillArticle, Promise, PromiseStatus


def test_promise_evaluator_rag_flow() -> None:
    """Weryfikuje pełny przepływ RAG: wyszukiwanie artykułów, ocenę LLM i zapis do bazy."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    init_db(engine)

    # Przygotowanie danych testowych w bazie
    with Session(engine) as session:
        promise = Promise(
            id="TEST-PROM-01",
            party="KO",
            title="Kwota wolna od podatku 60 tysięcy zł",
            full_text="Podniesiemy kwotę wolną od podatku do 60 000 zł.",
            category="Podatki",
            status=PromiseStatus.IN_PROGRESS,
        )
        bill = Bill(
            id="TEST-BILL-01",
            sejm_print_num="124",
            title="Projekt ustawy o podatku dochodowym",
            status="KONSULTACJE",
            author="Rada Ministrów",
        )
        session.add(promise)
        session.add(bill)
        session.commit()

        # Dodanie 2 artykułów z wektorami
        evaluator = PromiseEvaluator(engine=engine)
        vec1 = evaluator.analyzer.generate_embeddings(["Art. 1. Kwota wolna wynosi 60 000 zł."])[0]
        vec2 = evaluator.analyzer.generate_embeddings(["Art. 2. Przepisy porządkowe i karne."])[0]

        art1 = BillArticle(
            bill_id=bill.id,
            article_number="Art. 1.",
            raw_text="W art. 27 ust. 1 kwotę zmniejszającą podatek ustala się na 60 000 zł.",
            embedding=vec1,
        )
        art2 = BillArticle(
            bill_id=bill.id,
            article_number="Art. 2.",
            raw_text="Kto narusza przepisy porządkowe podlega karze grzywny.",
            embedding=vec2,
        )
        session.add(art1)
        session.add(art2)
        session.commit()

    evaluator = PromiseEvaluator(engine=engine)

    # 1. Wyszukanie najbardziej relewantnych artykułów
    articles = evaluator.get_relevant_articles(
        promise_id="TEST-PROM-01", bill_id="TEST-BILL-01", top_k=1
    )
    assert len(articles) == 1
    assert articles[0].article_number == "Art. 1."

    # 2. Weryfikacja oceny
    eval_result = evaluator.evaluate_bill_against_promise(promise, articles)
    assert isinstance(eval_result, PromiseEvaluationSchema)
    assert eval_result.alignment_status in ["W_PELNI", "CZESCIOWO", "SPRZECZNA", "BRAK_POWIAZANIA"]
    assert eval_result.score > 0.0

    # 3. Zapisanie oceny do bazy (LLMEvaluation)
    saved_eval = evaluator.save_evaluation(
        promise_id="TEST-PROM-01",
        bill_id="TEST-BILL-01",
        evaluation=eval_result,
    )
    assert saved_eval.id is not None
    assert saved_eval.promise_id == "TEST-PROM-01"
    assert saved_eval.bill_id == "TEST-BILL-01"
    assert saved_eval.alignment_status == AlignmentStatus(eval_result.alignment_status)
