"""User-run, one-time credential setup for an empty private staging environment.

Uses the existing psycopg dependency and gcloud in Cloud Shell.
Never run this on an existing deployment or use it as a rotation tool.
"""

import argparse
import getpass
import re
import secrets
import shutil
import subprocess
from pathlib import Path
from urllib.parse import quote

from psycopg import Error as DatabaseError
from psycopg import connect as connect
from psycopg import sql

SECRET_NAMES = (
    "jhworks-runtime-database",
    "jhworks-migration-database",
    "jhworks-session-secret",
)
DEPLOYMENT_CA_PATH = "/workspace/certs/supabase-ca-2021.crt"


def safe_failure_code(error: BaseException) -> str:
    """Classify locally; never return provider diagnostics or credential-bearing SQL."""
    if isinstance(error, DatabaseError):
        if error.sqlstate == "28P01":
            return "DB_AUTHENTICATION_FAILED"
        if error.sqlstate == "42501":
            return "DB_ROLE_PERMISSION_DENIED"
        message = str(error).lower()
        if "certificate" in message or "ssl" in message:
            return "DB_TLS_FAILED"
        if "translate host" in message or "name resolution" in message:
            return "DB_DNS_FAILED"
        if "timeout" in message or "timed out" in message:
            return "DB_CONNECTION_TIMEOUT"
        return "DB_CONNECTION_OR_STATEMENT_FAILED"
    if isinstance(error, subprocess.TimeoutExpired):
        return "GCP_COMMAND_TIMEOUT"
    return "PREFLIGHT_OR_GCP_COMMAND_FAILED"


def database_url(role: str, project_ref: str, password: str, host: str, port: int) -> str:
    user = quote(f"{role}.{project_ref}", safe="")
    return (
        f"postgresql+psycopg://{user}:{quote(password, safe='')}@{host}:{port}/postgres"
        f"?sslmode=verify-full&sslrootcert={DEPLOYMENT_CA_PATH}"
    )


def run_command(
    arguments: list[str], *, payload: bytes | None = None, environment: dict[str, str] | None = None
) -> bytes:
    result = subprocess.run(
        arguments, input=payload, env=environment, capture_output=True, check=False, timeout=120
    )
    if result.returncode:
        # psql diagnostics can contain SQL, so never propagate stdout/stderr.
        raise RuntimeError("command failed; diagnostic output suppressed")
    return result.stdout


def ensure_empty_targets(project: str) -> None:
    services = run_command(
        ["gcloud", "run", "services", "list", f"--project={project}", "--format=value(name)"]
    )
    if services.strip():
        raise RuntimeError("initial setup requires a project without Cloud Run services")
    for name in SECRET_NAMES:
        versions = run_command(
            [
                "gcloud",
                "secrets",
                "versions",
                "list",
                name,
                f"--project={project}",
                "--format=value(name)",
            ]
        )
        if versions.strip():
            raise RuntimeError("initial setup requires secrets without existing versions")


def set_role_passwords(
    project_ref: str,
    host: str,
    admin_password: str,
    passwords: dict[str, str],
    ca_file: str = DEPLOYMENT_CA_PATH,
) -> None:
    with connect(
        host=host,
        port=5432,
        dbname="postgres",
        user=f"postgres.{project_ref}",
        password=admin_password,
        sslmode="verify-full",
        sslrootcert=ca_file,
        connect_timeout=10,
        prepare_threshold=None,
        application_name="jhworks-initial-credentials",
    ) as connection:
        for role, password in passwords.items():
            verifier = connection.pgconn.encrypt_password(
                password.encode(), role.encode(), algorithm=b"scram-sha-256"
            ).decode()
            connection.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(verifier)
                )
            )


def bootstrap(
    project: str,
    project_ref: str,
    host: str,
    admin_password: str,
    ca_file: str = DEPLOYMENT_CA_PATH,
) -> None:
    ensure_empty_targets(project)
    runtime_password = secrets.token_urlsafe(48)
    migration_password = secrets.token_urlsafe(48)
    session_secret = secrets.token_urlsafe(64)
    if not all(
        re.fullmatch(r"[A-Za-z0-9_-]+", value)
        for value in (runtime_password, migration_password, session_secret)
    ):
        raise RuntimeError("unexpected generated credential format")
    # libpq hashes locally, keeping cleartext out of ALTER ROLE and server SQL logs.
    print("Stage: database_credentials", flush=True)
    set_role_passwords(
        project_ref,
        host,
        admin_password,
        {"jhworks_runtime": runtime_password, "jhworks_migrate": migration_password},
        ca_file,
    )
    values = (
        database_url("jhworks_runtime", project_ref, runtime_password, host, 6543),
        database_url("jhworks_migrate", project_ref, migration_password, host, 5432),
        session_secret,
    )
    for name, value in zip(SECRET_NAMES, values, strict=True):
        print(f"Stage: secret_version/{name}", flush=True)
        run_command(
            ["gcloud", "secrets", "versions", "add", name, f"--project={project}", "--data-file=-"],
            payload=value.encode(),
        )
        print(f"Created initial version: {name}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--project-ref", required=True)
    parser.add_argument("--pooler-host", required=True)
    parser.add_argument("--ca-file", default=str(Path.home() / "jhworks-supabase-ca.crt"))
    parser.add_argument("--confirm-new-private-staging", action="store_true", required=True)
    args = parser.parse_args()
    if (
        not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", args.project)
        or not re.fullmatch(r"[a-z]{20}", args.project_ref)
        or not re.fullmatch(r"aws-[0-9]+-[a-z0-9-]+\.pooler\.supabase\.com", args.pooler_host)
    ):
        parser.error("invalid dedicated project or pooler identifiers")
    if not shutil.which("gcloud"):
        parser.error("gcloud must be installed")
    if not Path(args.ca_file).is_file():
        parser.error("download the official Supabase CA certificate first; --ca-file is required")
    print("Creates two random DB passwords and a JWT secret, then stores them in GCP.")
    print("Fresh staging only. On failure, inspect partial state before deploying or retrying.")
    try:
        print("Stage: preflight", flush=True)
        ensure_empty_targets(args.project)
    except (RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        print(f"Setup failed: {safe_failure_code(error)}. No password requested.")
        return 1
    if input("Type SETUP to continue: ").strip() != "SETUP":
        return 1
    admin_password = getpass.getpass("Supabase postgres password (hidden): ")
    if not admin_password:
        return 1
    try:
        bootstrap(args.project, args.project_ref, args.pooler_host, admin_password, args.ca_file)
    except (RuntimeError, OSError, subprocess.TimeoutExpired, DatabaseError) as error:
        print(f"Setup failed: {safe_failure_code(error)}. Check partial state before retrying.")
        return 1
    print("Credential setup complete. No application was deployed; no credential values printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
