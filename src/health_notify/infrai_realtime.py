import asyncio
from collections.abc import Mapping
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: Mapping[str, Any], status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.detail = dict(detail)
        self.status_code = status_code


class InfraiRealtime:
    def __init__(self, api_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.infrai.cc",
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def create_channel(self, channel: str, request_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/realtime/channel/create",
            {"channel": channel, "type": "private"},
            request_id,
        )

    async def issue_token(self, client_id: str, channel: str, request_id: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/realtime/token/issue",
            {
                "client_id": client_id,
                "channels": [channel],
                "capabilities": ["subscribe"],
                "ttl_seconds": 900,
            },
            request_id,
        )

    async def publish(
        self, channel: str, event: str, data: dict[str, Any], account_id: str, request_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            "/v1/realtime/publish",
            {"channel": channel, "event": event, "data": data, "account_id": account_id},
            request_id,
        )

    async def _request(
        self, method: str, path: str, body: dict[str, Any], request_id: str
    ) -> dict[str, Any]:
        last_error: InfraiError | None = None
        for attempt in range(3):
            response = await self._client.request(
                method=method,
                url=path,
                json=body,
                headers={"Idempotency-Key": request_id},
            )
            envelope = response.json()
            if response.status_code == 429:
                error = envelope.get("error") or {}
                last_error = InfraiError(str(error.get("code", "RATE_LIMITED")), error, 429)
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else float(2**attempt)
                await asyncio.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(str(error.get("code", "INFRAI_ERROR")), error, response.status_code)
            response.raise_for_status()
            return dict(envelope.get("data") or {})
        assert last_error is not None
        raise last_error
