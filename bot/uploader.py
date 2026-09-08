# -*- coding: utf-8 -*-
"""图片托管：把本地生成的图片上传到匿名图床，换取 QQ 可抓取的公网 URL。

botpy 的媒体上传接口只接受"公网 URL"，本地渲染产物需先经此处转存。
"""
import logging

import aiohttp

_logger = logging.getLogger(__name__)

__all__ = ["ImageHost"]

# uguu.se：匿名上传，返回直链（国内可达，已实测）
UGUU_ENDPOINT = "https://uguu.se/upload"


class ImageHost:
    """把图片 bytes 转成可公网访问的直链。"""

    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout

    async def upload_png(self, data: bytes) -> str | None:
        """上传 PNG bytes -> 直链 URL；失败返回 None。"""
        return await self.upload_bytes(data, filename="skin.png",
                                       content_type="image/png")

    async def upload_bytes(self, data: bytes, filename: str,
                           content_type: str) -> str | None:
        try:
            async with aiohttp.ClientSession() as session:
                form = aiohttp.FormData()
                form.add_field("files[]", data, filename=filename,
                               content_type=content_type)
                async with session.post(
                        UGUU_ENDPOINT, data=form,
                        timeout=aiohttp.ClientTimeout(total=self._timeout)) as resp:
                    if resp.status == 200:
                        payload = await resp.json()
                        files = (payload or {}).get("files") or []
                        if files:
                            url = files[0].get("url")
                            if url:
                                return str(url).replace("\\/", "/")
        except Exception as error:
            _logger.warning("[uploader] 图床上传失败: %r", error)
        return None