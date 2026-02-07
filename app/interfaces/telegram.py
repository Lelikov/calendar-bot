from __future__ import annotations
from typing import Protocol


class ITelegramController(Protocol):
    async def start(self) -> None: ...
