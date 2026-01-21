from typing import Protocol

import structlog


logger = structlog.get_logger(__name__)


class IChatClient(Protocol):
    async def create_chat(self, *, channel_id: str, organizer_id: str, client_id: str) -> None:
        pass

    async def delete_chat(self, *, channel_id: str) -> None:
        pass

    def create_token(self, *, user_id: str, name: str, expires_at: int) -> str:
        pass


class ChatController:
    def __init__(self, client: IChatClient) -> None:
        self.client = client

    async def create_chat(self, *, channel_id: str, organizer_id: str, client_id: str) -> None:
        logger.info("Creating chat", channel_id=channel_id, organizer_id=organizer_id, client_id=client_id)
        await self.client.create_chat(channel_id=channel_id, organizer_id=organizer_id, client_id=client_id)
        logger.info("Chat created", channel_id=channel_id, organizer_id=organizer_id, client_id=client_id)

    async def delete_chat(self, *, channel_id: str) -> None:
        logger.info("Deleting chat", channel_id=channel_id)
        await self.client.delete_chat(channel_id=channel_id)
        logger.info("Chat deleted", channel_id=channel_id)

    def create_token(self, *, user_id: str, name: str, expires_at: int) -> str:
        logger.info("Token create", user_id=user_id, name=name, expires_at=expires_at)
        return self.client.create_token(user_id=user_id, name=name, expires_at=expires_at)
