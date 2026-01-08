import httpx
import structlog

from app.settings import get_settings


logger = structlog.get_logger(__name__)
cfg = get_settings()


class UrlShortenerAdapter:
    BASE_URL = cfg.shortner_url

    async def create_short_url(self, long_url: str, expires_at: float, external_id: str) -> str | None:
        if not cfg.shortify_api_key:
            logger.warning("Shortify API key is not set")
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/api/v1/urls/shorten",
                    headers={"Content-Type": "application/json", "api-key": cfg.shortify_api_key},
                    json={
                        "url": long_url,
                        "expires_at": expires_at,
                        "external_id": external_id,
                    },
                )
                response.raise_for_status()
                data = response.json()
                if ident := data.get("ident"):
                    return f"{self.BASE_URL}/{ident}"
            except Exception:
                logger.exception("Failed to shorten URL")
        return None

    async def update_url_data(
        self,
        long_url: str,
        expires_at: float,
        old_external_id: str,
        new_external_id: str,
    ) -> str | None:
        if not cfg.shortify_api_key:
            logger.warning("Shortify API key is not set")
            return None

        async with httpx.AsyncClient() as client:
            try:
                response = await client.patch(
                    f"{self.BASE_URL}/api/v1/urls/external/{old_external_id}",
                    headers={"Content-Type": "application/json", "api-key": cfg.shortify_api_key},
                    json={
                        "url": long_url,
                        "expires_at": expires_at,
                        "external_id": new_external_id,
                    },
                )
                response.raise_for_status()
                data = response.json()
                if ident := data.get("ident"):
                    return f"{self.BASE_URL}/{ident}"
            except Exception:
                logger.exception("Failed to shorten URL")
        return None
