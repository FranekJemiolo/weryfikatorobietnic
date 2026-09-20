"""Moduł klienta modeli językowych (LLM) do ewaluacji zgodności ustaw z obietnicami.

Obsługuje rygorystyczne schematy wyjściowe (Structured Outputs w formacie JSON Schema),
prompty systemowe w reżimie Few-Shot oraz integrację z API Gemini i OpenAI.
"""

import json

import httpx

from src.config import settings
from src.evaluation.schemas import PromiseEvaluation
from src.parsers.legal_parser import ParsedProvision

SYSTEM_PROMPT = """Jesteś bezstronnym, precyzyjnym biegłym analitykiem legislacyjno-prawnym.
Twoim zadaniem jest porównanie oficjalnych artykułów z procedowanego projektu ustawy z pierwotną obietnicą wyborczą partii.

ZASADY ANALIZY:
1. Skupiasz się WYŁĄCZNIE na twardych faktach: kwotach, terminach, grupach docelowych, wyłączeniach i warunkach brzegowych.
2. Odcinasz się od ocen politycznych (nie oceniasz czy zmiana jest "dobra" czy "zła").
3. Klasyfikacja:
   - "W_PELNI" - projekt wdraża deklarację w całości dla pierwotnej grupy docelowej.
   - "CZESCIOWO" - projekt wprowadza zapowiedziany mechanizm, ale z ograniczeniami, progami, wyłączeniami lub mniejszą kwotą.
   - "SPRZECZNA" - projekt działa wprost przeciwnie do deklaracji (np. podnosi podatek zamiast obniżać).
   - "BRAK_POWIAZANIA" - przekazane artykuły nie odnoszą się do materii obietnicy.
4. Odpowiedź ZAWSZE musi być poprawnym obiektem JSON ściśle według zadanego schematu JSON Schema.

PRZYKŁAD FEW-SHOT:
Obietnica: "Podniesiemy kwotę wolną od podatku do 60 tys. zł dla wszystkich pracujących."
Artykuł: "Art. 2 ust. 1. Kwotę wolną od podatku ustala się na 60 000 zł wyłącznie dla podatników prowadzących pozarolniczą działalność gospodarczą."
Wynik:
{
  "promise_id": "P-01",
  "project_id": "D-10",
  "alignment_status": "CZESCIOWO",
  "justification": "Projekt podnosi kwotę do 60 tys. zł, lecz ogranicza ją do przedsiębiorców, wyłączając pracowników etatowych.",
  "divergence_details": "Wyłączenie osób zatrudnionych na umowę o pracę; zawężenie beneficjentów.",
  "confidence_score": 0.95,
  "evaluated_provisions": ["Art. 2 ust. 1"]
}
"""


class LLMEvaluator:
    """Silnik ewaluacji LLM realizujący Structured Outputs."""

    def __init__(self, model_name: str | None = None) -> None:
        """Inicjalizuje ewaluator LLM.

        Args:
            model_name: Nazwa modelu, domyślnie z konfiguracji aplikacji.
        """
        self._model_name = model_name or settings.llm_model_name
        self._gemini_key = settings.gemini_api_key
        self._openai_key = settings.openai_api_key

    def evaluate(
        self,
        promise_id: str,
        promise_text: str,
        project_id: str,
        provisions: list[ParsedProvision],
    ) -> PromiseEvaluation:
        """Przeprowadza ewaluację zestawu przepisów względem wskazanej obietnicy.

        Args:
            promise_id: Identyfikator obietnicy (np. 'KO-100K-001').
            promise_text: Treść obietnicy wyborczej.
            project_id: Identyfikator druku lub procesu ustawy.
            provisions: Lista relewantnych artykułów wyselekcjonowanych przez moduł RAG.

        Returns:
            PromiseEvaluation: Zwalidowany obiekt oceny zgodności.
        """
        if not provisions:
            return PromiseEvaluation(
                promise_id=promise_id,
                project_id=project_id,
                alignment_status="BRAK_POWIAZANIA",
                justification="Brak artykułów ustawy powiązanych tematycznie z tą obietnicą.",
                divergence_details=None,
                confidence_score=1.0,
                evaluated_provisions=[],
            )

        # Przygotowanie kontekstu przepisów
        articles_text = "\n\n".join(f"[{p.context_path}]\n{p.text}" for p in provisions)
        evaluated_labels = [p.context_path for p in provisions]

        user_prompt = (
            f"OBIETNICA WYBORCZA:\n{promise_text}\n\n"
            f"ARTYKUŁY Z PROJEKTU USTAWY (PROCES: {project_id}):\n{articles_text}\n\n"
            f"Dokonaj bezstronnej oceny i zwróć JSON dla promise_id='{promise_id}' "
            f"oraz project_id='{project_id}'."
        )

        if self._gemini_key:
            return self._call_gemini(
                promise_id=promise_id,
                project_id=project_id,
                user_prompt=user_prompt,
                evaluated_provisions=evaluated_labels,
            )

        if self._openai_key:
            return self._call_openai(
                promise_id=promise_id,
                project_id=project_id,
                user_prompt=user_prompt,
                evaluated_provisions=evaluated_labels,
            )

        # Fallback offline / środowisko testowe bez kluczy API
        return self._local_heuristic_evaluator(
            promise_id=promise_id,
            promise_text=promise_text,
            project_id=project_id,
            provisions=provisions,
        )

    def _call_gemini(
        self,
        promise_id: str,
        project_id: str,
        user_prompt: str,
        evaluated_provisions: list[str],
    ) -> PromiseEvaluation:
        """Wywołuje API Google Gemini z wymuszonym schematem JSON Schema."""
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model_name}:generateContent?key={self._gemini_key}"
        )
        headers = {"Content-Type": "application/json"}
        json_schema = PromiseEvaluation.model_json_schema()

        payload = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": json_schema,
                "temperature": 0.1,
            },
        }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                content_text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed_json = json.loads(content_text)
                return PromiseEvaluation.model_validate(parsed_json)
        except Exception:
            return self._fallback_error_evaluation(promise_id, project_id, evaluated_provisions)

    def _call_openai(
        self,
        promise_id: str,
        project_id: str,
        user_prompt: str,
        evaluated_provisions: list[str],
    ) -> PromiseEvaluation:
        """Wywołuje API OpenAI z modelem obsługującym JSON mode."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._openai_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        }

        try:
            with httpx.Client(timeout=30) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                content_text = data["choices"][0]["message"]["content"]
                parsed_json = json.loads(content_text)
                return PromiseEvaluation.model_validate(parsed_json)
        except Exception:
            return self._fallback_error_evaluation(promise_id, project_id, evaluated_provisions)

    def _local_heuristic_evaluator(
        self,
        promise_id: str,
        promise_text: str,
        project_id: str,
        provisions: list[ParsedProvision],
    ) -> PromiseEvaluation:
        """Algorytmiczny ewaluator heurystyczny na potrzeby testów jednostkowych i pracy offline."""
        evaluated_labels = [p.context_path for p in provisions]
        all_text = " ".join(p.text.lower() for p in provisions)
        p_lower = promise_text.lower()

        # Wykrycie słów kluczowych
        promise_keywords = {w for w in p_lower.split() if len(w) > 4}
        overlap = sum(1 for kw in promise_keywords if kw in all_text)

        if overlap >= 3:
            # Sprawdzenie negacji lub wyłączeń
            if any(term in all_text for term in ["z wyjątkiem", "wyłącza się", "nie dotyczy"]):
                return PromiseEvaluation(
                    promise_id=promise_id,
                    project_id=project_id,
                    alignment_status="CZESCIOWO",
                    justification="Projekt realizuje postulat z ograniczeniami lub wyłączeniami podmiotowymi.",
                    divergence_details="Zidentyfikowano klauzule wyłączające część beneficjentów.",
                    confidence_score=0.85,
                    evaluated_provisions=evaluated_labels,
                )
            return PromiseEvaluation(
                promise_id=promise_id,
                project_id=project_id,
                alignment_status="W_PELNI",
                justification="Zapisy projektu ustawy w pełni pokrywają się z celem deklaracji.",
                divergence_details=None,
                confidence_score=0.90,
                evaluated_provisions=evaluated_labels,
            )

        if overlap >= 1:
            return PromiseEvaluation(
                promise_id=promise_id,
                project_id=project_id,
                alignment_status="CZESCIOWO",
                justification="Częściowa zbieżność terminologiczna; wymagana weryfikacja analityka.",
                divergence_details="Ograniczony zakres wspólnych dyspozycji.",
                confidence_score=0.65,  # Wymaga weryfikacji manualnej (< 0.70)
                evaluated_provisions=evaluated_labels,
            )

        return PromiseEvaluation(
            promise_id=promise_id,
            project_id=project_id,
            alignment_status="BRAK_POWIAZANIA",
            justification="Brak istotnych zbieżności merytorycznych między przepisami a obietnicą.",
            divergence_details=None,
            confidence_score=0.80,
            evaluated_provisions=evaluated_labels,
        )

    def _fallback_error_evaluation(
        self, promise_id: str, project_id: str, evaluated_provisions: list[str]
    ) -> PromiseEvaluation:
        """Tworzy awaryjny rekord z niską pewnością oznaczony do ręcznego przeglądu."""
        return PromiseEvaluation(
            promise_id=promise_id,
            project_id=project_id,
            alignment_status="CZESCIOWO",
            justification="Błąd sieciowy podczas wnioskowania LLM; rekord skierowany do analizy manualnej.",
            divergence_details="API LLM było niedostępne lub zwróciło odpowiedź niezgodną ze schematem.",
            confidence_score=0.10,
            evaluated_provisions=evaluated_provisions,
        )
