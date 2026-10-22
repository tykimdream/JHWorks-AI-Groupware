"""Offline preflight for the static domain holding page; never calls a cloud API."""

import argparse
import json
from pathlib import Path
from typing import Any

PROJECT = "jhworks-staging-tykimdream"
FILES = {"index.html", "styles.css"}
HEADERS = {
    "Cache-Control": "private, no-store",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'self'; base-uri 'none'; "
        "frame-ancestors 'none'; form-action 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def deployment_plan(config_file: Path) -> dict[str, Any]:
    """Reject dynamic routing, extra upload files and weakened security headers."""
    config = json.loads(config_file.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or set(config) != {"hosting"}:
        raise ValueError("Only static Hosting configuration is permitted")
    hosting = config["hosting"]
    if not isinstance(hosting, dict) or set(hosting) != {"site", "public", "ignore", "headers"}:
        raise ValueError("Unexpected Hosting options; dynamic routing is not approved")
    if hosting["site"] != PROJECT or hosting["public"] != "public":
        raise ValueError("Unexpected site or public directory")
    if hosting["ignore"] != ["firebase.json", "**/.*", "**/node_modules/**"]:
        raise ValueError("Unexpected ignore rules")
    expected_headers = [{"source": "**", "headers": [
        {"key": key, "value": value} for key, value in HEADERS.items()
    ]}]
    if hosting["headers"] != expected_headers:
        raise ValueError("Security headers differ from the reviewed static policy")
    project_config = json.loads(
        (config_file.parent / ".firebaserc").read_text(encoding="utf-8")
    )
    if project_config != {"projects": {"default": PROJECT}}:
        raise ValueError("Project binding differs from the reviewed project")
    public = config_file.parent / "public"
    if public.is_symlink() or not public.is_dir():
        raise ValueError("Public directory must be a regular directory")
    entries = list(public.iterdir())
    if {entry.name for entry in entries} != FILES:
        raise ValueError("Only the reviewed static files may be uploaded")
    if any(entry.is_symlink() or not entry.is_file() for entry in entries):
        raise ValueError("Symlinks and directories are not permitted")
    upload_bytes = sum(entry.stat().st_size for entry in entries)
    if upload_bytes > 32 * 1024:
        raise ValueError("Static upload exceeds the 32 KiB holding-page limit")
    return {
        "status": "passed", "mode": "static-holding-plan", "project": PROJECT,
        "site": hosting["site"], "targetDomain": "groupware.pikan.dev",
        "files": sorted(FILES), "uploadBytes": upload_bytes, "backendRewrites": 0,
        "cloudRunIamChanges": 0, "aiCalls": 0, "applied": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(deployment_plan(args.config), sort_keys=True))


if __name__ == "__main__":
    main()
