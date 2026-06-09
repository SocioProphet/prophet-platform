-- Prophet Workspace: mail domains and virtual users
CREATE TABLE IF NOT EXISTS mail_domains (
    domain       TEXT PRIMARY KEY,
    active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mail_users (
    email        TEXT PRIMARY KEY,
    domain       TEXT NOT NULL REFERENCES mail_domains(domain),
    password     TEXT NOT NULL,  -- SHA512-CRYPT hash
    quota_bytes  BIGINT NOT NULL DEFAULT 5368709120,  -- 5 GB
    active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS mail_users_domain_idx ON mail_users(domain);
