# Wymagania Systemowe i Przewodnik Uruchomienia Lokalnego
## Projekt: Weryfikator Obietnic

Niniejszy dokument precyzuje rygorystyczne wymagania sprzętowe, programowe oraz konfigurację poświadczeń i zewnętrznych API niezbędnych do stabilnego uruchomienia całego stosu technologicznego (PostgreSQL + pgvector, Apache Airflow, FastAPI, Next.js PWA, RAG/LLM).

---

## 1. Wymagania Sprzętowe (Hardware Requirements)

System "Weryfikator Obietnic" przetwarza obszerne korpusy dokumentów legislacyjnych (wielostronicowe załączniki PDF, obliczenia OSR) oraz wykonuje operacje na przestrzeniach wektorowych (indeksy HNSW, operacje dystansu kosinusowego). Z tego względu orkiestracja w kontenerach Docker wymaga odpowiednio zwymiarowanych zasobów.

| Parametr | Minimalne | Zalecane (Produkcja / Pełny ETL) |
| :--- | :--- | :--- |
| **Pamięć RAM** | **8 GB** (przydzielone min. 6 GB dla silnika Docker) | **16 GB - 32 GB** |
| **Procesor (CPU)** | 4 rdzenie (x86_64 lub Apple Silicon ARM64) | 8 rdzeni |
| **Przestrzeń dyskowa** | 15 GB wolnego miejsca na dysku SSD | 40+ GB SSD (obrazy Docker, wektory pgvector, cache PDF) |
| **Łącze sieciowe** | 10 Mbps (pobieranie PDF i komunikacja z Sejm API) | 50+ Mbps |

> [!WARNING]
> **Alokacja Pamięci w Docker Desktop:**
> Domyślna alokacja Docker Desktop na systemach macOS i Windows (często 2 GB lub 4 GB RAM) **doprowadzi do błędu OOM (Out Of Memory)** podczas jednoczesnego uruchamiania Airflow Webservera, Schedulera i budowania indeksów wektorowych w PostgreSQL.
> Upewnij się, że w *Docker Desktop -> Settings -> Resources* przydzielono **co najmniej 6-8 GB RAM**.

---

## 2. Wymagania Programowe (Software Requirements)

Do zarządzania projektem i uruchamiania skryptów wymagane są następujące narzędzia zainstalowane na maszynie deweloperskiej:

1. **Docker Engine & Docker Compose:**
   - Docker v24.0+
   - Docker Compose v2.20+
2. **Środowisko Python:**
   - Python 3.12+
   - Menedżer pakietów **`uv`** (wersja >= 0.4.0) – `curl -LsSf https://astral.sh/uv/install.sh | sh`
3. **Środowisko Node.js (Frontend):**
   - Node.js v20.x LTS
   - Menedżer pakietów **`pnpm`** (wersja >= 9.x) – `npm install -g pnpm`
4. **Narzędzie Make:**
   - `make` (dostępne domyślnie w systemach Linux oraz macOS Command Line Tools).

---

## 3. Zewnętrzne API i Klucze Środowiskowe

Projekt wymaga skonfigurowania pliku `.env` w głównym katalogu repozytorium (na bazie dostarczonego szablonu `.env.example`).

### A. Wymagane Dostawcy Modeli LLM i Embeddings
Do działania silnika RAG (wyszukiwanie semantyczne ustaw i wnioskowanie rozbieżności z obietnicami):
- **Google Gemini API (Domyślne):**
  - Zmienna: `GEMINI_API_KEY=AIzaSy...`
  - Model: `gemini-1.5-flash` lub `gemini-1.5-pro`
  - Pozyskanie klucza: [Google AI Studio](https://aistudio.google.com/)
- **Opcjonalnie: OpenAI API:**
  - Zmienna: `OPENAI_API_KEY=sk-...`

### B. Otwarte API Instytucjonalne (Bez Kluczy)
Poniższe interfejsy są w pełni publiczne i nie wymagają autoryzacji tokenem, jednak nasze klienty wysyłają transparentny nagłówek `User-Agent` i stosują politykę uprzejmości (politeness delay):
- **Sejm OpenAPI:** `https://api.sejm.gov.pl/sejm` (X kadencja Sejmu RP)
- **ISAP / ELI API:** `https://api.sejm.gov.pl/eli` (baza Dziennika Ustaw i Monitora Polskiego)
- **Kanały RSS:** `https://www.gov.pl/web/premier/komunikaty?format=rss`, `https://legislacja.gov.pl/rss`

---

## 4. Poświadczenia Lokalne i Autoryzacja

Dla lokalnego środowiska deweloperskiego przyjęto spójny, bezpieczny zestaw domyślnych portów i poświadczeń:

### A. Apache Airflow (Zarządzanie Potokami Danych)
- **Adres panelu WWW:** [http://localhost:8080](http://localhost:8080)
- **Domyślny Login:** `admin`
- **Domyślne Hasło:** `admin`
- **Rola:** `Admin` (pełne uprawnienia do podglądu DAG-ów, ręcznego wyzwalania potoków i inspekcji logów)

### B. PostgreSQL + pgvector (Główny Magazyn Relacyjny i Wektorowy)
- **Host:** `localhost` (lub w sieci Dockera: `postgres`)
- **Port:** `5432`
- **Użytkownik:** `user`
- **Hasło:** `pass`
- **Baza danych:** `weryfikator`
- **Parametry połączenia (SQLAlchemy/SQLModel):**
  ```bash
  DATABASE_URL=postgresql://user:pass@localhost:5432/weryfikator
  ```

### C. FastAPI Backend (Interfejs API dla Obywateli)
- **Adres serwera:** [http://localhost:8000](http://localhost:8000)
- **Interaktywna dokumentacja OpenAPI (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternatywna dokumentacja (ReDoc):** [http://localhost:8000/redoc](http://localhost:8000/redoc)

### D. Next.js PWA Frontend (Aplikacja Webowa)
- **Adres aplikacji:** [http://localhost:3000](http://localhost:3000)

---

## 5. Procedura Uruchomienia Krok po Kroku

Wszystkie operacje zostały zautomatyzowane w pliku [`Makefile`](file:///Users/franek/personal_workspace/weryfikatorobietnic/Makefile):

```bash
# 1. Klonowanie repozytorium i przejście do katalogu
git clone git@github.com:FranekJemiolo/weryfikatorobietnic.git
cd weryfikatorobietnic

# 2. Przygotowanie pliku zmiennych środowiskowych
cp .env.example .env
# Uzupełnij swój klucz GEMINI_API_KEY w pliku .env

# 3. Pełna inicjalizacja środowiska (build kontenerów, migracje bazy i konto admina Airflow)
make init

# 4. Zasilenie bazy danych 'Złotą Bazą Obietnic' (100 deklaracji)
make seed

# 5. Uruchomienie wszystkich kontenerów w tle
make start

# 6. Uruchomienie testów automatycznych
make test
```

---

## 6. Rozwiązywanie Problemów (Troubleshooting)

### Problem 1: Port 5432 lub 8080 jest już zajęty
- **Objaw:** Błąd `Bind for 0.0.0.0:5432 failed: port is already allocated`.
- **Rozwiązanie:** Lokalnie działa inna instancja PostgreSQL lub usługa na porcie 8080. Zatrzymaj lokalny serwis (`brew services stop postgresql` lub zatrzymaj kontenery kolidujące) albo zmień mapowanie portów w `docker-compose.yml`.

### Problem 2: Kontenery Airflow ulegają awarii (Exit Code 137)
- **Objaw:** Kontener `weryfikator_airflow_scheduler` nagle znika lub zgłasza `Killed`.
- **Przyczyna:** Kod 137 oznacza interwencję Linux OOM Killer (brak pamięci RAM).
- **Rozwiązanie:** Zwiększ pamięć w konfiguracji Docker Desktop do min. 6-8 GB.

### Problem 3: Błąd rozszerzenia pgvector przy migracji
- **Objaw:** `type "vector" does not exist`.
- **Rozwiązanie:** Upewnij się, że obrazem bazy danych jest oficjalny obraz `ankane/pgvector:v0.5.1` (który automatycznie instaluje bibliotekę wektorową w PostgreSQL), a skrypt `docker/init_db.sql` zawiera dyrektywę `CREATE EXTENSION IF NOT EXISTS vector;`.
