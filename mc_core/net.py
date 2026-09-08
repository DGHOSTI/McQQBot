# -*- coding: utf-8 -*-
"""共享 HTTP 工具：aiohttp 会话管理与 JSON / 图片请求。"""
import logging

import aiohttp

_logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


class HttpClient:
    """共享 aiohttp 会话，提供图片可达性探测与 JSON 请求。"""

    def __init__(self):
        self._session = None

    async def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": DEFAULT_USER_AGENT}
            )
        return self._session

    async def fetch_json(self, url: str, timeout: float = 10.0) -> dict | None:
        try:
            session = await self.session()
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status == 200:
                    return await response.json()
        except Exception as error:
            _logger.info("[net] JSON 请求失败 %s: %s", url, error)
        return None

    async def probe_image(self, url: str, timeout: float = 4.0) -> bool:
        """探测 URL 是否返回一张图片。"""
        try:
            session = await self.session()
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status == 200:
                    content_type = response.headers.get("Content-Type", "")
                    return content_type.startswith("image/")
        except Exception:
            pass
        return False

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None


__all__ = ["HttpClient", "DEFAULT_USER_AGENT"]