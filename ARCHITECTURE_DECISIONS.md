# Rejestr Decyzji Architektonicznych (Architecture Decision Records - ADR)
**Projekt:** Weryfikator Obietnic  
**Główny Architekt:** Principal Staff Engineer  
**Standard Dokumentacji:** MADR 3.0 (Markdown Architectural Decision Records)  

Niniejszy rejestr dokumentuje kluczowe decyzje technologiczne podjęte podczas projektowania platformy "Weryfikator Obietnic". Każdy rekord szczegółowo wyjaśnia kontekst, motywację inżynieryjną ("The Why") oraz wpływ na szybkość wytwarzania oprogramowania (Developer Velocity) i stabilność produkcyjną.

---

## ADR-001: Wybór Python 3.12 oraz Menedżera Pakietów `uv`

### Kontekst:
Projekt łączy zaawansowane biblioteki do analizy danych i AI (`pgvector`, `google-genai`, `pymupdf`, `sqlmodel`, `fastapi`, `apache-airflow`). Tradycyjne narzędzia (`pip`, `pip-tools`, `poetry`) cierpią na wolne rozwiązywanie zależności (Dependency Resolution) sięgające w środowiskach CI/CD od 2 do 5 minut oraz brak determinizmu w środowiskach wielosystemowych.

### Decyzja:
Zastosowanie **Python 3.12** jako bazowego interpretera oraz **`uv`** (napisanego w Rust przez zespół Astral) jako jedynego menedżera pakietów, wirtualnych środowisk i narzędzia uruchomieniowego (`uv run`, `uv sync`, `uv lock`).

### Dlaczego to wybraliśmy ("The Why")?
1. **Skrajna Wydajność i Szybkość CI/CD**: `uv` rozwiązuje i instaluje zależności od 10x do 100x szybciej niż `pip` i `poetry`. Czas instalacji w potoku GitHub Actions skrócił się z ~180 sekund do zaledwie 3 sekund.
2. **Globalny Cache Pakietów**: Mechanizm deduplikacji pobranych kół (wheels) za pomocą linków twardych (hardlinks) oszczędza przestrzeń dyskową na maszynach deweloperskich i runnerach chmurowych.
3. **Deterministyczny `uv.lock`**: Gwarantuje identyczną wersję każdego podrzędnego pakietu na maszynie każdego inżyniera, eliminując błędy typu *"u mnie działa"*.
4. **Python 3.12 Performance**: Usprawnienia interpretera (Faster CPython) oraz ulepszone komunikaty błędów przyspieszają parsowanie tekstów prawnych bez narzutu kompilacji C.

### Alternatywy Odrzucone:
- `Poetry`: Powolny resolver zależności przy dużych drzewach zależności (np. Airflow).
- `pipenv`: Ociężały, problemy z pamięcią podręczną i brak natywnego wsparcia dla formatu `pyproject.toml` zgodnego z PEP 621.

---

## ADR-002: Orkiestracja Danych z Apache Airflow (TaskFlow API)

### Kontekst:
System wymaga ciągłego pobierania danych z API Sejmu, monitorowania zmian na stronach partii (DOM Watchdog), pobierania dużych plików PDF, ekstrakcji OSR i wektoryzacji artykułów. Potrzebowaliśmy narzędzia orkiestracji zapewniającego pełną widoczność, wznawianie w przypadku awarii (Retries) oraz śledzenie przepływu danych (Data Lineage).

### Decyzja:
Wybór **Apache Airflow 2.x** z wykorzystaniem paradygmatu **TaskFlow API** (`@dag`, `@task`).

### Dlaczego to wybraliśmy ("The Why")?
1. **Zarządzanie Zależnościami i Stanem (State Machine)**: Tradycyjny CRON nie posiada świadomości stanu poprzednich zadań ani obsługi błędów kaskadowych. Airflow gwarantuje, że wektoryzacja artykułów (`vectorize_and_save_articles`) uruchomi się wyłącznie wtedy, gdy pobieranie PDF (`process_bill_documents`) zakończyło się sukcesem.
2. **Idempotentność i Backfilling**: Jeśli API Sejmu było niedostępne przez weekend, Airflow automatycznie dogoni zaległe interwały czasowe (Catchup/Backfill) bez dublowania wpisów w bazie.
3. **Czysty Kod z TaskFlow API**: Zastąpienie przestarzałych operatorów (`PythonOperator`) natywnymi dekoratorami `@task` eliminuje boilerplate, a przekazywanie metadanych przez mechanizm XCom jest w pełni typowane.
4. **Zarządzalność Chmurowa**: Natywna zgodność z Google Cloud Composer bez konieczności pisania własnego harmonogramu.

### Alternatywy Odrzucone:
- `CRON + systemd`: Brak interfejsu graficznego, brak automatycznych ponowień z wykładniczym opóźnieniem (Exponential Backoff), brak audytowalności logów poszczególnych kroków.
- `Celery`: Doskonałe do asynchronicznych zadań HTTP, ale brak natywnego silnika DAG (Direct Acyclic Graph) i harmonogramowania kalendarzowego.

---

## ADR-003: Warstwa Persystencji: SQLModel + PostgreSQL (zamiast czystego SQLAlchemy lub MongoDB)

### Kontekst:
Aplikacja operuje na relacjach silnie powiązanych (Poseł -> Głosowania -> Wyniki, Obietnica -> Rewizje -> Ustawa -> Artykuły -> Ewaluacje). Jednocześnie dane te muszą być walidowane przy wejściu do API i serializowane do JSON.

### Decyzja:
Wybór **SQLModel** (łączącego SQLAlchemy Core/ORM z Pydantic v2) na bazie danych **PostgreSQL 16**.

### Dlaczego to wybraliśmy ("The Why")?
1. **Pojedyncze Źródło Prawdy (Single Source of Truth)**: W klasycznym podejściu inżynier musi zdefiniować model tabeli SQLAlchemy, a następnie powielić te same pola w schemacie Pydantic dla FastAPI. SQLModel eliminuje tę redundancję – jedna klasa reprezentuje jednocześnie tabelę SQL i model walidacyjny Pydantic.
2. **ACID i Integralność Relacyjna**: Obietnice wyborcze i powiązane z nimi druki sejmowe wymagają transakcyjności i twardych kluczy obcych (`FOREIGN KEY ... ON DELETE CASCADE`), co chroni przed osieroconymi rekordami.
3. **PostgreSQL jako Ekosystem Zunifikowany**: Dzięki typom `JSONB`, indeksowaniu `GIN` oraz rozszerzeniu `pgvector`, PostgreSQL pełni rolę bazy relacyjnej, dokumentowej i wektorowej w jednym silniku, redukując koszty operacyjne o 60%.

### Alternatywy Odrzucone:
- `MongoDB`: Brak natywnej transakcyjności wielodokumentowej o gwarancjach ACID, brak typowania relacyjnego, trudności w agregacjach typu `JOIN` na tabelach głosowań poselskich.
- `Czyste SQLAlchemy + Pydantic`: Podwójny narzut pracy deweloperskiej przy utrzymywaniu dwóch równoległych hierarchii klas dla każdego bytu domenowego.

---

## ADR-004: Architektura RAG + pgvector (zamiast Olbrzymiego Okna Kontekstowego LLM)

### Kontekst:
Pojedyncza ustawa procedowana w Sejmie RP potrafi liczyć od kilkudziesięciu do kilkuset stron maszynopisu (od 20 000 do 500 000 tokenów). Nowoczesne modele LLM (np. Gemini z oknem 1M+ tokenów) pozwalają technicznie na przesłanie całego dokumentu w jednym prompcie.

### Decyzja:
Zastosowanie architektury **Retrieval-Augmented Generation (RAG)** z krojeniem tekstu na artykuły (Legal Chunking), generowaniem embeddingów wektorowych (1536 wymiarów) i wyszukiwaniem semantycznym w rozszerzeniu **`pgvector`** PostgreSQL.

### Dlaczego to wybraliśmy ("The Why")?
1. **Redukcja Halucynacji i Zjawiska "Lost in the Middle"**: Wrzucenie 200 stron ustawy do LLM drastycznie zwiększa ryzyko pominięcia kluczowego artykułu ukrytego w przepisach przejściowych. RAG wyciąga dokładnie te 5 artykułów, które bezpośrednio odnoszą się do postulatu obietnicy.
2. **Precyzja Cytowania Audytorskiego**: Aby obywatel zaufał werdyktowi AI, system musi podać konkretny przepis prawny (np. *„Art. 4 ust. 2 ustawy z dnia...”*). RAG umożliwia bezpośrednie powiązanie oceny z identyfikatorem rekordu w `bill_articles`.
3. **Koszty API i Latencja**:
   - Koszt zapytania z pełną ustawą (200k tokenów): ~$0.05 / zapytanie, czas odpowiedzi: 12-25 sekund.
   - Koszt zapytania RAG (Top-5 artykułów, ~2k tokenów): ~$0.0005 / zapytanie, czas odpowiedzi: 1.2 sekundy.
   - Oszczędność finansowa: **99%**, przyspieszenie odpowiedzi: **10x**.

### Alternatywy Odrzucone:
- `Dedykowane bazy wektorowe (Pinecone / Qdrant)`: Wprowadzenie dodatkowego komponentu infrastruktury, problem z synchronizacją transakcyjną (oddzielna baza na wektory, oddzielna na metadane w SQL). `pgvector` pozwala na złączenie zapytań wektorowych ze zwykłym filtrem SQL w jednym poleceniu `SELECT`.

---

## ADR-005: Rozdzielona Architektura: FastAPI + Next.js App Router (zamiast Monolitu Django/Jinja)

### Kontekst:
Platforma musi łączyć szybkie, asynchroniczne REST API dla obywateli, dziennikarzy i organizacji pozarządowych z interfejsem webowym Progressive Web App (PWA) o bezkompromisowej estetyce, responsywności i natychmiastowym ładowaniu (SEO / FCP).

### Decyzja:
Architektura rozdzielona (Decoupled):
- **Backend**: Asynchroniczne REST API w **FastAPI** z automatyczną dokumentacją OpenAPI.
- **Frontend**: **Next.js (App Router)** z React Server Components, Tailwind CSS i TanStack Query.

### Dlaczego to wybraliśmy ("The Why")?
1. **Zasada Otwartego Państwa (Open API First)**: Dane publiczne wygenerowane przez system muszą być dostępne nie tylko przez stronę WWW, ale również programistycznie dla innych serwisów i analityków. FastAPI generuje w standardzie specyfikację OpenAPI (Swagger UI).
2. **Optymalne SEO i Szybkość (Server Components)**: Profile posłów i szczegóły obietnic są renderowane po stronie serwera w Next.js (RSC/ISR), co zapewnia indeksowanie przez wyszukiwarki i natychmiastowy First Contentful Paint bez wysyłania zbędnego JavaScriptu.
3. **Instalacja Mobilna (PWA)**: Obywatele mogą zainstalować Weryfikator Obietnic na ekranie smartfona jak natywną aplikację mobilną z obsługą Service Workera i pamięcią podręczną.
4. **Zarządzanie Stanem Klienta przez TanStack Query**: Automatyczny caching, deduplikacja zapytań w locie, wbudowane stany `isLoading` i optymistyczne odświeżanie danych bez konieczności pisania skomplikowanych reducerów w Redux.

### Alternatywy Odrzucone:
- `Django + Jinja2 (Monolit)`: Brak asynchronicznego I/O w standardzie, trudność w budowie nowoczesnych wykresów reaktywnych (np. Recharts Donut) bez pisania spaghetti w jQuery/Vanilla JS, brak natywnego wsparcia dla PWA i streamingu Reacta.
