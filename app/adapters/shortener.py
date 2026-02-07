import httpx
import structlog

from app.interfaces.url_shortener import IUrlShortener
from app.settings import Settings


logger = structlog.get_logger(__name__)


class UrlShortenerAdapter(IUrlShortener):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.shortner_url

    async def create_url(self, long_url: str, expires_at: float, external_id: str) -> str | None:
        if not self._check_api_key():
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/v1/urls/shorten",
                    headers={"Content-Type": "application/json", "api-key": self.settings.shortify_api_key},
                    json={
                        "url": long_url,
                        "expires_at": expires_at,
                        "external_id": external_id,
                    },
                )
                response.raise_for_status()
                data = response.json()
                if ident := data.get("ident"):
                    return f"{self.base_url}/{ident}"
            except Exception:
                logger.exception("Failed to shorten URL")
        return None

    async def get_url(self, external_id: str) -> str | None:
        if not self._check_api_key():
            return None
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/api/v1/urls/external/{external_id}",
                    headers={"Content-Type": "application/json", "api-key": self.settings.shortify_api_key},
                )
                response.raise_for_status()
                data = response.json()
                if ident := data.get("ident"):
                    return f"{self.base_url}/{ident}"
            except Exception:
                logger.exception("Failed to get shorten URL data")

    async def update_url_data(
        self,
        long_url: str,
        expires_at: float,
        old_external_id: str,
        new_external_id: str,
    ) -> str | None:
        if not self._check_api_key():
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(
                    f"{self.base_url}/api/v1/urls/external/{old_external_id}",
                    headers={"Content-Type": "application/json", "api-key": self.settings.shortify_api_key},
                    json={
                        "url": long_url,
                        "expires_at": expires_at,
                        "external_id": new_external_id,
                    },
                )
                response.raise_for_status()
                data = response.json()
                if ident := data.get("ident"):
                    return f"{self.base_url}/{ident}"
            except Exception:
                logger.exception("Failed to update shorten URL")
        return None

    async def delete_url(self, *, external_id: str) -> str | None:
        if not self._check_api_key():
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.base_url}/api/v1/urls/external/{external_id}",
                    headers={"Content-Type": "application/json", "api-key": self.settings.shortify_api_key},
                )
                response.raise_for_status()
                logger.info(f"Shortened URL {external_id} deleted")
            except Exception:
                logger.exception("Failed to delete shorten URL")
        return None

    def _check_api_key(self) -> bool:
        if not self.settings.shortify_api_key:
            logger.warning("Shortify API key is not set")
        return bool(self.settings.shortify_api_key)
