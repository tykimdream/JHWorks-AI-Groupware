from urllib.parse import urlsplit

from starlette.requests import Request

from app.core.config import Settings

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _origin(value: str, *, allow_path: bool) -> tuple[str, str, int] | None:
    # Reject ambiguous headers before URL parsing can normalize control characters.
    if not value or any(character.isspace() for character in value) or "," in value:
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or (not allow_path and (parsed.path not in {"", "/"} or "?" in value or "#" in value))
        ):
            return None
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
        return parsed.scheme, parsed.hostname, port
    except ValueError:
        return None


def has_trusted_write_origin(request: Request, settings: Settings) -> bool:
    if request.method in SAFE_METHODS:
        return True

    # A present but invalid Origin must never fall back to a valid Referer.
    origins = request.headers.getlist("origin")
    referers = request.headers.getlist("referer")
    if origins:
        if len(origins) != 1:
            return False
        source = _origin(origins[0], allow_path=False)
    elif referers:
        if len(referers) != 1:
            return False
        source = _origin(referers[0], allow_path=True)
    else:
        # Preserve local CLI/test calls; public deployments fail closed.
        return settings.environment.lower() not in {"production", "prod"}

    trusted = _origin(settings.frontend_origin, allow_path=False)
    return source is not None and trusted is not None and source == trusted
