# Przewodnik dla Współtwórców (Contributing Guide)

Dziękujemy za zainteresowanie rozwojem projektu **Weryfikator Obietnic**! Jest to inicjatywa open-source mająca na celu zwiększanie transparentności procesów legislacyjnych w Polsce poprzez automatyczny audyt obietnic wyborczych przy użyciu modeli RAG, analiz OSR i otwartych danych Sejmu RP.

Każda pomoc – od poprawy literówek w dokumentacji, przez zgłaszanie błędów, po nowe algorytmy analizy prawnej – jest niezwykle cenna.

---

## 1. Wymagania Wstępne

Przed rozpoczęciem upewnij się, że masz zainstalowane następujące narzędzia:
- **Python**: Wersja 3.12+ (zalecane zarządzanie przez [`uv`](https://docs.astral.sh/uv/))
- **Node.js**: Wersja 20 LTS lub nowsza
- **pnpm**: Wersja 9+ (`corepack enable pnpm`)
- **Docker & Docker Compose**: Do uruchomienia lokalnej bazy PostgreSQL z `pgvector` oraz instancji Apache Airflow
- **Git**: Do kontroli wersji

---

## 2. Szybki Start: Uruchomienie Środowiska Lokalnego

Wykonaj poniższe kroki w terminalu:

### Krok 1: Klonowanie Repozytorium
```bash
git clone https://github.com/FranekJemiolo/weryfikatorobietnic.git
cd weryfikatorobietnic
```

### Krok 2: Konfiguracja Zależności Pythona (`uv`)
Projekt używa menedżera `uv` do błyskawicznego rozwiązywania zależności i tworzenia wirtualnego środowiska:
```bash
# Instalacja wszystkich pakietów projektu (wraz z narzędziami dev: pytest, ruff, mypy)
uv sync
```

### Krok 3: Uruchomienie Usług Pomocniczych (Docker)
Wystartuj kontenery z bazą PostgreSQL (zainstalowane rozszerzenie `pgvector`) oraz lokalnym Apache Airflow:
```bash
docker compose up -d postgres
```
*Uwaga: Jeśli chcesz rozwijać DAG-i ETL, możesz uruchomić również scheduler i webserwer Airflow poleceniem: `docker compose up -d`.*

### Krok 4: Załadowanie Złotej Bazy Obietnic (Seed)
Zainicjalizuj strukturę tabel i wczytaj bazowy zestaw obietnic wyborczych:
```bash
uv run python -m src.scripts.seed_promises
```

### Krok 5: Uruchomienie Backend API (FastAPI)
```bash
uv run uvicorn src.api.main:app --reload --port 8000
```
API będzie dostępne pod adresem: `http://localhost:8000`.
Interaktywna dokumentacja Swagger UI dostępna jest pod adresem: `http://localhost:8000/docs`.

### Krok 6: Uruchomienie Frontendu (Next.js)
W nowym oknie terminala:
```bash
cd frontend
pnpm install
pnpm dev
```
Interfejs webowy PWA będzie dostępny pod adresem: `http://localhost:3000`.

---

## 3. Standardy Jakości Kodu (Quality Gates)

Żaden Pull Request nie zostanie zaakceptowany, jeśli nie przejdzie wszystkich automatycznych testów jakości. Przed wysłaniem zmian upewnij się, że poniższe polecenia kończą się sukcesem (kod wyjścia 0):

### A. Weryfikacja Backendu (Python)
```bash
# 1. Sprawdzenie formatowania i reguł lintera (Ruff)
uv run ruff check .

# 2. Statyczna kontrola typów (Mypy)
uv run mypy src/ tests/ dags/

# 3. Uruchomienie testów jednostkowych i integracyjnych (Pytest)
uv run pytest -v
```

### B. Weryfikacja Frontendu (TypeScript / Next.js)
```bash
cd frontend

# 1. Sprawdzenie typowania w TypeScript
pnpm run typecheck

# 2. Linter Next.js (ESLint)
pnpm run lint

# 3. Test budowania produkcyjnego
pnpm run build
```

---

## 4. Wytyczne Tworzenia Kodu (Coding Standards)

### Backend:
- **Logowanie**: Bezwzględny zakaz używania instrukcji `print()`. Zawsze importuj i używaj loggera `src.core.logger.get_logger(__name__)`. Logi muszą mieć postać ustrukturyzowaną z kluczami kontekstowymi (`logger.info("nazwa_zdarzenia", promise_id=..., status=...)`).
- **Baza Danych**: Używaj modeli `SQLModel`. Wszelkie obliczenia agregujące (`COUNT`, `AVG`, `SUM`) muszą być delegowane do bazy danych za pomocą funkcji SQLAlchemy (`func.count`, `func.avg`), a nie przeliczane w pamięci RAM Pythona.
- **Odporność na błędy**: Klienty HTTP komunikujące się z API Sejmu lub Google Gemini muszą korzystać ze strategii Exponential Backoff (`tenacity`).

### Frontend:
- **Server Components**: Preferuj asynchroniczne React Server Components (`RSC`) do pobierania danych i SEO. Komponenty oznaczaj dyrektywą `"use client"` wyłącznie wtedy, gdy korzystają z hooków Reacta (`useState`, `useEffect`, `useQuery`) lub nasłuchują na zdarzenia przeglądarki.
- **Styling**: Używaj wyłącznie Vanilla CSS i Tailwind CSS. Korzystaj z gotowego systemu tokenów zdefiniowanych w `@/components/ui/` (shadcn/ui).
- **Wydajność**: Pola wyszukiwania muszą być optymalizowane hookiem `useDebounce`, a wykresy muszą być osadzone w `ResponsiveContainer`.

---

## 5. Proces Zgłaszania Zmian (Pull Request Workflow)

1. **Utwórz Fork** repozytorium na swoje konto GitHub.
2. **Utwórz nową gałąź** z opisową nazwą:
   - Nowa funkcja: `git checkout -b feat/wyszukiwanie-frazeologiczne`
   - Poprawka błędu: `git checkout -b fix/kalkulacja-kosztu-osr`
   - Dokumentacja: `git checkout -b docs/instrukcja-instalacji`
3. **Formatuj Commity** zgodnie ze standardem [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat(api): dodanie endpointu eksportu danych CSV`
   - `fix(rag): poprawka odrzucania wykluczonych artykułów`
   - `docs(readme): aktualizacja architektury projektu`
4. **Wyślij Pull Request (PR)** do gałęzi `main` z dokładnym opisem wprowadzonych modyfikacji, zrzutami ekranu (dla zmian UI) oraz informacją o pomyślnym wykonaniu testów.

---

## 6. Kontakt i Pomoc

W razie wątpliwości architektonicznych lub pytań technicznych:
- Otwórz zgłoszenie w sekcji [GitHub Issues](https://github.com/FranekJemiolo/weryfikatorobietnic/issues).
- Dołącz do dyskusji w zakładce [GitHub Discussions](https://github.com/FranekJemiolo/weryfikatorobietnic/discussions).

*Dziękujemy za budowanie narzędzia, które realnie wspiera polską demokrację i kontrolę obywatelską!*
