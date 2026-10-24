import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.api.documentation import API_DESCRIPTION, TAGS
from app.api.router import api_router
from app.core.config import get_settings
from app.core.csrf import has_trusted_write_origin
from app.core.errors import AppError, RateLimitError
from app.core.logging import configure_logging, reset_request_id, set_request_id

settings = get_settings()
configure_logging(settings.log_format, settings.log_level)
logger = logging.getLogger("jhworks.api")
PRIVATE_API_CACHE_CONTROL = "private, no-store"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=API_DESCRIPTION,
    openapi_tags=TAGS,
    docs_url=None,
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
    swagger_ui_parameters={
        "docExpansion": "none",
        "filter": True,
        "displayRequestDuration": True,
        "persistAuthorization": False,
        **({"supportedSubmitMethods": []} if settings.public_demo_enabled else {}),
    },
)


@app.get("/api/v1/docs", include_in_schema=False)
def api_documentation() -> HTMLResponse:
    response = get_swagger_ui_html(
        openapi_url="/api/v1/openapi.json",
        title=f"{settings.app_name} - Swagger UI",
        swagger_ui_parameters=app.swagger_ui_parameters,
    )
    # Swagger's long domain tags otherwise squeeze mobile descriptions into one character columns.
    style = """<style>
    @media (max-width: 640px) {
      .swagger-ui .opblock-tag { display: block; position: relative; padding-right: 44px; }
      .swagger-ui .opblock-tag > a { display: block; overflow-wrap: anywhere; }
      .swagger-ui .opblock-tag small { display: block; padding: 8px 0; }
      .swagger-ui .opblock-tag .expand-operation { position: absolute; right: 8px; top: 16px; }
    }
    </style>"""
    return HTMLResponse(bytes(response.body).decode().replace("</head>", style + "</head>"))


@app.get("/docs", include_in_schema=False)
def legacy_docs() -> RedirectResponse:
    return RedirectResponse("/api/v1/docs")


@app.get("/openapi.json", include_in_schema=False)
def legacy_openapi() -> RedirectResponse:
    return RedirectResponse("/api/v1/openapi.json")


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = (
        supplied_request_id if REQUEST_ID_PATTERN.fullmatch(supplied_request_id) else str(uuid4())
    )
    request.state.request_id = request_id
    context_token = set_request_id(request_id)
    started_at = perf_counter()
    try:
        if not has_trusted_write_origin(request, settings):
            logger.info(
                "request_rejected",
                extra={
                    "event": "request_rejected",
                    "error_code": "CSRF_ORIGIN_REJECTED",
                    "status_code": 403,
                },
            )
            response = JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "CSRF_ORIGIN_REJECTED",
                        "message": "The request must originate from the trusted frontend.",
                        "details": None,
                    },
                    "requestId": request_id,
                },
            )
        else:
            response = await call_next(request)
        duration_ms = round((perf_counter() - started_at) * 1000, 2)
        # Cookie-authenticated data and errors must not enter shared gateway caches.
        response.headers["Cache-Control"] = PRIVATE_API_CACHE_CONTROL
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed",
            extra={
                "event": "request_completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response
    finally:
        reset_request_id(context_token)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    logger.info(
        "request_rejected",
        extra={
            "event": "request_rejected",
            "error_code": exc.code,
            "status_code": exc.status_code,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        headers={"Retry-After": str(exc.retry_after)} if isinstance(exc, RateLimitError) else None,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
            "requestId": request_id,
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    logger.exception(
        "unhandled_request_error",
        exc_info=(type(exc), exc, exc.__traceback__),
        extra={"event": "unhandled_request_error", "status_code": 500},
    )
    return JSONResponse(
        status_code=500,
        headers={"Cache-Control": PRIVATE_API_CACHE_CONTROL},
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "The request could not be completed.",
                "details": None,
            },
            "requestId": request_id,
        },
    )


app.include_router(api_router)
