-- prophet-workspace mail schema. Tables + columns match the exact queries in the Postfix pgsql maps
-- (services/workspace-smtp/postfix/virtual_*.cf) and Dovecot auth-sql (services/workspace-mail/.../auth-sql.conf.ext).
-- Passwords are SHA512-CRYPT (Dovecot default_pass_scheme = SHA512-CRYPT).

CREATE TABLE IF NOT EXISTS mail_domains (
  id      SERIAL PRIMARY KEY,
  domain  VARCHAR(255) UNIQUE NOT NULL,
  active  BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS mail_users (
  id        SERIAL PRIMARY KEY,
  email     VARCHAR(255) UNIQUE NOT NULL,
  password  VARCHAR(255) NOT NULL,          -- {SHA512-CRYPT}$6$...
  active    BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mail_aliases (
  id          SERIAL PRIMARY KEY,
  source      VARCHAR(255) NOT NULL,
  destination VARCHAR(255) NOT NULL,
  active      BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_mail_users_email ON mail_users (email) WHERE active;
CREATE INDEX IF NOT EXISTS idx_mail_domains_domain ON mail_domains (domain) WHERE active;
