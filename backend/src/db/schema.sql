-- RootMap database schema (PostgreSQL)
--
-- Apply with:  uv run python -m src.db.init_db
-- Safe to re-run: every statement uses IF NOT EXISTS.
-- Mirror of ERD diagram.

-- Core tables

CREATE TABLE IF NOT EXISTS hosts (
    host_id             INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    host_ip             VARCHAR(45)  NOT NULL, -- IPv4 or IPv6
    host_name           VARCHAR(253) NOT NULL,
    collection_interval INTEGER      NOT NULL,   -- Time (s) between collections
    is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
    ssh_port            INTEGER      NOT NULL DEFAULT 22
);

CREATE TABLE IF NOT EXISTS scripts (
    script_id      INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    script_name    VARCHAR(255) NOT NULL,
    script_path    TEXT         NOT NULL,        
    script_version VARCHAR(64)  NOT NULL,        
    script_type    VARCHAR(64)  NOT NULL,        
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS scans (
    scan_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    status    VARCHAR(32) NOT NULL,
    host_id   INTEGER     NOT NULL REFERENCES hosts (host_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS services (
    service_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    service_name VARCHAR(255) NOT NULL,
    service_type VARCHAR(64)  NOT NULL,
    config_path  TEXT,
    service_port INTEGER,
    host_id      INTEGER      NOT NULL REFERENCES hosts (host_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dependencies (
    dependency_id     INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_service_id INTEGER NOT NULL REFERENCES services (service_id) ON DELETE CASCADE,
    target_service_id INTEGER NOT NULL REFERENCES services (service_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dependency_id INTEGER     NOT NULL REFERENCES dependencies (dependency_id) ON DELETE CASCADE,
    scan_id       INTEGER     NOT NULL REFERENCES scans (scan_id) ON DELETE CASCADE,
    source_type   VARCHAR(64) NOT NULL,
    source_path   TEXT,
    raw_data      TEXT,
    collected_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Junction tables

CREATE TABLE IF NOT EXISTS scan_scripts (
    scan_script_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scan_id          INTEGER     NOT NULL REFERENCES scans (scan_id) ON DELETE CASCADE,
    script_id        INTEGER     NOT NULL REFERENCES scripts (script_id),
    execution_status VARCHAR(32) NOT NULL,
    started_at       TIMESTAMPTZ,
    completed_at     TIMESTAMPTZ,
    exit_code        INTEGER
);

-- Token management

CREATE TABLE IF NOT EXISTS host_tokens (
    token_id   INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    host_id    INTEGER     NOT NULL REFERENCES hosts (host_id) ON DELETE CASCADE,
    token_hash TEXT        NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    is_revoked BOOLEAN     NOT NULL DEFAULT FALSE
);

-- User management tables

CREATE TABLE IF NOT EXISTS roles (
    role_name   VARCHAR(64) PRIMARY KEY,
    permissions TEXT        NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username       VARCHAR(64) NOT NULL UNIQUE,
    password_hash  TEXT        NOT NULL,
    role_name      VARCHAR(64) NOT NULL REFERENCES roles (role_name),
    must_change_pw BOOLEAN     NOT NULL DEFAULT TRUE
);

-- Important indexes on FKs. 

CREATE INDEX IF NOT EXISTS idx_scans_host_id             ON scans (host_id);
CREATE INDEX IF NOT EXISTS idx_services_host_id          ON services (host_id);
CREATE INDEX IF NOT EXISTS idx_dependencies_source       ON dependencies (source_service_id);
CREATE INDEX IF NOT EXISTS idx_dependencies_target       ON dependencies (target_service_id);
CREATE INDEX IF NOT EXISTS idx_evidence_dependency_id    ON evidence (dependency_id);
CREATE INDEX IF NOT EXISTS idx_evidence_scan_id          ON evidence (scan_id);
CREATE INDEX IF NOT EXISTS idx_scan_scripts_scan_id      ON scan_scripts (scan_id);
CREATE INDEX IF NOT EXISTS idx_scan_scripts_script_id    ON scan_scripts (script_id);
CREATE INDEX IF NOT EXISTS idx_host_tokens_host_id       ON host_tokens (host_id);
CREATE INDEX IF NOT EXISTS idx_users_role_name           ON users (role_name);
