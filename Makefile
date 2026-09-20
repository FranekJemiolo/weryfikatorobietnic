# ==============================================================================
# Makefile - Weryfikator Obietnic
# Zarządzanie środowiskiem deweloperskim, orkiestracją i testami
# ==============================================================================

.PHONY: help init seed start stop down restart logs test lint format clean isap-sync fetch-parties

# Domyślny cel - pomoc
help:
	@echo "Dostępne komendy projektu 'Weryfikator Obietnic':"
	@echo "  make init        - Buduje obrazy Docker, inicjalizuje bazę Airflow i odpala migracje Alembic"
	@echo "  make seed        - Wgrywa 'Złotą Bazę Obietnic' do bazy PostgreSQL"
	@echo "  make start       - Uruchamia całe środowisko deweloperskie w tle (Docker Compose)"
	@echo "  make stop        - Zatrzymuje działające kontenery środowiska"
	@echo "  make down        - Zatrzymuje kontenery i usuwa wolumeny sieciowe"
	@echo "  make restart     - Restartuje kontenery deweloperskie"
	@echo "  make logs        - Śledzi logi wszystkich kontenerów w czasie rzeczywistym"
	@echo "  make test        - Uruchamia pełny zestaw testów jednostkowych (pytest + uv)"
	@echo "  make lint        - Sprawdza poprawność typowania (mypy) oraz reguły lintera (ruff)"
	@echo "  make format      - Automatycznie formatuje kod źródłowy (ruff format)"
	@echo "  make isap-sync   - Ręcznie wyzwala synchronizację uchwalonych ustaw z ISAP"
	@echo "  make fetch-data  - Pobiera dane ze stron wszystkich partii politycznych oraz kanałów RSS"

# ------------------------------------------------------------------------------
# 1. INICJALIZACJA ŚRODOWISKA
# ------------------------------------------------------------------------------
init:
	@echo "🚀 [1/4] Budowanie obrazów kontenerów..."
	docker compose build
	@echo "🐘 [2/4] Uruchamianie bazy PostgreSQL (pgvector)..."
	docker compose up -d postgres
	@echo "⏳ Oczekiwanie na gotowość bazy danych PostgreSQL..."
	@until docker compose exec -T postgres pg_isready -U user -d weryfikator; do sleep 1; done
	@echo "📦 [3/4] Uruchamianie migracji bazy danych (Alembic)..."
	uv run alembic upgrade head || docker compose run --rm api uv run alembic upgrade head
	@echo "🌪️ [4/4] Inicjalizacja bazy metadanych Apache Airflow i tworzenie konta administratora..."
	docker compose run --rm airflow-init
	@echo "✅ Środowisko zostało pomyślnie zainicjalizowane!"
	@echo "👉 Uruchom 'make start', aby włączyć usługi."

# ------------------------------------------------------------------------------
# 2. ZASILANIE DANYMI REFERENCYJNYMI
# ------------------------------------------------------------------------------
seed:
	@echo "🌱 Wgrywanie 'Złotej Bazy Obietnic' do PostgreSQL..."
	uv run python -m src.scripts.seed_promises
	@echo "✅ Baza została zasilona danymi referencyjnymi!"

# ------------------------------------------------------------------------------
# 3. ZARZĄDZANIE KONTENERAMI
# ------------------------------------------------------------------------------
start:
	@echo "▶️ Uruchamianie usług (Postgres, Airflow Webserver/Scheduler, FastAPI)..."
	docker compose up -d
	@echo "🎉 Wszystkie usługi działają!"
	@echo "• FastAPI Backend:       http://localhost:8000/docs"
	@echo "• Airflow Webserver:     http://localhost:8080 (login: admin / hasło: admin)"
	@echo "• PostgreSQL (pgvector): localhost:5432 (baza: weryfikator)"

stop:
	@echo "⏹️ Zatrzymywanie kontenerów..."
	docker compose stop

down:
	@echo "🛑 Usuwanie kontenerów i sieci..."
	docker compose down

restart: stop start

logs:
	docker compose logs -f

# ------------------------------------------------------------------------------
# 4. JAKOŚĆ KODU I TESTY
# ------------------------------------------------------------------------------
test:
	@echo "🧪 Uruchamianie testów jednostkowych i integracyjnych..."
	uv run pytest -v

lint:
	@echo "🔍 Sprawdzanie formatowania i linterów..."
	uv run ruff check .
	uv run ruff format --check src/ tests/ dags/
	@echo "🧠 Statyczna analiza typów (mypy)..."
	uv run mypy src/ tests/ dags/
	@echo "✨ Frontend typecheck & lint..."
	pnpm --dir frontend run typecheck
	pnpm --dir frontend run lint

format:
	@echo "🎨 Automatyczne formatowanie kodu (Ruff)..."
	uv run ruff check --fix .
	uv run ruff format .

clean:
	@echo "🧹 Czyszczenie plików tymczasowych..."
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# ------------------------------------------------------------------------------
# 5. DEDYKOWANE OPERACJE DANYCH
# ------------------------------------------------------------------------------
isap-sync:
	@echo "🏛️ Wymuszenie synchronizacji projektów z ISAP..."
	uv run python -c "from dags.isap_sync_dag import isap_sync_pipeline; print('Uruchomiono zadanie weryfikacji ISAP.'); isap_sync_pipeline()"

fetch-data:
	@echo "📡 Pobieranie danych ze stron partii oraz kanałów RSS..."
	uv run python -m src.scripts.fetch_parties_and_rss --delay 0.5
