# -*- coding: utf-8 -*-
"""Minecraft 皮肤 3D 渲染服务（基于 vendored 的 MinePI 库）。

输出"走路姿势"的立体全身图 / 立体头像 / 带披风背面图。
"""
import asyncio
import io
import logging
import urllib.request
from collections import OrderedDict

from PIL import Image, ImageDraw

from vendor.minepi import Skin

_logger = logging.getLogger(__name__)
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      " (KHTML, like Gecko) Chrome/126.0 Safari/537.36")

__all__ = ["SkinRenderer", "DEFAULT_POSE"]

# 背景卡片参数（模型四周留白 + 圆角渐变背景；不加阴影）
_PAD_X_RATIO = 0.16      # 左右留白（相对模型宽度）
_PAD_TOP_RATIO = 0.12    # 顶部留白
_PAD_BOTTOM_RATIO = 0.16  # 底部留白
_BG_TOP = (238, 240, 245)
_BG_BOTTOM = (203, 210, 221)
_RADIUS = 24             # 圆角半径


def _card_background(img: Image.Image) -> Image.Image:
    """裁掉多余透明后，居中放到圆角渐变背景上（无阴影）。"""
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    w, h = img.size
    pad_x = max(12, int(w * _PAD_X_RATIO))
    top = max(12, int(h * _PAD_TOP_RATIO))
    bottom = max(18, int(h * _PAD_BOTTOM_RATIO))
    width, height = w + pad_x * 2, h + top + bottom

    # 竖向渐变背景
    bg = Image.new("RGBA", (1, height))
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(int(a + (b - a) * t)
                      for a, b in zip(_BG_TOP, _BG_BOTTOM)) + (255,)
        bg.putpixel((0, y), color)
    bg = bg.resize((width, height))

    # 圆角遮罩
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, width - 1, height - 1], radius=_RADIUS, fill=255)
    bg.putalpha(mask)

    bg.alpha_composite(img, (pad_x, top))
    return bg


# 定稿默认参数（走路姿势 B：右臂前摆、左腿前迈、手臂直摆）
DEFAULT_POSE = {
    "hr": 25,      # 水平偏转
    "vr": -15,     # 垂直俯仰
    "hrh": 0,
    "vrla": -25,   # 左臂
    "vrra": 25,    # 右臂
    "vrll": 20,    # 左腿
    "vrrl": -20,   # 右腿
    "ratio": 16,
}
# 背面展示披风的偏转增量（hr + 180）
CAPE_HR_OFFSET = 180


def _download_image(url: str) -> Image.Image:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=25) as response:
        return Image.open(io.BytesIO(response.read())).convert("RGBA")


class SkinRenderer:
    """本地渲染 MC 皮肤：全身走路姿势 / 头部 / 带披风背面。

    皮肤/披风纹理按 uuid 缓存，避免重复下载。
    """

    TEXTURE_CACHE_MAX = 32   # 最多缓存的皮肤纹理数（避免无界增长）

    def __init__(self):
        # uuid -> 皮肤 RGBA（LRU 淘汰）
        self._textures: "OrderedDict[str, Image.Image]" = OrderedDict()

    async def close(self) -> None:
        self._textures.clear()

    async def load_skin(self, uuid: str, skin_url: str) -> Image.Image:
        cached = self._textures.get(uuid)
        if cached is not None:
            self._textures.move_to_end(uuid)
            return cached
        image = await asyncio.to_thread(_download_image, skin_url)
        self._textures[uuid] = image
        self._textures.move_to_end(uuid)
        while len(self._textures) > self.TEXTURE_CACHE_MAX:
            self._textures.popitem(last=False)
        return image

    async def load_cape(self, cape_url: str) -> Image.Image:
        return await asyncio.to_thread(_download_image, cape_url)

    # ------------------------------------------------------------------
    SSAA = 2   # 超采样倍数：以 2 倍分辨率渲染再缩小，平滑边缘锯齿

    @staticmethod
    def _render_sync(kind: str, skin: Image.Image, cape: Image.Image | None,
                     pose: dict) -> Image.Image:
        """子线程内跑 MinePI（CPU 密集），避免阻塞事件循环。

        用 pose["ratio"]*SSAA 渲染，再 LANCZOS 缩回目标尺寸（抗锯齿）。
        """
        ratio = int(pose["ratio"]) * SkinRenderer.SSAA

        async def _do() -> Image.Image:
            mc_skin = Skin(raw_skin=skin, raw_cape=cape)
            if kind == "head":
                return await mc_skin.render_head(
                    vr=pose["vr"], hr=pose["hr"], ratio=ratio,
                    display_hair=True, aa=False,
                )
            return await mc_skin.render_skin(
                vr=pose["vr"], hr=pose["hr"], hrh=pose["hrh"],
                vrla=pose["vrla"], vrra=pose["vrra"],
                vrll=pose["vrll"], vrrl=pose["vrrl"],
                ratio=ratio,
                display_second_layer=True, display_hair=True,
                display_cape=cape is not None,
                aa=False,
            )

        img = asyncio.run(_do())
        if SkinRenderer.SSAA > 1:
            size = (max(1, round(img.width / SkinRenderer.SSAA)),
                    max(1, round(img.height / SkinRenderer.SSAA)))
            img = img.resize(size, Image.LANCZOS)
        return img

    async def render_full_body(self, uuid: str, skin_url: str,
                               cape_url: str | None = None,
                               pose: dict | None = None) -> bytes:
        """渲染全身走路姿势 PNG；cape_url 提供时把披风披上。"""
        skin = await self.load_skin(uuid, skin_url)
        cape = await self.load_cape(cape_url) if cape_url else None
        img = await asyncio.to_thread(
            self._render_sync, "body", skin, cape, pose or DEFAULT_POSE)
        return self._to_png(img)

    async def render_back_with_cape(self, uuid: str, skin_url: str,
                                    cape_url: str) -> bytes:
        """渲染背面带披风全身图（展示披风外表面）。"""
        skin = await self.load_skin(uuid, skin_url)
        cape = await self.load_cape(cape_url)
        pose = dict(DEFAULT_POSE)
        pose["hr"] = (pose["hr"] + CAPE_HR_OFFSET) % 360
        img = await asyncio.to_thread(
            self._render_sync, "body", skin, cape, pose)
        return self._to_png(img)

    async def render_head(self, uuid: str, skin_url: str) -> bytes:
        """渲染立体头像 PNG（含头发层）。"""
        skin = await self.load_skin(uuid, skin_url)
        img = await asyncio.to_thread(
            self._render_sync, "head", skin, None, DEFAULT_POSE)
        return self._to_png(img)

    @staticmethod
    def _to_png(img: Image.Image) -> bytes:
        img = _card_background(img)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()