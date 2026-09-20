# Standardy Inżynieryjne i Wytyczne Deweloperskie
**Projekt:** Weryfikator Obietnic  
**Wydanie:** 1.0 (Oficjalna Biblia Kodowania)  
**Status:** Obowiązujący dla wszystkich współtwórców  

---

## 1. Filozofia Architektoniczna i Jakość Kodu

Weryfikator Obietnic to projekt infrastruktury zaufania publicznego. Kod musi cechować się:
1. **Determinizmem**: Identyczne dane wejściowe muszą zawsze dawać identyczny wynik ewaluacji.
2. **Bezkompromisowym Typowaniem**: Całkowity zakaz stosowania typów niejawnych (`Any` bez uzasadnienia, brak adnotacji parametrów lub zwracanych wartości).
3. **Odpornością na Błędy (Resilience)**: Każde wywołanie zewnętrzne (Sejm API, Google Gemini, baza danych) musi posiadać mechanizmy timeoutów, automatycznych ponowień i graceful degradation.
4. **Wydajnością z Założenia**: Ciężkie operacje matematyczne i agregacje delegujemy do silnika bazy danych, a nie do wątków Pythona czy przeglądarki klienta.

---

## 2. Standardy dla Backendu (Python 3.12 / FastAPI / SQLModel / Airflow)

### 2.1. Type Hints i Walidacja Pydantic v2
- Wszystkie sygnatury funkcji i metod muszą posiadać pełne typowanie zgodne ze standardem **PEP 484 / PEP 604**:
  ```python
  # PRAWIDŁOWO (Python 3.10+ syntax):
  def calculate_delivery_rate(fulfilled: int, total: int) -> float | None:
      if total == 0:
          return None
      return round((fulfilled / total) * 100.0, 2)


  # BŁĘDNIE (Przestarzała składnia typing.Optional / brak typów):
  def calculate_delivery_rate(fulfilled, total): ...
  ```
- Wszystkie modele transferu danych (DTO) oraz schematy żądań i odpowiedzi API muszą dziedziczyć z `pydantic.BaseModel` lub `sqlmodel.SQLModel` z jawną konfiguracją:
  ```python
  class PromiseFilterRequest(BaseModel):
      party: str = Field(..., min_length=2, max_length=50, description="Kod partii")
      limit: int = Field(default=20, ge=1, le=100)

      model_config = ConfigDict(from_attributes=True, extra="forbid")
  ```

### 2.2. Dependency Injection w FastAPI
- **Zakaz tworzenia sesji "ad-hoc" w handlerach**: Nigdy nie twórz bezpośrednich instancji `Session(engine)` wewnątrz tras endpointów. Zawsze korzystaj z mechanizmu wstrzykiwania zależności (`FastAPI Dependency Injection`):
  ```python
  # src/api/routes.py
  from typing import Annotated
  from fastapi import Depends
  from sqlmodel import Session
  from src.database.engine import get_session

  # Zdefiniowany typ zależności
  SessionDep = Annotated[Session, Depends(get_session)]


  @router.get("/promises/{id}")
  async def get_promise(id: str, session: SessionDep) -> PromiseResponse:
      # Sesja zarządzana jest automatycznie w ramach cyklu życia requestu
      promise = session.get(Promise, id)
      ...
  ```
- Generator `get_session` w `src/database/engine.py` musi gwarantować bezpieczne zamknięcie połączenia w bloku `finally`:
  ```python
  def get_session() -> Generator[Session, None, None]:
      with Session(engine) as session:
          yield session
  ```

### 2.3. Zasady Pisania Idempotentnych Tasków w Apache Airflow
Każdy task w potokach ETL (`@task`) musi spełniać kryterium **pełnej idempotentności**: wielokrotne uruchomienie tego samego zadania (np. z powodu ponowienia po błędzie sieciowym lub ponownego przeliczenia z przeszłości) musi dać identyczny stan w bazie danych.

1. **Używaj Operacji UPSERT / Merge zamiast czystych `INSERT`**:
   ```python
   # W PostgreSQL używaj klauzuli ON CONFLICT:
   stmt = (
       insert(Promise)
       .values(new_data)
       .on_conflict_do_update(
           index_elements=[Promise.id], set_={"title": new_data["title"], "updated_at": func.now()}
       )
   )
   ```
2. **Deduplikacja za pomocą Skrótów Kryptograficznych (SHA-256)**:
   - Przed zapisaniem nowej wersji dokumentu lub zrzutu strony partii, oblicz sumę kontrolną SHA-256 (`content_hash`). Zapisuj nowy rekord tylko wtedy, gdy hash uległ zmianie.
3. **Zasada "Lekkich XCom" (Thin XComs)**:
   - Bezwzględny zakaz przekazywania dużych payloadów (surowych plików PDF, setek tysięcy znaków HTML) przez mechanizm XCom Airflow. Przekazuj wyłącznie metadane: identyfikatory (`bill_id`) lub ścieżki w magazynie obiektowym (`storage_path`).

### 2.4. Ustrukturyzowane Logowanie (Zakaz `print()`)
- Wszystkie moduły muszą korzystać z loggera `structlog`:
  ```python
  from src.core.logger import get_logger

  logger = get_logger(__name__)

  # PRAWIDŁOWO:
  logger.info("bill_evaluated", bill_id=bill.id, status=status.value, score=0.95)

  # ZABRONIONE:
  print(f"Oceniono ustawe {bill.id} z wynikiem {status}")
  ```

### 2.5. Dyscyplina Linterów i Narzędzi Statycznych
Przed wysłaniem kodu do repozytorium kod musi spełniać wymagania:
```bash
# 1. Sprawdzenie formatu i reguł jakości kodu (Ruff)
uv run ruff check .
uv run ruff format --check .

# 2. Rygorystyczna analiza typów (Mypy)
uv run mypy src/ tests/ dags/
```

---

## 3. Standardy dla Frontendu (TypeScript / Next.js / Tailwind CSS)

### 3.1. Podział: Server Components (RSC) vs Client Components
1. **React Server Components (RSC) - Domyślny Standard**:
   - Wszystkie strony (`page.tsx`) oraz kontenery layoutów (`layout.tsx`) muszą być asynchronicznymi komponentami serwerowymi.
   - Pobierają dane bezpośrednio przez `fetch` z natywnym mechanizmem `next: { revalidate: X }` (Incremental Static Regeneration).
   - Generują metadane SEO (`generateMetadata`).
   - Nie wysyłają do przeglądarki żadnego kodu JavaScript dla statycznej części strony.
2. **Client Components (`"use client"`) - Zasada Minimalizacji**:
   - Oznaczaj plik dyrektywą `"use client"` wyłącznie na samym dole drzewa komponentów, gdy:
     * Komponent zarządza stanem formularza (`useState`, `useReducer`),
     * Komponent korzysta z bibliotek wizualizacji wymagających obiektu `window` lub `document` (np. `recharts`),
     * Komponent nasłuchuje na zdarzenia interfejsu (`onClick`, `onChange`),
     * Komponent korzysta z hooków TanStack Query (`useQuery`).

### 3.2. Styling z Tailwind CSS, `cn` i shadcn/ui
- **Łączenie Klas Warunkowych**: Zawsze używaj pomocnika `cn()` z `@/lib/utils` (łączącego `clsx` i `tailwind-merge`), aby zapobiec konfliktom stylów CSS:
  ```tsx
  import { cn } from "@/lib/utils";

  export function StatusBadge({ isCompleted, className }: BadgeProps) {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold",
          isCompleted
            ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
            : "bg-slate-800 text-slate-400 border border-slate-700",
          className
        )}
      >
        ...
      </span>
    );
  }
  ```
- **Spójność Wizualna**: Nie wprowadzaj nowych, przypadkowych kolorów w kodzie CSS. Używaj wyłącznie palety semantycznej zdefiniowanej w projekcie:
  * Kolor sukcesu / realizacji: `emerald-400` / `emerald-500`
  * Kolor prac w toku: `amber-400` / `amber-500`
  * Kolor złamanej obietnicy / błędu: `rose-400` / `rose-500`
  * Tła i panele: `slate-900`, `slate-950` z ramkami `border-slate-800`

### 3.3. Obsługa Stanów Asynchronicznych (TanStack Query)
Żaden komponent kliencki nie może wyświetlić pustego ekranu podczas oczekiwania na dane. Wymagane jest pokrycie trzech stanów cyklu zapytania:
1. **Stan Ładowania (`isLoading` / `isPending`)**: Wyrenderowanie komponentu szkieletowego (`*Skeleton`) z animacją `animate-pulse`, zachowującego identyczny układ i wymiary jak treść docelowa.
2. **Stan Błędu (`isError`)**: Czytelny komunikat dla użytkownika z przyciskiem umożliwiającym ponowienie zapytania (`refetch()`).
3. **Stan Pusty (Empty State)**: Informacja w przypadku braku wyników (np. brak obietnic dla wybranego filtra w wyszukiwarce) wraz z propozycją zresetowania filtrów.

---

## 4. Git Flow i Standardy Wytwarzania Oprogramowania

### 4.1. Model Gałęzi (Trunk-Based Development)
- Główna, stabilna gałąź projektu to `main`. Kod w `main` musi być w każdym momencie zdatny do wdrożenia na produkcję.
- Prace programistyczne prowadzone są na krótkich gałęziach funkcyjnych (czas życia gałęzi < 2 dni).
- Nazewnictwo gałęzi:
  * `feat/<krótki-opis>` – nowe funkcjonalności
  * `fix/<krótki-opis>` – poprawki błędów
  * `perf/<krótki-opis>` – optymalizacje wydajnościowe
  * `docs/<krótki-opis>` – dokumentacja

### 4.2. Konwencja Komunikatów Commitów (Conventional Commits 1.0)
Wszystkie commity w repozytorium muszą być sformatowane zgodnie ze wzorcem:
`<typ>(<zakres>): <zwięzły opis w trybie rozkazującym>`

Dopuszczalne typy:
- `feat`: Nowa funkcja w API, silniku AI lub interfejsie użytkownika.
- `fix`: Naprawa zidentyfikowanego błędu.
- `perf`: Zmiana w kodzie poprawiająca czas wykonania lub zużycie zasobów.
- `refactor`: Refaktoryzacja bez zmiany funkcjonalności zewnętrznej.
- `test`: Dodanie lub modyfikacja testów automatycznych.
- `docs`: Zmiany wyłącznie w dokumentacji projektu.
- `chore`: Zmiany konfiguracyjne, aktualizacje zależności, skrypty pomocnicze.

*Przykłady:*
- `feat(api): dodanie paginacji i parametrów wyszukiwania w endpointzie obietnic`
- `fix(parser): obsługa znaków nowej linii w nagłówkach artykułów prawnych`
- `perf(pgvector): dodanie indeksu HNSW dla kolumny embeddingów`

### 4.3. Kryteria Ukończenia i Akceptacji (Definition of Done - DoD)
Pull Request może zostać zmergowany do `main` wyłącznie wtedy, gdy:
1. Wszystkie automatyczne testy jednostkowe i integracyjne kończą się sukcesem (`pytest` - 100% passed).
2. Linter i formater Pythona nie zgłaszają żadnych uwag (`ruff check .`).
3. Analiza typów Mypy kończy się bez błędów w trybie ścisłym (`mypy src/ tests/ dags/`).
4. Kod frontendu przechodzi kontrolę kompilatora TypeScript (`pnpm run typecheck`) oraz lintera Next.js (`pnpm run lint`).
5. Aplikacja Next.js pomyślnie buduje się produkcyjnie (`pnpm run build`).
6. Nowy kod zawiera odpowiednie testy jednostkowe pokrywające zaimplementowaną logikę oraz scenariusze brzegowe.
