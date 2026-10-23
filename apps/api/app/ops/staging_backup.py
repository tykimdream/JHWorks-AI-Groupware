"""Read-only staging dump and isolated, socket-only Docker restore rehearsal.

Not a scheduled backup service. Dumps stay in the operator's private directory.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

import psycopg
from psycopg import sql

PROJECT = "jhworks-staging-tykimdream"
POOLER = "aws-0-ap-northeast-2.pooler.supabase.com"
DATABASE_USER = "jhworks_migrate.uztfgtfvxhpmavybldbh"
CA_SHA256 = "700723581420dd1ac98fd7e9ac529f0ef210eadcaf87fc868a3ad7d114c2f3b7"
ROW_LIMIT = 10_000


class BackupProfile(StrEnum):
    STAGING = "staging"
    DEMO = "demo"

    @property
    def schema(self) -> str:
        return "groupware_demo" if self == self.DEMO else "groupware"

    @property
    def migration_role(self) -> str:
        return "jhworks_demo_migrate" if self == self.DEMO else "jhworks_migrate"

    @property
    def runtime_role(self) -> str:
        return "jhworks_demo_runtime" if self == self.DEMO else "jhworks_runtime"

    @property
    def database_user(self) -> str:
        return self.migration_role + ".uztfgtfvxhpmavybldbh"

    @property
    def database_secret(self) -> str:
        if self == self.DEMO:
            return "jhworks-demo-migration-database"
        return "jhworks-migration-database"

    @property
    def search_path(self) -> str:
        return "groupware_demo,extensions" if self == self.DEMO else "groupware,extensions,public"


def connection_parameters(
    database_url: str, ca_file: Path, *, profile: BackupProfile = BackupProfile.STAGING,
) -> dict[str, Any]:
    parsed = urlsplit(database_url)
    query = parse_qs(parsed.query)
    if (
        parsed.scheme != "postgresql+psycopg"
        or parsed.hostname != POOLER
        or parsed.port != 5432
        or unquote(parsed.username or "") != profile.database_user
        or parsed.path != "/postgres"
        or not parsed.password
        or query.get("sslmode") != ["verify-full"]
        or parsed.fragment
    ):
        raise ValueError("only the approved migration session pooler is allowed")
    # Git on Windows may checkout the same public PEM certificate with CRLF.
    if hashlib.sha256(ca_file.read_bytes().replace(b"\r\n", b"\n")).hexdigest() != CA_SHA256:
        raise ValueError("Supabase CA checksum mismatch")
    return {
        "host": POOLER,
        "port": 5432,
        "dbname": "postgres",
        "user": profile.database_user,
        "password": unquote(parsed.password),
        "sslmode": "verify-full",
        "sslrootcert": str(ca_file),
        "connect_timeout": 15,
    }


def rows_fingerprint(rows: list[str]) -> str:
    digest = hashlib.sha256()
    for row in sorted(rows):
        # Length framing avoids ambiguity between different row boundaries.
        encoded = row.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
    if not kwargs.get("capture_output"):
        kwargs.setdefault("stderr", subprocess.PIPE)
    return subprocess.run(command, check=True, timeout=300, **kwargs)


CATALOG_QUERIES = {
    "columns": """SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY t.table_name,t.position),'[]')
      FROM (SELECT c.relname table_name,a.attnum position,a.attname column_name,
       format_type(a.atttypid,a.atttypmod) data_type,a.attnotnull not_null,
       pg_get_expr(d.adbin,d.adrelid) default_value FROM pg_attribute a
       JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
       LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
       WHERE n.nspname='groupware' AND c.relkind IN ('r','p')
       AND a.attnum>0 AND NOT a.attisdropped) t""",
    "constraints": """SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY t.table_name,t.name),'[]')
      FROM (SELECT c.relname table_name,k.conname name,pg_get_constraintdef(k.oid,true) definition
       FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid
       JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='groupware') t""",
    "indexes": """SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY t.tablename,t.indexname),'[]')
      FROM (SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='groupware') t""",
    "ownership_acl": """SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY t.name),'[]') FROM
      (SELECT c.relname name,c.relkind kind,pg_get_userbyid(c.relowner) owner,
       c.relacl::text acl FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
       WHERE n.nspname='groupware' AND c.relkind IN ('r','p','S','v','m')) t""",
    "schema_acl": """SELECT jsonb_build_object('owner',pg_get_userbyid(nspowner),
      'acl',nspacl::text) FROM pg_namespace WHERE nspname='groupware'""",
    "default_acl": """SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY t.owner,t.kind),'[]') FROM
      (SELECT pg_get_userbyid(d.defaclrole) owner,d.defaclobjtype kind,d.defaclacl::text acl
       FROM pg_default_acl d JOIN pg_namespace n ON n.oid=d.defaclnamespace
       WHERE n.nspname='groupware') t""",
}


def catalog_queries(profile: BackupProfile) -> dict[str, str]:
    # Only two fixed profiles can select a namespace; no arbitrary schema/Secret
    # CLI argument is accepted. Keep legacy staging query strings unchanged.
    literal = sql.Literal(profile.schema).as_string()
    return {name: statement.replace("'groupware'", literal)
            for name, statement in CATALOG_QUERIES.items()}


def snapshot(
    query: Callable[[str], Any], *, profile: BackupProfile = BackupProfile.STAGING,
) -> dict[str, Any]:
    literal = sql.Literal(profile.schema).as_string()
    names = query("SELECT coalesce(jsonb_agg(tablename ORDER BY tablename),'[]') "
                  "FROM pg_tables WHERE schemaname=" + literal)
    if not names or "alembic_version" not in names:
        raise ValueError("expected an initialized backup target schema")
    result = {name: query(statement) for name, statement in catalog_queries(profile).items()}
    tables = {}
    for name in names:
        identifier = sql.Identifier(profile.schema, name).as_string()
        count = query(
            "SELECT to_jsonb(count(*)) FROM "
            f"(SELECT 1 FROM {identifier} LIMIT {ROW_LIMIT + 1}) bounded_rows"
        )
        if count > ROW_LIMIT:
            raise ValueError("rehearsal row limit exceeded; review resources before larger dumps")
        rows = query(
            f"SELECT coalesce(jsonb_agg(row_data),'[]') FROM "
            f"(SELECT to_jsonb(t)::text row_data FROM {identifier} t) rows"
        )
        tables[name] = {"count": count, "sha256": rows_fingerprint(rows)}
    result["tables"] = tables
    result["head"] = query("SELECT to_jsonb(version_num) FROM "
                           + sql.Identifier(profile.schema, "alembic_version").as_string())
    sequences = query("SELECT coalesce(jsonb_agg(sequencename ORDER BY sequencename),'[]') "
                      "FROM pg_sequences WHERE schemaname=" + literal)
    result["sequences"] = {
        name: query(
            "SELECT jsonb_build_object('last_value',last_value,'is_called',is_called) FROM "
            + sql.Identifier(profile.schema, name).as_string()
        )
        for name in sequences
    }
    return result


def rehearse(
    image: str, ca_file: Path, output_root: Path, *, profile: BackupProfile = BackupProfile.STAGING,
) -> dict[str, Any]:
    if not isinstance(profile, BackupProfile):
        raise ValueError("use one of the fixed backup profiles")
    if not re.fullmatch(r"pgvector/pgvector@sha256:[a-f0-9]{64}", image):
        raise ValueError("use a verified pgvector image digest")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    directory = output_root / stamp
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    archive = directory / (profile.schema + ".dump")
    container = "jhworks-restore-" + uuid4().hex
    created = False
    stage = "preflight"
    report: dict[str, Any] = {
        "generatedAt": stamp, "status": "preparing", "image": image,
        "profile": profile.value, "schema": profile.schema,
    }
    try:
        project = run(
            ["gcloud", "projects", "describe", PROJECT, "--format=value(projectNumber)"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        if project != "968398406137":
            raise ValueError("unexpected project")
        url = run(
            ["gcloud", "secrets", "versions", "access", "1", "--secret",
             profile.database_secret, "--project", PROJECT],
            capture_output=True,
            text=True,
        ).stdout.strip()
        parameters = connection_parameters(url, ca_file, profile=profile)
        queries = catalog_queries(profile)
        stage = "dump"
        started = time.monotonic()
        with psycopg.connect(**parameters) as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            connection.execute("SET LOCAL search_path TO " + profile.search_path)
            identity = connection.execute("SELECT current_user,current_schema()").fetchone()
            if identity != (profile.migration_role, profile.schema):
                raise ValueError("unexpected authenticated backup identity or schema")
            if profile == BackupProfile.DEMO and connection.execute(
                "SELECT has_schema_privilege(current_user,'groupware','USAGE')"
            ).fetchone() != (False,):
                raise ValueError("demo backup must not access the private schema")

            def source_query(statement: str) -> Any:
                report["sourceQuery"] = next(
                    (name for name, query in queries.items() if query == statement),
                    "snapshot-or-table-data",
                )
                report["sourceQueryIndex"] = report.get("sourceQueryIndex", 0) + 1
                row = connection.execute(statement).fetchone()
                if row is None:
                    raise ValueError("snapshot query returned no result")
                return row[0]

            exported = source_query("SELECT pg_export_snapshot()")
            source = snapshot(source_query, profile=profile)
            environment = {
                **os.environ, "PGHOST": parameters["host"], "PGPORT": "5432",
                "PGDATABASE": "postgres", "PGUSER": parameters["user"],
                "PGPASSWORD": parameters["password"], "PGSSLMODE": "verify-full",
                "PGSSLROOTCERT": "/certs/supabase.crt", "PGCONNECT_TIMEOUT": "15",
            }
            env_names = ["PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD",
                         "PGSSLMODE", "PGSSLROOTCERT", "PGCONNECT_TIMEOUT"]
            with archive.open("xb") as destination:
                archive.chmod(0o600)
                run(
                    ["docker", "run", "--rm", "--network=host", "--mount",
                     f"type=bind,src={ca_file.resolve()},dst=/certs/supabase.crt,readonly",
                     *[item for name in env_names for item in ("--env", name)],
                     image, "pg_dump", "--format=custom", "--schema=" + profile.schema,
                     "--strict-names", "--no-password", "--lock-wait-timeout=10s",
                     f"--snapshot={exported}"], env=environment, stdout=destination,
                )
        report["dumpSeconds"] = round(time.monotonic() - started, 2)
        report["dumpBytes"] = archive.stat().st_size
        report["dumpSha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
        stage = "isolated_restore"
        started = time.monotonic()
        run(
            ["docker", "run", "--detach", "--rm", "--name", container,
             "--label", "jhworks.task=restore-rehearsal", "--network=none",
             "--memory=512m", "--cpus=1", "--user=postgres", "--entrypoint=sh", image,
             "-c", "initdb -D /tmp/jhworks-pg --auth-local=peer --auth-host=reject "
             "--encoding=UTF8 --no-locale >/tmp/initdb.log && "
             "exec postgres -D /tmp/jhworks-pg -c listen_addresses='' "
             "-c unix_socket_directories=/tmp"], capture_output=True,
        )
        created = True
        psql = ["docker", "exec", "--user=postgres", "-i", container,
                "psql", "-XAtq", "--set=ON_ERROR_STOP=1", "-h", "/tmp", "-U", "postgres"]
        for attempt in range(30):
            try:
                run([*psql, "-c", "SELECT 1"], capture_output=True)
                break
            except subprocess.CalledProcessError:
                if attempt == 29:
                    raise
                time.sleep(1)
        run([*psql, "-c", f"CREATE ROLE {profile.migration_role} NOLOGIN NOINHERIT; "
             f"CREATE ROLE {profile.runtime_role} NOLOGIN NOINHERIT; "
             "CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN; "
             "CREATE SCHEMA extensions; CREATE EXTENSION vector WITH SCHEMA extensions;"],
            capture_output=True)
        with archive.open("rb") as source_file:
            run(["docker", "exec", "--user=postgres", "-i", container, "pg_restore",
                 "--exit-on-error", "--single-transaction", "-h", "/tmp", "-U", "postgres",
                 "--dbname=postgres"], stdin=source_file, stdout=subprocess.PIPE)
        restored = snapshot(lambda q: json.loads(run(
            [*psql, "-c", "SET search_path TO " + profile.search_path + "; " + q],
            capture_output=True, text=True,
        ).stdout), profile=profile)
        if source != restored:
            raise ValueError("restored schema/data/ACL fingerprint differs")
        report.update(
            status="passed", restoreSeconds=round(time.monotonic() - started, 2),
            head=source["head"], tables=source["tables"],
            verified=[*queries, "rows", "sequences", "head"],
            backupReference=f"cloud-shell:{stamp}:sha256:{report['dumpSha256']}:restore-verified",
        )
    except Exception as error:
        # No connection strings, passwords, SQL rows, command stderr, or tracebacks.
        report.update(status="failed", stage=stage, errorType=type(error).__name__)
        if isinstance(error, psycopg.Error):
            report["sqlstate"] = error.sqlstate
    finally:
        if created:
            try:
                run(["docker", "stop", container], capture_output=True)
                report["temporaryContainerRemoved"] = True
            except subprocess.SubprocessError:
                report.update(status="failed", temporaryContainerRemoved=False)
        (directory / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
        (directory / "verification.json").chmod(0o600)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--ca-file", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--profile", type=BackupProfile, choices=list(BackupProfile),
                        default=BackupProfile.STAGING)
    args = parser.parse_args()
    report = rehearse(args.image, args.ca_file, args.output_root, profile=args.profile)
    print(json.dumps(report))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
