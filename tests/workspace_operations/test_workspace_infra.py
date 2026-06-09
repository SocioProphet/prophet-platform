"""
pytest suite for workspace infrastructure.
No Docker required — validates config files, manifests, and schema consistency.
"""
import configparser
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent.parent
SERVICES = ROOT / "services"
INFRA_K8S = ROOT / "infra" / "k8s"
INFRA_LOCAL = ROOT / "infra" / "local"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def dovecot_main():
    return (SERVICES / "workspace-mail" / "dovecot" / "dovecot.conf").read_text()

@pytest.fixture
def dovecot_auth_sql():
    return (SERVICES / "workspace-mail" / "dovecot" / "conf.d" / "auth-sql.conf.ext").read_text()

@pytest.fixture
def postfix_main():
    return (SERVICES / "workspace-smtp" / "postfix" / "main.cf").read_text()

@pytest.fixture
def postfix_master():
    return (SERVICES / "workspace-smtp" / "postfix" / "master.cf").read_text()

@pytest.fixture
def radicale_config():
    cp = configparser.ConfigParser()
    cp.read(SERVICES / "workspace-caldav" / "radicale" / "config")
    return cp

@pytest.fixture
def compose_doc():
    with (INFRA_LOCAL / "docker-compose.workspace.yml").open() as f:
        return yaml.safe_load(f)

@pytest.fixture
def appset_doc():
    with (INFRA_K8S / "argo-cd" / "appsets" / "socioprophet-appset.yaml").open() as f:
        return yaml.safe_load(f)


# ── Dovecot tests ─────────────────────────────────────────────────────────────

class TestDovecotConfig:
    def test_main_conf_exists(self):
        assert (SERVICES / "workspace-mail" / "dovecot" / "dovecot.conf").exists()

    def test_protocols_declared(self, dovecot_main):
        assert "protocols = imap lmtp" in dovecot_main

    def test_mail_location_declared(self, dovecot_main):
        assert "mail_location" in dovecot_main

    def test_auth_mechanisms(self, dovecot_main):
        assert "auth_mechanisms" in dovecot_main

    def test_includes_conf_d(self, dovecot_main):
        assert "!include conf.d/*.conf" in dovecot_main

    @pytest.mark.parametrize("fname", [
        "10-auth.conf", "10-mail.conf", "10-master.conf", "auth-sql.conf.ext"
    ])
    def test_conf_d_files_exist(self, fname):
        assert (SERVICES / "workspace-mail" / "dovecot" / "conf.d" / fname).exists()

    def test_auth_sql_driver_pgsql(self, dovecot_auth_sql):
        assert "driver = pgsql" in dovecot_auth_sql

    def test_auth_sql_has_password_query(self, dovecot_auth_sql):
        assert "password_query" in dovecot_auth_sql

    def test_auth_sql_has_user_query(self, dovecot_auth_sql):
        assert "user_query" in dovecot_auth_sql

    def test_auth_sql_references_env_vars(self, dovecot_auth_sql):
        for var in ("POSTGRES_HOST", "POSTGRES_USER", "POSTGRES_PASSWORD"):
            assert var in dovecot_auth_sql, f"missing env var {var} in auth-sql.conf.ext"

    def test_master_conf_services(self):
        text = (SERVICES / "workspace-mail" / "dovecot" / "conf.d" / "10-master.conf").read_text()
        for svc in ("imap-login", "lmtp", "auth"):
            assert f"service {svc}" in text, f"missing 'service {svc}' in 10-master.conf"

    def test_lmtp_port_24(self):
        text = (SERVICES / "workspace-mail" / "dovecot" / "conf.d" / "10-master.conf").read_text()
        assert "port = 24" in text


# ── Postfix tests ─────────────────────────────────────────────────────────────

class TestPostfixConfig:
    def test_main_cf_exists(self):
        assert (SERVICES / "workspace-smtp" / "postfix" / "main.cf").exists()

    def test_virtual_transport_to_dovecot(self, postfix_main):
        assert "virtual_transport = lmtp:" in postfix_main

    def test_no_open_relay(self, postfix_main):
        assert "reject_unauth_destination" in postfix_main, \
            "main.cf must include reject_unauth_destination to prevent open relay"

    def test_virtual_mailbox_domains_pgsql(self, postfix_main):
        assert "pgsql:" in postfix_main

    def test_submission_port_in_master(self, postfix_master):
        assert "submission" in postfix_master

    def test_sasl_auth_enabled(self, postfix_main):
        assert "smtpd_sasl_auth_enable = yes" in postfix_main

    def test_message_size_limit(self, postfix_main):
        assert "message_size_limit" in postfix_main

    def test_entrypoint_substitutes_env_vars(self):
        text = (SERVICES / "workspace-smtp" / "entrypoint.sh").read_text()
        for var in ("SMTP_HOSTNAME", "DOVECOT_HOST", "POSTGRES_HOST",
                    "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
            assert var in text, f"entrypoint.sh does not substitute {var}"

    @pytest.mark.parametrize("fname", ["virtual_domains.cf", "virtual_mailbox.cf"])
    def test_pgsql_map_files_exist(self, fname):
        assert (SERVICES / "workspace-smtp" / "postfix" / fname).exists()


# ── Radicale tests ────────────────────────────────────────────────────────────

class TestRadicaleConfig:
    def test_config_exists(self):
        assert (SERVICES / "workspace-caldav" / "radicale" / "config").exists()

    @pytest.mark.parametrize("section", ["server", "auth", "storage", "logging"])
    def test_required_sections(self, radicale_config, section):
        assert radicale_config.has_section(section), f"radicale config missing [{section}]"

    def test_listens_on_5232(self, radicale_config):
        hosts = radicale_config.get("server", "hosts")
        assert "5232" in hosts

    def test_storage_filesystem(self, radicale_config):
        fs = radicale_config.get("storage", "filesystem_folder")
        assert "/var/lib/radicale" in fs

    def test_auth_htpasswd(self, radicale_config):
        auth_type = radicale_config.get("auth", "type")
        assert auth_type == "htpasswd"


# ── docker-compose tests ───────────────────────────────────────────────────────

class TestDockerCompose:
    def test_compose_file_exists(self):
        assert (INFRA_LOCAL / "docker-compose.workspace.yml").exists()

    @pytest.mark.parametrize("svc", [
        "postgres", "redis", "minio", "workspace-mail", "workspace-smtp", "workspace-caldav"
    ])
    def test_required_services_present(self, compose_doc, svc):
        assert svc in compose_doc["services"], f"compose missing service '{svc}'"

    def test_workspace_mail_depends_on_postgres(self, compose_doc):
        deps = compose_doc["services"]["workspace-mail"].get("depends_on", [])
        assert "postgres" in deps

    def test_workspace_smtp_depends_on_dovecot(self, compose_doc):
        deps = compose_doc["services"]["workspace-smtp"].get("depends_on", [])
        assert "workspace-mail" in deps

    @pytest.mark.parametrize("vol", ["pgdata", "maildata", "caldavdata", "miniodata"])
    def test_required_volumes(self, compose_doc, vol):
        assert vol in compose_doc["volumes"], f"compose missing volume '{vol}'"

    def test_imap_port_exposed(self, compose_doc):
        ports = compose_doc["services"]["workspace-mail"].get("ports", [])
        assert any("143" in str(p) for p in ports), "IMAP port 143 not exposed"

    def test_minio_s3_port_exposed(self, compose_doc):
        ports = compose_doc["services"]["minio"].get("ports", [])
        assert any("9000" in str(p) for p in ports)


# ── Kustomize tests ───────────────────────────────────────────────────────────

class TestKustomize:
    @pytest.mark.parametrize("service", [
        "workspace-mail", "workspace-caldav", "workspace-minio"
    ])
    def test_base_kustomization_exists(self, service):
        kust = INFRA_K8S / service / "base" / "kustomization.yaml"
        assert kust.exists(), f"{service}/base/kustomization.yaml missing"

    @pytest.mark.parametrize("service", [
        "workspace-mail", "workspace-caldav", "workspace-minio"
    ])
    def test_p0_lab_overlay_exists(self, service):
        kust = INFRA_K8S / service / "overlays" / "p0-lab" / "kustomization.yaml"
        assert kust.exists(), f"{service}/overlays/p0-lab/kustomization.yaml missing"

    @pytest.mark.parametrize("service", [
        "workspace-mail", "workspace-caldav", "workspace-minio"
    ])
    def test_base_resources_exist(self, service):
        kust_path = INFRA_K8S / service / "base" / "kustomization.yaml"
        with kust_path.open() as f:
            doc = yaml.safe_load(f)
        base_dir = kust_path.parent
        for resource in doc.get("resources", []):
            assert (base_dir / resource).exists(), \
                f"{service}/base/{resource} listed in kustomization but file missing"

    def test_mail_namespace_socioprophet(self):
        kust = INFRA_K8S / "workspace-mail" / "base" / "kustomization.yaml"
        with kust.open() as f:
            doc = yaml.safe_load(f)
        assert doc.get("namespace") == "socioprophet"


# ── DB migration tests ────────────────────────────────────────────────────────

class TestDBMigration:
    def test_migration_file_exists(self):
        assert (ROOT / "infra" / "datastores" / "postgres" / "010_workspace_mail.sql").exists()

    def test_creates_mail_domains(self):
        sql = (ROOT / "infra" / "datastores" / "postgres" / "010_workspace_mail.sql").read_text()
        assert "CREATE TABLE IF NOT EXISTS mail_domains" in sql

    def test_creates_mail_users(self):
        sql = (ROOT / "infra" / "datastores" / "postgres" / "010_workspace_mail.sql").read_text()
        assert "CREATE TABLE IF NOT EXISTS mail_users" in sql

    def test_mail_users_references_domains(self):
        sql = (ROOT / "infra" / "datastores" / "postgres" / "010_workspace_mail.sql").read_text()
        assert "REFERENCES mail_domains" in sql

    def test_migration_uses_if_not_exists(self):
        sql = (ROOT / "infra" / "datastores" / "postgres" / "010_workspace_mail.sql").read_text()
        assert sql.count("IF NOT EXISTS") >= 2, "migration must be idempotent (IF NOT EXISTS)"


# ── Argo CD AppSet tests ──────────────────────────────────────────────────────

class TestArgoAppSet:
    def test_workspace_bundles_registered(self, appset_doc):
        elements = (appset_doc["spec"]["generators"][0]["list"]["elements"])
        names = {e["name"] for e in elements}
        for expected in ("workspace-mail", "workspace-caldav", "workspace-minio"):
            assert expected in names, f"Argo appset missing element '{expected}'"

    def test_workspace_mail_path(self, appset_doc):
        elements = appset_doc["spec"]["generators"][0]["list"]["elements"]
        mail = next(e for e in elements if e["name"] == "workspace-mail")
        assert "workspace-mail" in mail["path"]
        assert "overlays" in mail["path"]
