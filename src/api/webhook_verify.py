"""Webhook signature verification — HMAC-SHA256."""

import hashlib
import hmac
import logging

from fastapi import HTTPException, Request

log = logging.getLogger("synapse.webhook")


def _generate_signature(secret: str, payload_bytes: bytes) -> str:
    """Generate HMAC-SHA256 hex digest for payload bytes."""
    return hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


def _compare_signatures(expected: str, provided: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    return hmac.compare_digest(expected, provided)


async def verify_webhook_signature(
    request: Request,
    secret: str,
    header_name: str = "x-webhook-signature",
) -> bytes:
    """Verify webhook HMAC signature. Returns raw body bytes if valid.

    Raises HTTPException 401 if signature missing or invalid.
    """
    if not secret:
        # No secret configured — skip verification
        return await request.body()

    body = await request.body()
    signature_header = request.headers.get(header_name, "")

    if not signature_header:
        log.warning("Webhook missing %s header", header_name)
        raise HTTPException(status_code=401, detail="Missing webhook signature")

    # Support formats: "sha256=<hex>" or plain "<hex>"
    if signature_header.startswith("sha256="):
        provided = signature_header[7:]
    else:
        provided = signature_header

    expected = _generate_signature(secret, body)

    if not _compare_signatures(expected, provided):
        log.warning("Webhook signature mismatch")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    return body


def sign_payload(secret: str, payload_bytes: bytes) -> str:
    """Sign payload with secret for testing / client use."""
    return f"sha256={_generate_signature(secret, payload_bytes)}"
