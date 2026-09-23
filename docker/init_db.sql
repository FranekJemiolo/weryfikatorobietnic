-- ==============================================================================
-- Schema inicjalizacyjny dla projektu: Weryfikator Obietnic
-- Zoptymalizowany pod PostgreSQL 15+ z obsługą typów JSONB oraz indeksów GIN.
-- ==============================================================================

-- Utworzenie bazy dedykowanej dla aplikacji w przypadku uruchamiania poza Docker Compose
CREATE DATABASE IF NOT EXISTS weryfikator_db;
\c weryfikator_db;

-- Włączenie rozszerzeń (UUID i unaccent dla wyszukiwania w języku polskim)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "unaccent";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ------------------------------------------------------------------------------
-- 1. Warstwa Stagingowa (Raw Data Lake)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS raw_sejm_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    endpoint VARCHAR(100) NOT NULL,
    term INT NOT NULL DEFAULT 10,
    external_id VARCHAR(120),
    payload JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_raw_sejm_endpoint_term ON raw_sejm_data(endpoint, term);
CREATE INDEX IF NOT EXISTS idx_raw_sejm_external_id ON raw_sejm_data(external_id);
CREATE INDEX IF NOT EXISTS idx_raw_sejm_payload_gin ON raw_sejm_data USING GIN (payload);

-- ------------------------------------------------------------------------------
-- 2. Podmioty Polityczne i Źródła Informacji
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS political_parties (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    short_name VARCHAR(50) NOT NULL,
    coalition_status VARCHAR(50) NOT NULL, -- np. GOVERNING, OPPOSITION
    official_website VARCHAR(255),
    rss_feed_url VARCHAR(255),
    program_page_url VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Historia zmian stron i feedów partii (DOM Hash Tracking)
CREATE TABLE IF NOT EXISTS party_web_snapshots (
    id SERIAL PRIMARY KEY,
    party_id VARCHAR(50) NOT NULL REFERENCES political_parties(id) ON DELETE CASCADE,
    source_url VARCHAR(500) NOT NULL,
    content_hash VARCHAR(64) NOT NULL, -- SHA-256
    cleaned_markdown TEXT,
    raw_html TEXT,
    is_changed BOOLEAN NOT NULL DEFAULT TRUE,
    revision_number INT NOT NULL DEFAULT 1,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_party_snapshots_hash ON party_web_snapshots(party_id, content_hash);
CREATE INDEX IF NOT EXISTS idx_party_snapshots_changed ON party_web_snapshots(party_id, is_changed);

-- ------------------------------------------------------------------------------
-- 3. Złoty Zbiór Obietnic Wyborczych (Ground Truth)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS electoral_promises (
    promise_id VARCHAR(100) PRIMARY KEY,
    party_id VARCHAR(50) NOT NULL REFERENCES political_parties(id) ON DELETE RESTRICT,
    title VARCHAR(500) NOT NULL,
    raw_text TEXT NOT NULL,
    category VARCHAR(100) NOT NULL, -- np. Gospodarka, Podatki, Zdrowie, Edukacja
    source_document VARCHAR(255) NOT NULL, -- np. '100_konkretow.pdf'
    announced_date DATE,
    quantifiable_metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_promises_party ON electoral_promises(party_id);
CREATE INDEX IF NOT EXISTS idx_promises_category ON electoral_promises(category);

-- ------------------------------------------------------------------------------
-- 4. Procesy Legislacyjne i Druki Sejmowe
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS legislative_processes (
    process_id VARCHAR(100) PRIMARY KEY,
    term INT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    author VARCHAR(255),
    author_type VARCHAR(100), -- np. 'Rada Ministrów', 'Grupa Posłów'
    status VARCHAR(100) NOT NULL,
    change_date TIMESTAMPTZ,
    print_numbers JSONB NOT NULL DEFAULT '[]'::jsonb,
    timeline JSONB NOT NULL DEFAULT '{}'::jsonb,
    time_to_delivery_days INT,
    first_reading_date DATE,
    passed_date DATE,
    signed_date DATE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_processes_status ON legislative_processes(status);
CREATE INDEX IF NOT EXISTS idx_processes_author ON legislative_processes(author_type);
CREATE INDEX IF NOT EXISTS idx_processes_timeline_gin ON legislative_processes USING GIN (timeline);

-- ------------------------------------------------------------------------------
-- 5. Głosowania i Aktywność Posłów (Wielu-do-Wielu)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS parliamentary_votings (
    voting_id VARCHAR(100) PRIMARY KEY,
    process_id VARCHAR(100) REFERENCES legislative_processes(process_id) ON DELETE SET NULL,
    term INT NOT NULL,
    sitting INT NOT NULL,
    voting_number INT NOT NULL,
    date TIMESTAMPTZ NOT NULL,
    title TEXT NOT NULL,
    topic TEXT,
    total_voted INT,
    votes_yes INT,
    votes_no INT,
    votes_abstain INT,
    votes_absent INT,
    mp_votes JSONB NOT NULL DEFAULT '[]'::jsonb -- Zapis JSON dla szybkiego odczytu
);

CREATE INDEX IF NOT EXISTS idx_votings_date ON parliamentary_votings(date);
CREATE INDEX IF NOT EXISTS idx_votings_process ON parliamentary_votings(process_id);
CREATE INDEX IF NOT EXISTS idx_votings_mp_gin ON parliamentary_votings USING GIN (mp_votes);

-- Znormalizowana tabela relacji: voting_id <-> mp_id <-> vote_type
CREATE TABLE IF NOT EXISTS parliamentary_mp_votes (
    voting_id VARCHAR(100) NOT NULL REFERENCES parliamentary_votings(voting_id) ON DELETE CASCADE,
    mp_id INT NOT NULL,
    mp_name VARCHAR(255) NOT NULL,
    club VARCHAR(50),
    vote_type VARCHAR(20) NOT NULL, -- YES, NO, ABSTAIN, ABSENT
    PRIMARY KEY (voting_id, mp_id)
);

CREATE INDEX IF NOT EXISTS idx_mp_votes_lookup ON parliamentary_mp_votes(mp_id, vote_type);
CREATE INDEX IF NOT EXISTS idx_mp_votes_club ON parliamentary_mp_votes(club, vote_type);

-- ------------------------------------------------------------------------------
-- 6. Rejestr Pobranych Dokumentów Binarnych (PDF Storage)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS downloaded_documents (
    id SERIAL PRIMARY KEY,
    document_type VARCHAR(50) NOT NULL, -- 'PRINT', 'OSR', 'JUSTIFICATION', 'RCL'
    term INT NOT NULL,
    associated_id VARCHAR(100) NOT NULL, -- np. numer druku / numer procesu
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    sha256_hash VARCHAR(64) NOT NULL,
    downloaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_docs_associated ON downloaded_documents(term, associated_id);
CREATE INDEX IF NOT EXISTS idx_docs_hash ON downloaded_documents(sha256_hash);

-- ------------------------------------------------------------------------------
-- 7. Wyodrębnione Przepisy Ustawy (Legal AST: Artykuły, Ustępy, Kontekst)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS legislative_provisions (
    id SERIAL PRIMARY KEY,
    process_id VARCHAR(100) NOT NULL REFERENCES legislative_processes(process_id) ON DELETE CASCADE,
    print_number VARCHAR(50),
    section VARCHAR(255),  -- Dział
    chapter VARCHAR(255),  -- Rozdział
    article VARCHAR(50) NOT NULL, -- np. "Art. 5"
    paragraph VARCHAR(50), -- np. "ust. 2"
    point VARCHAR(50),     -- np. "pkt 1"
    provision_text TEXT NOT NULL,
    context_path TEXT NOT NULL, -- np. "Rozdział 2: Podatki > Art. 5 ust. 2"
    embedding_vector JSONB, -- Wektor embeddingu [float, ...]
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_provisions_process ON legislative_provisions(process_id);
CREATE INDEX IF NOT EXISTS idx_provisions_article ON legislative_provisions(process_id, article);

-- ------------------------------------------------------------------------------
-- 8. Ewaluacja LLM i Analiza Zgodności (Fakty i Structured Outputs)
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS legislative_evaluations (
    id SERIAL PRIMARY KEY,
    promise_id VARCHAR(100) NOT NULL REFERENCES electoral_promises(promise_id) ON DELETE RESTRICT,
    process_id VARCHAR(100) NOT NULL REFERENCES legislative_processes(process_id) ON DELETE CASCADE,
    alignment_status VARCHAR(50) NOT NULL, -- W_PELNI, CZESCIOWO, SPRZECZNA, BRAK_POWIAZANIA
    alignment_score INT NOT NULL CHECK (alignment_score BETWEEN 0 AND 100),
    justification TEXT NOT NULL,
    divergence_details TEXT,
    confidence_score FLOAT NOT NULL DEFAULT 1.0 CHECK (confidence_score BETWEEN 0.0 AND 1.0),
    requires_manual_review BOOLEAN NOT NULL DEFAULT FALSE,
    evaluated_provisions JSONB DEFAULT '[]'::jsonb,
    model_name VARCHAR(100) NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_eval_promise ON legislative_evaluations(promise_id);
CREATE INDEX IF NOT EXISTS idx_eval_process ON legislative_evaluations(process_id);
CREATE INDEX IF NOT EXISTS idx_eval_status ON legislative_evaluations(alignment_status);
CREATE INDEX IF NOT EXISTS idx_eval_review ON legislative_evaluations(requires_manual_review);

-- Tabela produkcyjna: core_evaluations (klucz główny: promise_id, project_id)
CREATE TABLE IF NOT EXISTS core_evaluations (
    promise_id VARCHAR(100) NOT NULL,
    project_id VARCHAR(100) NOT NULL,
    alignment_status VARCHAR(50) NOT NULL, -- W_PELNI, CZESCIOWO, SPRZECZNA, BRAK_POWIAZANIA
    justification TEXT NOT NULL,
    divergence_details TEXT,
    confidence_score FLOAT NOT NULL CHECK (confidence_score BETWEEN 0.0 AND 1.0),
    needs_human_review BOOLEAN NOT NULL DEFAULT FALSE,
    evaluated_provisions JSONB DEFAULT '[]'::jsonb,
    model_name VARCHAR(100) NOT NULL DEFAULT 'gemini-1.5-flash',
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (promise_id, project_id)
);

CREATE INDEX IF NOT EXISTS idx_core_eval_review ON core_evaluations(needs_human_review);
CREATE INDEX IF NOT EXISTS idx_core_eval_status ON core_evaluations(alignment_status);

-- ------------------------------------------------------------------------------
-- Dane początkowe (Seed Data)
-- ------------------------------------------------------------------------------
INSERT INTO political_parties (id, name, short_name, coalition_status, official_website, rss_feed_url)
VALUES 
    ('KO', 'Koalicja Obywatelska', 'KO', 'GOVERNING', 'https://platforma.org', 'https://platforma.org/feed'),
    ('TD', 'Trzecia Droga (PSL - Polska 2050)', 'TD', 'GOVERNING', 'https://trzeciadroga.org', NULL),
    ('LEWICA', 'Nowa Lewica', 'Lewica', 'GOVERNING', 'https://klub-lewica.org.pl', NULL),
    ('PIS', 'Prawo i Sprawiedliwość', 'PiS', 'OPPOSITION', 'https://pis.org.pl', NULL),
    ('KONF', 'Konfederacja', 'Konfederacja', 'OPPOSITION', 'https://konfederacja.pl', NULL)
ON CONFLICT (id) DO NOTHING;
