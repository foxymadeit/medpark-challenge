import logging
import os
import smtplib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=False)   # before any module reads its settings

from offline import block_outbound, enforce_offline  # noqa: E402
from schemas import EmailSendRequest, EmailSendResponse  # noqa: E402
from services.EmailService import DistributionListNotConfiguredError, EmailService  # noqa: E402

enforce_offline()
block_outbound()

import api  # noqa: E402  (after the network guard, so nothing it imports can reach out)
import delivery  # noqa: E402
import jobs  # noqa: E402
import security  # noqa: E402

logger = logging.getLogger(__name__)
FRONTEND = Path(os.getenv("LIMINAL_FRONTEND_DIST", "")) if os.getenv("LIMINAL_FRONTEND_DIST") else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    security.ensure_admin()
    api.seed()
    threads = []
    if os.getenv("LIMINAL_START_WORKERS", "1") == "1":
        threads = [jobs.Worker(), delivery.Scheduler()]
        for t in threads:
            t.start()
    yield
    for t in threads:
        t.stopping.set()


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), geolocation=(), microphone=(self)")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response


app = FastAPI(title="Liminal", lifespan=lifespan)
app.add_middleware(security.AuditTrail)
app.add_middleware(security.OriginCheck)
app.add_middleware(SecurityHeaders)
app.include_router(api.router)
email_service = EmailService()


@app.get("/")
def root():
    if FRONTEND and (FRONTEND / "index.html").is_file():
        return FileResponse(FRONTEND / "index.html")
    return {"message": "backend initialized."}


@app.post("/api/email/send", response_model=EmailSendResponse)
async def send_mom_email(
    request: EmailSendRequest,
    user: dict = Depends(security.require_admin),
) -> EmailSendResponse | JSONResponse:
    """Email structured minutes to the configured meeting-type distribution list.
    Administrators only: under /api it gets the origin check and the audit trail."""
    try:
        result = await run_in_threadpool(
            email_service.send_mom_email,
            request.minutes,
            participant_emails=tuple(request.participant_emails),
        )
    except DistributionListNotConfiguredError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (OSError, smtplib.SMTPException) as error:
        logger.exception("Failed to send MoM email")
        raise HTTPException(
            status_code=502,
            detail="Could not deliver email through SMTP.",
        ) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if result.refused:
        status_code = 207 if result.accepted else 502
        status = "partial" if result.accepted else "failed"
        message = "Some recipients were refused." if result.accepted else "All recipients were refused."
    else:
        status_code = 200
        status = "sent"
        message = "Email sent."

    response = EmailSendResponse(
        status=status,
        accepted_count=len(result.accepted),
        refused_count=len(result.refused),
        message=message,
    )
    if status_code != 200:
        return JSONResponse(status_code=status_code, content=response.model_dump())
    return response



if FRONTEND:
    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        """The built web app from the same origin; unknown paths get index.html (client routes)."""
        root = FRONTEND.resolve()
        target = (root / path).resolve()
        if path.startswith("api/") or not str(target).startswith(str(root)):
            raise HTTPException(404)
        return FileResponse(target if target.is_file() else root / "index.html")
