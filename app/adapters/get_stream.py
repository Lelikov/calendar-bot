import base64
import hashlib
import logging

import structlog
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from stream_chat import StreamChat, StreamChatAsync
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from app.interfaces.chat import IChatClient


logger = structlog.get_logger(__name__)


class GetStreamAdapter(IChatClient):
    def __init__(self, chat_api_key: str, chat_api_secret: str, user_id_encryption_key: str) -> None:
        self.chat_api_key = chat_api_key
        self.chat_api_secret = chat_api_secret
        self.encryption_key = hashlib.sha256(user_id_encryption_key.encode()).digest()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def create_chat(self, *, channel_id: str, organizer_id: str, client_id: str) -> None:
        organizer_id = self._encode_user_id(user_id=organizer_id)
        client_id = self._encode_user_id(user_id=client_id)
        async with StreamChatAsync(api_key=self.chat_api_key, api_secret=self.chat_api_secret) as client:
            await client.upsert_users(
                [
                    {"id": organizer_id},
                    {"id": client_id},
                ],
            )
            channel = client.channel(
                channel_type="messaging",
                channel_id=channel_id,
                data={"members": [organizer_id, client_id]},
            )
            await channel.create(user_id=organizer_id)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def delete_chat(self, *, channel_id: str) -> None:
        async with StreamChatAsync(api_key=self.chat_api_key, api_secret=self.chat_api_secret) as client:
            channel = client.channel(channel_type="messaging", channel_id=channel_id)
            await channel.delete()

    def create_token(self, *, user_id: str, name: str, expires_at: int) -> str:
        client = StreamChat(api_key=self.chat_api_key, api_secret=self.chat_api_secret)
        return client.create_token(
            user_id=self._encode_user_id(user_id=user_id),
            exp=expires_at,
            name=name,
        )

    def _encode_user_id(self, *, user_id: str) -> str:
        cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(b"\x00" * 16), backend=default_backend())
        encryptor = cipher.encryptor()
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(user_id.encode()) + padder.finalize()
        encrypted = encryptor.update(padded_data) + encryptor.finalize()
        return base64.urlsafe_b64encode(encrypted).decode().replace("=", "")

    def _decode_user_id(self, *, encoded_user_id: str) -> str:
        padding_needed = len(encoded_user_id) % 4
        if padding_needed:
            encoded_user_id += "=" * (4 - padding_needed)

        encrypted_data = base64.urlsafe_b64decode(encoded_user_id)

        cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(b"\x00" * 16), backend=default_backend())
        decryptor = cipher.decryptor()

        padded_data = decryptor.update(encrypted_data) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        user_id = unpadder.update(padded_data) + unpadder.finalize()

        return user_id.decode()
