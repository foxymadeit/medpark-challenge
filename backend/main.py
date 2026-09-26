import logging
import smtplib

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from offline import block_outbound, enforce_offline
from schemas import EmailSendRequest, EmailSendResponse
from services.EmailService import DistributionListNotConfiguredError, EmailService

enforce_offline()
block_outbound()

app = FastAPI()
logger = logging.getLogger(__name__)
email_service = EmailService()


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "backend initialized."}


@app.post("/email/send", response_model=EmailSendResponse)
async def send_mom_email(
    request: EmailSendRequest,
) -> EmailSendResponse | JSONResponse:
    """Email structured minutes to the configured meeting-type distribution list."""
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

