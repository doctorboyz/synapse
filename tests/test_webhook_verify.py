"""Tests for webhook HMAC signature verification."""

import json

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from src.api.webhook_verify import (
    _compare_signatures,
    _generate_signature,
    sign_payload,
    verify_webhook_signature,
)


class TestGenerateSignature:
    def test_basic(self):
        sig = _generate_signature("secret", b'{"a":1}')
        assert len(sig) == 64  # hex sha256
        assert isinstance(sig, str)

    def test_different_payloads_different_sigs(self):
        sig1 = _generate_signature("secret", b'{"a":1}')
        sig2 = _generate_signature("secret", b'{"a":2}')
        assert sig1 != sig2

    def test_different_secrets_different_sigs(self):
        sig1 = _generate_signature("secret-a", b'{"a":1}')
        sig2 = _generate_signature("secret-b", b'{"a":1}')
        assert sig1 != sig2


class TestCompareSignatures:
    def test_match(self):
        assert _compare_signatures("abc", "abc") is True

    def test_mismatch(self):
        assert _compare_signatures("abc", "abd") is False

    def test_timing_safe(self):
        # Same length, different content
        assert _compare_signatures("a" * 64, "b" * 64) is False


class TestSignPayload:
    def test_format(self):
        signed = sign_payload("secret", b'{"a":1}')
        assert signed.startswith("sha256=")
        assert len(signed) == 7 + 64


class TestVerifyWebhookSignature:
    @pytest.mark.asyncio
    async def test_no_secret_skips_verification(self):
        body = b'{"title":"x"}'
        request = _make_request(body)
        result = await verify_webhook_signature(request, secret="")
        assert result == body

    @pytest.mark.asyncio
    async def test_valid_signature(self):
        body = b'{"title":"x"}'
        signature = sign_payload("secret", body)
        request = _make_request(body, headers={"x-webhook-signature": signature})
        result = await verify_webhook_signature(request, secret="secret")
        assert result == body

    @pytest.mark.asyncio
    async def test_missing_signature_raises_401(self):
        body = b'{"title":"x"}'
        request = _make_request(body)
        with pytest.raises(HTTPException) as exc_info:
            await verify_webhook_signature(request, secret="secret")
        assert exc_info.value.status_code == 401
        assert "Missing" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_signature_raises_401(self):
        body = b'{"title":"x"}'
        request = _make_request(body, headers={"x-webhook-signature": "sha256=bad" * 10})
        with pytest.raises(HTTPException) as exc_info:
            await verify_webhook_signature(request, secret="secret")
        assert exc_info.value.status_code == 401
        assert "Invalid" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_plain_hex_signature(self):
        """Accept signatures without 'sha256=' prefix."""
        body = b'{"title":"x"}'
        signature = _generate_signature("secret", body)
        request = _make_request(body, headers={"x-webhook-signature": signature})
        result = await verify_webhook_signature(request, secret="secret")
        assert result == body


async def _async_body(body: bytes):
    return body


def _make_request(body: bytes, headers: dict | None = None):
    from starlette.datastructures import Headers

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/webhook",
        "headers": [],
    }
    request = Request(scope)
    # Monkey-patch body to avoid async read
    request._body = body
    request.body = lambda: _async_body(body)
    if headers:
        request._headers = Headers(raw=[(k.encode(), v.encode()) for k, v in headers.items()])
    return request
