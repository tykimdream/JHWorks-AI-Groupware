"""Human-run initial credentials for the already approved isolated demo foundation.

No cloud resource creation, IAM changes, deployment, migration, rotation or resume.
"""

import argparse
import getpass
import json
import re
import secrets
import shutil
import sys
from pathlib import Path
from typing import Any

from psycopg import Connection, connect, errors, sql

from app.ops.bootstrap_cloud_secrets import database_url, run_command, safe_failure_code

ROLES = ("jhworks_demo_runtime", "jhworks_demo_migrate")
SECRET_NAMES = (
    "jhworks-demo-runtime-database",
    "jhworks-demo-migration-database",
    "jhworks-demo-session-secret",
)


def cloud_preflight(project: str) -> None:
    for name in SECRET_NAMES:
        versions = run_command([
            "gcloud", "secrets", "versions", "list", name, f"--project={project}",
            "--format=json",
        ])
        if json.loads(versions) != []:
            raise RuntimeError("Initial demo setup requires empty secret targets")
        policy = json.loads(run_command([
            "gcloud", "secrets", "get-iam-policy", name, f"--project={project}",
            "--format=json",
        ]))
        expected_accounts = (
            ["jhworks-demo-runtime", "jhworks-demo-migrate"] if name == SECRET_NAMES[2]
            else ["jhworks-demo-runtime" if name == SECRET_NAMES[0] else "jhworks-demo-migrate"]
        )
        bindings = policy.get("bindings", [])
        if (
            len(bindings) != 1
            or bindings[0]["role"] != "roles/secretmanager.secretAccessor"
            or set(bindings[0]["members"]) != {
                f"serviceAccount:{account}@{project}.iam.gserviceaccount.com"
                for account in expected_accounts
            }
            or bindings[0].get("condition", {}).get("expression")
            != "resource.name.endsWith('/versions/1')"
        ):
            raise RuntimeError("Unexpected initial demo secret permissions")


def database_preflight(connection: Connection[Any], *, expected_database: str = "postgres") -> None:
    row = connection.execute(
        "SELECT current_database(), pg_get_userbyid(nspowner), "
        "(SELECT count(*) FROM information_schema.tables WHERE table_schema='groupware_demo') "
        "FROM pg_namespace WHERE nspname='groupware_demo'"
    ).fetchone()
    if row != (expected_database, "jhworks_demo_migrate", 0):
        raise RuntimeError("Expected empty demo schema with its dedicated owner")
    rows = connection.execute(
        "SELECT rolname, rolcanlogin, rolsuper, rolinherit, rolcreaterole, rolcreatedb, "
        "rolreplication, rolbypassrls, has_schema_privilege(rolname,'groupware','USAGE') "
        "FROM pg_roles WHERE rolname IN ('jhworks_demo_runtime','jhworks_demo_migrate') "
        "ORDER BY rolname"
    ).fetchall()
    if len(rows) != 2 or any(any(row[1:]) for row in rows):
        raise RuntimeError("Demo roles must remain NOLOGIN and isolated before initial setup")
    paths = connection.execute(
        "SELECT setconfig FROM pg_db_role_setting "
        "WHERE setdatabase=(SELECT oid FROM pg_database WHERE datname='postgres') "
        "AND setrole IN (SELECT oid FROM pg_roles "
        "WHERE rolname IN ('jhworks_demo_runtime','jhworks_demo_migrate'))"
    ).fetchall()
    if len(paths) != 2 or any(
        row[0] != ["search_path=groupware_demo, extensions"] for row in paths
    ):
        raise RuntimeError("Expected dedicated role search paths")
    privileges = connection.execute(
        "SELECT has_schema_privilege('jhworks_demo_runtime','groupware_demo','USAGE'), "
        "has_schema_privilege('jhworks_demo_runtime','groupware_demo','CREATE'), "
        "pg_has_role('jhworks_demo_runtime','jhworks_demo_migrate','MEMBER'), "
        "has_schema_privilege('anon','groupware_demo','USAGE'), "
        "has_schema_privilege('authenticated','groupware_demo','USAGE')"
    ).fetchone()
    if privileges != (True, False, False, False, False):
        raise RuntimeError("Unexpected demo runtime or anonymous schema privileges")


def verify_credentials(
    project_ref: str, host: str, passwords: tuple[str, str], ca_file: str
) -> None:
    for role, password, port in zip(ROLES, passwords, (6543, 5432), strict=True):
        with connect(
            host=host, port=port, dbname="postgres", user=f"{role}.{project_ref}",
            password=password, sslmode="verify-full", sslrootcert=ca_file,
            connect_timeout=10, prepare_threshold=None,
            application_name="jhworks-demo-credential-check",
        ) as connection:
            row = connection.execute(
                "SELECT current_user, current_schema(), "
                "has_schema_privilege(current_user,'groupware','USAGE')"
            ).fetchone()
            if row != (role, "groupware_demo", False):
                raise RuntimeError("Unexpected authenticated demo database boundary")
            try:
                with connection.transaction():
                    connection.execute("SELECT 1 FROM groupware.employees LIMIT 0")
            except errors.InsufficientPrivilege:
                pass
            else:
                raise RuntimeError("Private employee access was not denied")


def bootstrap(project: str, project_ref: str, host: str, admin_password: str, ca_file: str) -> None:
    # Keep DB changes in one transaction, including activation. If a GCP write
    # fails, roles stay NOLOGIN. Cloud versions cannot roll back: inspect partial
    # state rather than generating new credentials or deleting versions on retry.
    with connect(
        host=host, port=5432, dbname="postgres", user=f"postgres.{project_ref}",
        password=admin_password, sslmode="verify-full", sslrootcert=ca_file,
        connect_timeout=10, prepare_threshold=None,
        application_name="jhworks-demo-initial-credentials",
    ) as connection:
        connection.execute("SET LOCAL lock_timeout='5s'")
        connection.execute("SET LOCAL statement_timeout='15s'")
        connection.execute("SET LOCAL idle_in_transaction_session_timeout='90s'")
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtext('jhworks-demo-initial-credentials'))"
        )
        cloud_preflight(project)  # Recheck after acquiring the initialization lock.
        database_preflight(connection)
        passwords = (secrets.token_urlsafe(48), secrets.token_urlsafe(48))
        session_key = secrets.token_urlsafe(64)
        if any(
            not re.fullmatch(r"[A-Za-z0-9_-]{64,}", value) for value in (*passwords, session_key)
        ) or len(set((*passwords, session_key))) != 3:
            raise RuntimeError("Unexpected generated credential format")
        for role, password in zip(ROLES, passwords, strict=True):
            verifier = connection.pgconn.encrypt_password(
                password.encode(), role.encode(), algorithm=b"scram-sha-256"
            ).decode()
            connection.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                sql.Identifier(role), sql.Literal(verifier)
            ))
        values = (
            database_url(ROLES[0], project_ref, passwords[0], host, 6543),
            database_url(ROLES[1], project_ref, passwords[1], host, 5432),
            session_key,
        )
        for name, value in zip(SECRET_NAMES, values, strict=True):
            print(f"Stage: store_version_1/{name}", flush=True)
            created = run_command([
                "gcloud", "secrets", "versions", "add", name, f"--project={project}",
                "--data-file=-", "--format=value(name)",
            ], payload=value.encode()).decode().strip()
            if not created.endswith("/versions/1"):
                raise RuntimeError("Unexpected initial secret version; inspect partial state")
        for name in SECRET_NAMES:
            state = run_command([
                "gcloud", "secrets", "versions", "describe", "1", f"--secret={name}",
                f"--project={project}", "--format=value(state)",
            ]).decode().strip()
            if state != "ENABLED":
                raise RuntimeError("Initial secret version is not enabled")
        print("Stage: activate_demo_roles", flush=True)
        for role in ROLES:
            connection.execute(sql.SQL("ALTER ROLE {} LOGIN").format(sql.Identifier(role)))
    print("Stage: verify_authenticated_pooler_connections", flush=True)
    verify_credentials(project_ref, host, passwords, ca_file)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--project-ref", required=True)
    parser.add_argument("--pooler-host", required=True)
    parser.add_argument("--ca-file", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", required=True)
    args = parser.parse_args()
    if (
        not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", args.project)
        or not re.fullmatch(r"[a-z]{20}", args.project_ref)
        or not re.fullmatch(r"aws-[0-9]+-ap-northeast-2\.pooler\.supabase\.com", args.pooler_host)
    ):
        parser.error("Expected the approved project and official Seoul pooler identifiers")
    stage = "preflight"
    try:
        if not sys.stdin.isatty() or not sys.stderr.isatty():
            raise RuntimeError("Interactive terminal required; never echo a credential fallback")
        if not shutil.which("gcloud") or not args.ca_file.is_file():
            raise RuntimeError("gcloud and the verified Supabase CA file are required")
        cloud_preflight(args.project)
        print("Preflight passed. No SETUP confirmation text is required.", flush=True)
        stage = "administrator_password"
        password = getpass.getpass("Existing Supabase postgres password (hidden): ")
        if not password:
            raise ValueError("Empty credential")
        stage = "initial_credentials"
        bootstrap(args.project, args.project_ref, args.pooler_host, password, str(args.ca_file))
    except (Exception, KeyboardInterrupt) as exc:
        print(json.dumps({
            "status": "failed", "stage": stage, "errorType": type(exc).__name__,
            "errorCode": safe_failure_code(exc), "retry": "inspect_partial_state_first",
        }))
        return 1
    print(json.dumps({"status": "passed", "secretVersionsCreated": 3, "authenticatedRoles": 2}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
