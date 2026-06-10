#!/usr/bin/env python3
"""
Validates workspace service configs without requiring Docker.
Checks Dovecot, Postfix, Radicale configs; docker-compose syntax; Kustomize structure.
"""
import configparser
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SERVICES = ROOT / "services"
INFRA_LOCAL = ROOT / "infra" / "local"
INFRA_K8S = ROOT / "infra" / "k8s"

ERRORS: list[str] = []
CHECKS: list[str] = []


def ok(msg: str) -> None:
    CHECKS.append(f"  OK  {msg}")


def fail(msg: str) -> None:
    ERRORS.append(f"  FAIL  {msg}")
    CHECKS.append(f"  FAIL  {msg}")


def require_file(path: Path) -> bool:
    if not path.exists():
        fail(f"missing file: {path.relative_to(ROOT)}")
        return False
    ok(f"exists: {path.relative_to(ROOT)}")
    return True


# ── Dovecot ──────────────────────────────────────────────────────────────────

def check_dovecot() -> None:
    print("\n[dovecot]")
    conf_dir = SERVICES / "workspace-mail" / "dovecot"

    main_conf = conf_dir / "dovecot.conf"
    if not require_file(main_conf):
        return

    content = main_conf.read_text()
    for directive in ("protocols", "mail_location", "auth_mechanisms", "!include"):
        if directive in content:
            ok(f"dovecot.conf has '{directive}'")
        else:
            fail(f"dovecot.conf missing '{directive}'")

    for fname in ("10-auth.conf", "10-mail.conf", "10-master.conf", "auth-sql.conf.ext"):
        require_file(conf_dir / "conf.d" / fname)

    auth_ext = conf_dir / "conf.d" / "auth-sql.conf.ext"
    if auth_ext.exists():
        text = auth_ext.read_text()
        for key in ("driver", "connect", "password_query", "user_query"):
            if key in text:
                ok(f"auth-sql.conf.ext has '{key}'")
            else:
                fail(f"auth-sql.conf.ext missing '{key}'")

    master = conf_dir / "conf.d" / "10-master.conf"
    if master.exists():
        text = master.read_text()
        for service in ("imap-login", "lmtp", "auth"):
            if f"service {service}" in text:
                ok(f"10-master.conf has service '{service}'")
            else:
                fail(f"10-master.conf missing service '{service}'")


# ── Postfix ───────────────────────────────────────────────────────────────────

def check_postfix() -> None:
    print("\n[postfix]")
    postfix_dir = SERVICES / "workspace-smtp" / "postfix"

    main_cf = postfix_dir / "main.cf"
    if not require_file(main_cf):
        return

    content = main_cf.read_text()
    for key in ("virtual_transport", "virtual_mailbox_domains", "smtpd_relay_restrictions",
                "smtpd_sasl_auth_enable", "message_size_limit"):
        if key in content:
            ok(f"main.cf has '{key}'")
        else:
            fail(f"main.cf missing '{key}'")

    # Must not be an open relay
    if "reject_unauth_destination" in content:
        ok("main.cf has reject_unauth_destination (no open relay)")
    else:
        fail("main.cf missing reject_unauth_destination — open relay risk")

    for fname in ("master.cf", "virtual_domains.cf", "virtual_mailbox.cf"):
        require_file(postfix_dir / fname)

    entrypoint = SERVICES / "workspace-smtp" / "entrypoint.sh"
    if require_file(entrypoint):
        text = entrypoint.read_text()
        for var in ("SMTP_HOSTNAME", "DOVECOT_HOST", "POSTGRES_HOST"):
            if var in text:
                ok(f"entrypoint.sh substitutes {var}")
            else:
                fail(f"entrypoint.sh missing substitution for {var}")


# ── Radicale ──────────────────────────────────────────────────────────────────

def check_radicale() -> None:
    print("\n[radicale]")
    config_path = SERVICES / "workspace-caldav" / "radicale" / "config"

    if not require_file(config_path):
        return

    cp = configparser.ConfigParser()
    cp.read(config_path)

    for section in ("server", "auth", "storage", "logging"):
        if cp.has_section(section):
            ok(f"radicale config has [{section}]")
        else:
            fail(f"radicale config missing [{section}]")

    if cp.has_option("server", "hosts"):
        ok(f"radicale [server] hosts = {cp.get('server', 'hosts')}")
    else:
        fail("radicale [server] missing hosts")

    if cp.has_option("storage", "filesystem_folder"):
        ok(f"radicale [storage] filesystem_folder = {cp.get('storage', 'filesystem_folder')}")
    else:
        fail("radicale [storage] missing filesystem_folder")


# ── docker-compose ────────────────────────────────────────────────────────────

def check_compose() -> None:
    print("\n[docker-compose]")
    try:
        import yaml
    except ImportError:
        fail("PyYAML not installed — cannot validate docker-compose (pip install pyyaml)")
        return

    compose_path = INFRA_LOCAL / "docker-compose.workspace.yml"
    if not require_file(compose_path):
        return

    with compose_path.open() as f:
        doc = yaml.safe_load(f)

    services = doc.get("services", {})
    expected = {"postgres", "redis", "minio", "workspace-mail", "workspace-smtp", "workspace-caldav"}
    for svc in expected:
        if svc in services:
            ok(f"compose has service '{svc}'")
        else:
            fail(f"compose missing service '{svc}'")

    volumes = doc.get("volumes", {})
    for v in ("pgdata", "maildata", "caldavdata", "miniodata"):
        if v in volumes:
            ok(f"compose has volume '{v}'")
        else:
            fail(f"compose missing volume '{v}'")

    # workspace-mail must depend on postgres
    mail_deps = services.get("workspace-mail", {}).get("depends_on", [])
    if "postgres" in mail_deps:
        ok("workspace-mail depends_on postgres")
    else:
        fail("workspace-mail missing depends_on: postgres")


# ── Kustomize ─────────────────────────────────────────────────────────────────

def check_kustomize() -> None:
    print("\n[kustomize]")
    try:
        import yaml
    except ImportError:
        fail("PyYAML not installed — cannot validate kustomize")
        return

    for service in ("workspace-mail", "workspace-caldav", "workspace-minio"):
        kust = INFRA_K8S / service / "base" / "kustomization.yaml"
        if not require_file(kust):
            continue

        with kust.open() as f:
            doc = yaml.safe_load(f)

        resources = doc.get("resources", [])
        base_dir = kust.parent
        for r in resources:
            resource_path = base_dir / r
            if resource_path.exists():
                ok(f"{service}/base/{r} exists")
            else:
                fail(f"{service}/base/{r} referenced in kustomization but not found")

        for overlay in ("p0-lab", "p1-single-site"):
            overlay_kust = INFRA_K8S / service / "overlays" / overlay / "kustomization.yaml"
            if overlay_kust.exists():
                ok(f"{service}/overlays/{overlay}/kustomization.yaml exists")
            # p1-single-site not required for all services; just check p0-lab
            elif overlay == "p0-lab":
                fail(f"{service}/overlays/p0-lab/kustomization.yaml missing")


# ── Dockerfiles ───────────────────────────────────────────────────────────────

def check_dockerfiles() -> None:
    print("\n[dockerfiles]")
    for service in ("workspace-mail", "workspace-smtp", "workspace-caldav"):
        df = SERVICES / service / "Dockerfile"
        if not require_file(df):
            continue
        content = df.read_text()
        if "FROM" in content:
            ok(f"{service}/Dockerfile has FROM")
        else:
            fail(f"{service}/Dockerfile missing FROM")
        if "EXPOSE" in content:
            ok(f"{service}/Dockerfile has EXPOSE")
        else:
            fail(f"{service}/Dockerfile missing EXPOSE")


# ── DB migration ──────────────────────────────────────────────────────────────

def check_db_migration() -> None:
    print("\n[db-migration]")
    migration = ROOT / "infra" / "datastores" / "postgres" / "010_workspace_mail.sql"
    if not require_file(migration):
        return
    sql = migration.read_text()
    for table in ("mail_domains", "mail_users"):
        if f"CREATE TABLE IF NOT EXISTS {table}" in sql:
            ok(f"migration creates table '{table}'")
        else:
            fail(f"migration missing CREATE TABLE {table}")


# ── Argo CD AppSet ────────────────────────────────────────────────────────────

def check_argocd() -> None:
    print("\n[argocd-appset]")
    try:
        import yaml
    except ImportError:
        fail("PyYAML not installed")
        return

    appset = ROOT / "infra" / "k8s" / "argo-cd" / "appsets" / "socioprophet-appset.yaml"
    if not require_file(appset):
        return

    with appset.open() as f:
        doc = yaml.safe_load(f)

    elements = (doc.get("spec", {})
                   .get("generators", [{}])[0]
                   .get("list", {})
                   .get("elements", []))
    names = {e["name"] for e in elements}
    for expected in ("workspace-mail", "workspace-caldav", "workspace-minio"):
        if expected in names:
            ok(f"appset has element '{expected}'")
        else:
            fail(f"appset missing element '{expected}'")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=== validate-workspace-services ===")
    check_dockerfiles()
    check_dovecot()
    check_postfix()
    check_radicale()
    check_compose()
    check_kustomize()
    check_db_migration()
    check_argocd()

    print("\n--- summary ---")
    for line in CHECKS:
        print(line)

    if ERRORS:
        print(f"\n{len(ERRORS)} error(s):")
        for e in ERRORS:
            print(f"  {e}")
        sys.exit(1)
    else:
        print(f"\nAll {len(CHECKS)} checks passed.")


if __name__ == "__main__":
    main()
