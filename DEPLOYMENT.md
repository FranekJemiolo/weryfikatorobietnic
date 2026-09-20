# Przewodnik Wdrożenia Produkcyjnego: Weryfikator Obietnic

Niniejszy dokument przedstawia kompleksowy przewodnik wdrożenia produkcyjnego platformy **Weryfikator Obietnic** w architekturze chmurowej **Google Cloud Platform (GCP)**.

Architektura oparta jest na nowoczesnych usługach zarządzanych (Serverless / Managed Services), zapewniających wysoką dostępność, odporność na skoki obciążenia (np. w wieczór wyborczy) oraz izolację wrażliwych komponentów.

---

## 1. Docelowa Topologia Systemu (Cloud Architecture)

```mermaid
flowchart TD
    subgraph Internet ["Sieć Publiczna & Obywatele"]
        User["Użytkownik / Przeglądarka (PWA)"]
    end

    subgraph GCP ["Google Cloud Platform (Region: europe-west1)"]
        subgraph Edge ["Cloud CDN & Load Balancer"]
            GLB["Global External HTTPS Load Balancer"]
            CDN["Cloud CDN (Cache dla statyków i ISR)"]
        end

        subgraph Compute ["Środowisko Uruchomieniowe Serverless"]
            CR_Frontend["Cloud Run: Next.js Frontend (SSR & PWA)\n[Autoscaling: 1-20 instancji]"]
            CR_Backend["Cloud Run: FastAPI Backend REST API\n[Autoscaling: 1-15 instancji]"]
        end

        subgraph DataTier ["Baza Danych & Pamięć Wektorowa"]
            CloudSQL[("Cloud SQL for PostgreSQL 16\n+ Rozszerzenie pgvector (HNSW Index)\n[HA: Multi-AZ, SSD]")]
        end

        subgraph Orchestration ["Orkiestracja Danych & AI (ETL)"]
            Composer["Google Cloud Composer 2 (Managed Airflow)\n- DAG: sejm_ingest\n- DAG: party_watchdog\n- DAG: llm_evaluation"]
            GCS["Cloud Storage: Dokumenty PDF & Druki Sejmowe"]
        end

        subgraph ExternalAPIs ["Zewnętrzne Usługi AI i Państwowe"]
            GeminiAPI["Google Gemini 2.5 Flash / Embeddings API"]
            SejmGov["Oficjalne API Sejmu RP (api.sejm.gov.pl)"]
        end
    end

    User --> GLB
    GLB --> CDN
    GLB --> CR_Frontend
    CR_Frontend --> CR_Backend
    CR_Backend --> CloudSQL

    Composer --> CloudSQL
    Composer --> GCS
    Composer --> GeminiAPI
    Composer --> SejmGov
    CR_Backend --> GeminiAPI
```

### Komponenty Infrastruktury:
1. **Google Cloud Run (Frontend - Next.js)**: Bezserwerowe środowisko uruchamiania kontenerów Node.js obsługujące Server-Side Rendering (SSR), Incremental Static Regeneration (ISR) oraz pliki PWA zintegrowane z Cloud CDN.
2. **Google Cloud Run (Backend - FastAPI)**: Asynchroniczny serwis REST API skalujący się od zera do dziesiątek instancji, z ustrukturyzowanym logowaniem JSON trafiającym bezpośrednio do Cloud Logging.
3. **Cloud SQL for PostgreSQL (z rozszerzeniem `pgvector`)**: Zarządzana baza danych w klastrze High Availability z obsługą wektorów cech semantycznych (1536 wymiarów) dla mechanizmu wyszukiwania RAG.
4. **Google Cloud Composer (Managed Apache Airflow)**: Środowisko zarządzane orkiestrujące cykliczne pobieranie danych z Sejmu, analizę załączników PDF (OSR) oraz batchowe wnioskowanie LLM.
5. **Google Cloud Storage (GCS)**: Magazyn obiektowy na pobrane pliki PDF projektów ustaw i załączniki OSR.
6. **Secret Manager**: Bezpieczny skarbiec na klucze API i hasła bazodanowe.

---

## 2. Wymagane Zmienne Środowiskowe (Production .env)

Wszystkie sekrety produkcyjne należy zdefiniować w **Google Secret Manager** i wstrzykiwać do kontenerów jako zmienne środowiskowe.

### A. Backend FastAPI (`src/api/`)
| Zmienna | Typ | Przykładowa Wartość Produkcyjna | Opis |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | String | `postgresql+psycopg://app_user:SEC_PASS@/weryfikator?host=/cloudsql/project:region:instance` | Połączenie do Cloud SQL przez Unix Socket |
| `ENVIRONMENT` | String | `production` | Oznaczenie środowiska |
| `LOG_LEVEL` | String | `INFO` | Minimalny poziom logowania (`INFO`, `WARNING`, `ERROR`) |
| `LOG_FORMAT` | String | `json` | Wymuszenie ustrukturyzowanych logów JSON (`structlog`) |
| `CORS_ORIGINS` | String | `https://weryfikator-obietnic.pl,https://www.weryfikator-obietnic.pl` | Dozwolone domeny CORS dla zapytań z frontendu |
| `GEMINI_API_KEY` | String | `AIzaSy...` | Klucz API do Google GenAI (Gemini) |
| `PORT` | Integer | `8080` | Port nasłuchiwania w Cloud Run (domyślnie `8080`) |

### B. Frontend Next.js (`frontend/`)
| Zmienna | Typ | Przykładowa Wartość Produkcyjna | Opis |
| :--- | :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | String | `https://api.weryfikator-obietnic.pl` | Publiczny adres URL API FastAPI dostępny dla przeglądarek |
| `NODE_ENV` | String | `production` | Tryb produkcyjny Node.js |
| `PORT` | Integer | `3000` | Port kontenera Next.js |

### C. Cloud Composer / Airflow (`dags/`)
| Zmienna | Typ | Przykładowa Wartość Produkcyjna | Opis |
| :--- | :--- | :--- | :--- |
| `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN` | String | *(Zarządzane automatycznie przez Cloud Composer)* | Połączenie metadanych Airflow |
| `DATABASE_URL` | String | `postgresql+psycopg://airflow_user:PASS@10.x.x.x:5432/weryfikator` | Połączenie do bazy danych aplikacji |
| `GEMINI_API_KEY` | String | `AIzaSy...` | Klucz do wsadowej ewaluacji obietnic przez RAG |
| `GCS_BUCKET_NAME` | String | `weryfikator-documents-prod` | Bucket GCS do przechowywania pobranych druków PDF |

---

## 3. Procedura Wdrożenia Krok po Kroku

### Krok 1: Przygotowanie Projektu i Włączenie API w GCP
```bash
# Ustawienie projektu w gcloud
export PROJECT_ID="weryfikator-obietnic-prod"
export REGION="europe-west1"
gcloud config set project $PROJECT_ID

# Włączenie wymaganych usług
gcloud services enable \
    run.googleapis.com \
    sqladmin.googleapis.com \
    composer.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    cloudbuild.googleapis.com
```

### Krok 2: Utworzenie Bazy Cloud SQL z Rozszerzeniem pgvector
```bash
# Utworzenie instancji PostgreSQL 16
gcloud sql instances create weryfikator-db \
    --database-version=POSTGRES_16 \
    --tier=db-custom-2-7680 \
    --region=$REGION \
    --availability-type=REGIONAL \
    --storage-size=50GB \
    --storage-auto-increase \
    --backup-start-time=02:00

# Utworzenie bazy i użytkownika
gcloud sql databases create weryfikator --instance=weryfikator-db
gcloud sql users create app_user --instance=weryfikator-db --password="[BEZPIECZNE_HASLO]"

# Włączenie rozszerzenia pgvector w bazie (przez psql/Cloud Shell)
# gcloud sql connect weryfikator-db --user=postgres
# CREATE EXTENSION IF NOT EXISTS vector;
```

### Krok 3: Budowanie Obrazów i Wdrożenie Backend API (Cloud Run)
```bash
# Utworzenie rejestru Artifact Registry
gcloud artifacts repositories create app-repo \
    --repository-format=docker \
    --location=$REGION

# Zbudowanie i przesłanie obrazu API
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/app-repo/api:1.0.0 .

# Wdrożenie na Cloud Run
gcloud run deploy weryfikator-api \
    --image=$REGION-docker.pkg.dev/$PROJECT_ID/app-repo/api:1.0.0 \
    --region=$REGION \
    --platform=managed \
    --allow-unauthenticated \
    --add-cloudsql-instances=$PROJECT_ID:$REGION:weryfikator-db \
    --set-env-vars="ENVIRONMENT=production,LOG_FORMAT=json,LOG_LEVEL=INFO" \
    --set-secrets="DATABASE_URL=DATABASE_URL_SECRET:latest,GEMINI_API_KEY=GEMINI_API_KEY_SECRET:latest" \
    --min-instances=1 \
    --max-instances=15 \
    --cpu=1 \
    --memory=1Gi
```

### Krok 4: Budowanie i Wdrożenie Frontendu (Cloud Run)
```bash
# Przejście do katalogu frontend
cd frontend

# Zbudowanie kontenera z przekazaniem adresu produkcyjnego API
gcloud builds submit \
    --tag $REGION-docker.pkg.dev/$PROJECT_ID/app-repo/frontend:1.0.0 \
    --substitutions=_NEXT_PUBLIC_API_URL="https://api.weryfikator-obietnic.pl" .

# Wdrożenie na Cloud Run
gcloud run deploy weryfikator-frontend \
    --image=$REGION-docker.pkg.dev/$PROJECT_ID/app-repo/frontend:1.0.0 \
    --region=$REGION \
    --platform=managed \
    --allow-unauthenticated \
    --min-instances=1 \
    --max-instances=20 \
    --cpu=1 \
    --memory=1Gi
```

### Krok 5: Konfiguracja Cloud Composer (Airflow ETL)
1. Utwórz środowisko Cloud Composer 2:
   ```bash
   gcloud composer environments create weryfikator-airflow \
       --location=$REGION \
       --image-version=composer-2.9.0-airflow-2.9.1
   ```
2. Zsynchronizuj katalog `./dags` oraz `./src` z dedykowanym zasobnikiem Cloud Storage środowiska Composer:
   ```bash
   export DAGS_BUCKET=$(gcloud composer environments describe weryfikator-airflow \
       --location=$REGION \
       --format="get(config.nodeConfig.storageConfig.dagsBucket)")

   gsutil -m rsync -r ./dags $DAGS_BUCKET/dags
   gsutil -m rsync -r ./src $DAGS_BUCKET/dags/src
   ```

---

## 4. Monitoring i Utrzymanie (SRE & Observability)

- **Cloud Logging**: Dzięki bibliotece `structlog` wszystkie logi emitowane są w formacie JSON. Zapytania HTTP, błędy RAG oraz metryki wykonania zapytań są w pełni przeszukiwalne w Log Explorerze:
  ```json
  jsonPayload.event = "http_request_completed" AND jsonPayload.status_code >= 400
  ```
- **Uptime Checks**: Skonfiguruj sprawdzanie stanu zdrowia pod adresem `https://api.weryfikator-obietnic.pl/health` z alertem PagerDuty/Slack w przypadku braku odpowiedzi w czasie 5 sekund.
- **Kopie Zapasowe (Backups)**: Cloud SQL wykonuje zautomatyzowane codzienne zrzuty stanu z włączonym Point-in-Time Recovery (PITR) przez 7 dni.
