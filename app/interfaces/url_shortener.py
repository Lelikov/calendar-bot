from __future__ import annotations
from typing import Protocol


class IUrlShortener(Protocol):
    async def create_url(self, long_url: str, expires_at: float, external_id: str) -> str | None: ...

    async def get_url(self, external_id: str) -> str | None: ...

    async def update_url_data(
        self,
        *,
        long_url: str,
        expires_at: float,
        new_external_id: str,
        old_external_id: str,
    ) -> str | None: ...

    async def delete_url(self, *, external_id: str) -> str | None: ...
