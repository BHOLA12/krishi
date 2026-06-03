"""
Twilio Webhook Signature Validator
===================================
Twilio signs every incoming webhook request with an HMAC-SHA1 signature derived
from your Auth Token. This middleware validates that signature on all IVR and
missed-call webhook endpoints, ensuring that:

  - Only genuine Twilio requests are processed
  - Forged webhooks (which could trigger unlimited outbound calls at your expense)
    are rejected with HTTP 403

Reference: https://www.twilio.com/docs/usage/webhooks/webhooks-security

Usage:
    Add `Depends(validate_twilio_webhook)` to any route that receives Twilio webhooks.

Disable:
    Set TWILIO_WEBHOOK_VALIDATION=False in .env for local development without ngrok.
    NEVER disable in production.
"""

from fastapi import Request, HTTPException, Depends
from app.core.config import settings
import structlog

logger = structlog.get_logger()


async def validate_twilio_webhook(request: Request) -> None:
    """
    FastAPI dependency that validates the X-Twilio-Signature header on incoming
    Twilio webhook requests.

    Raises HTTP 403 if the signature is missing or invalid.
    Skips validation if TWILIO_WEBHOOK_VALIDATION=False (development mode only).
    """
    if not settings.TWILIO_WEBHOOK_VALIDATION:
        logger.warning(
            "Twilio webhook signature validation is DISABLED. "
            "This is only safe in local development. Enable in production."
        )
        return

    # Only validate if Twilio is the active provider
    if settings.TELEPHONY_PROVIDER.lower() != "twilio":
        return

    # Auth token must be configured to validate
    auth_token = settings.TWILIO_AUTH_TOKEN
    if not auth_token or auth_token == "your_twilio_auth_token_here":
        logger.warning("TWILIO_AUTH_TOKEN not set — skipping signature validation")
        return

    try:
        from twilio.request_validator import RequestValidator
    except ImportError:
        logger.error("twilio package not installed — cannot validate webhook signature")
        return

    # Read form data for POST requests (Twilio sends params as form-encoded body)
    form_params: dict = {}
    if request.method == "POST":
        try:
            form_data = await request.form()
            form_params = dict(form_data)
        except Exception:
            pass

    # For GET requests, Twilio includes params as query string
    query_params = dict(request.query_params)
    all_params = {**query_params, **form_params}

    # Reconstruct the full URL that Twilio signed
    # Use BASE_URL from settings since the request URL may be the internal container URL
    path = request.url.path
    query_string = request.url.query
    if query_string:
        signed_url = f"{settings.BASE_URL.rstrip('/')}{path}?{query_string}"
    else:
        signed_url = f"{settings.BASE_URL.rstrip('/')}{path}"

    signature = request.headers.get("X-Twilio-Signature", "")

    validator = RequestValidator(auth_token)
    is_valid = validator.validate(signed_url, all_params, signature)

    if not is_valid:
        logger.warning(
            "Twilio webhook signature validation FAILED",
            url=signed_url,
            signature_present=bool(signature),
        )
        raise HTTPException(
            status_code=403,
            detail="Invalid Twilio webhook signature. Request rejected."
        )

    logger.info("Twilio webhook signature validated successfully")
