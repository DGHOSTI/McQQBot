# -*- coding: utf-8 -*-
"""Minecraft 玩家外部服务：UUID 解析、档案、渲染图、披风。

`PlayerService` 将缓存作为实例状态持有，独立可测，可与调用方共享 HttpClient。
"""
import asyncio
import base64
import json
import logging
import time

from .net import HttpClient

_logger = logging.getLogger(__name__)

__all__ = ["PlayerService", "uuid_dashed"]


def uuid_dashed(uuid: str) -> str:
    """把 32 位无连字符 UUID 转成 8-4-4-4-12 虚线格式。"""
    u = uuid.replace("-", "")
    return f"{u[0:8]}-{u[8:12]}-{u[12:16]}-{u[16:20]}-{u[20:]}"


class PlayerService:
    """玩家名 / UUID / 档案 / 皮肤渲染图 / 披风 的查询服务。"""

    # 渲染图候选源（需与服务端的端点段一一对应，见 _RENDER_SEGMENTS）
    RENDER_KINDS = ("mc-heads", "crafatar", "minotar")

    # 缓存有效期（秒）
    UUID_TTL = 3600          # UUID / 档案
    RENDER_GOOD_TTL = 3600   # 渲染源成功后 1 小时不重复探测
    RENDER_BAD_TTL = 300     # 渲染源失败后 5 分钟内不重复探测

    def __init__(self, http: HttpClient | None = None):
        self._http = http or HttpClient()

        # 实例级缓存（替代旧版的模块级全局变量，实例相互独立）
        self._uuid_cache: dict[str, dict] = {}
        self._profile_cache: dict[str, dict] = {}
        self._good_render_sources: dict[str, float] = {}

    def _log(self, message: str) -> None:
        _logger.info(message)

    @staticmethod
    def _cached(cache: dict, ttl: float, key: str) -> dict | None:
        item = cache.get(key)
        if item and time.time() - item.get("ts", 0) < ttl:
            return item
        return None

    async def close(self) -> None:
        """关闭内部 HTTP 会话（进程退出前调用）。"""
        await self._http.close()

    # ------------------------------------------------------------------
    # 玩家名 -> UUID
    # ------------------------------------------------------------------
    async def lookup_uuid(self, name: str) -> dict | None:
        """解析正版玩家名 -> {"uuid": 虚线, "name": 官方名}；不存在/失败返回 None。"""
        key = name.strip().lower()
        if not key:
            return None
        cached = self._uuid_cache.get(key)
        if cached and (cached.get("hit") or time.time() - cached["ts"] < self.UUID_TTL):
            return cached if cached.get("uuid") else None

        url = f"https://api.mojang.com/users/profiles/minecraft/{key}"
        entry = {"uuid": None, "name": key, "ts": time.time(), "hit": False}
        data = await self._http.fetch_json(url, timeout=10.0)
        if data:
            entry = {
                "uuid": uuid_dashed(data["id"]),
                "name": data["name"],
                "ts": time.time(),
                "hit": True,
            }
        self._uuid_cache[key] = entry
        return entry if entry.get("uuid") else None

    # ------------------------------------------------------------------
    # 玩家档案（sessionserver）
    # ------------------------------------------------------------------
    async def profile(self, uuid: str) -> dict:
        """sessionserver 档案 -> {"name","model","skin_url","cape_url"}。"""
        u = uuid_dashed(uuid)
        cached = self._cached(self._profile_cache, self.UUID_TTL, u)
        if cached:
            return cached

        result = {"name": "", "model": "classic",
                  "skin_url": None, "cape_url": None, "ts": time.time()}
        textures: dict = {}
        data = await self._http.fetch_json(
            f"https://sessionserver.mojang.com/session/minecraft/profile/{u}",
            timeout=10.0,
        )
        if data:
            result["name"] = data.get("name", "")
            for prop in data.get("properties") or []:
                if prop.get("name") == "textures":
                    try:
                        textures = json.loads(base64.b64decode(prop.get("value", "")))
                    except Exception:
                        textures = {}
                    break

        skins = textures.get("textures") or {}
        skin = skins.get("SKIN", {})
        cape = skins.get("CAPE", {})
        result["model"] = (skin.get("metadata") or {}).get("model", "classic")
        result["skin_url"] = skin.get("url")
        result["cape_url"] = cape.get("url")

        self._profile_cache[u] = result
        return result

    # ------------------------------------------------------------------
    # 皮肤渲染图（mc-heads / crafatar / minotar 回退）
    # ------------------------------------------------------------------
    def _render_urls(self, kind: str, uuid: str) -> dict[str, str]:
        """按渲染种类生成各候选源的 URL；kind 取值 "body" / "head"。"""
        u = uuid_dashed(uuid)
        head_seg = {"body": "body", "head": "head"}
        cra_seg = {"body": "body", "head": "head"}
        min_seg = {"body": "body", "head": "helm"}
        return {
            "mc-heads": f"https://mc-heads.net/{head_seg[kind]}/{u}/128",
            "crafatar": f"https://crafatar.com/renders/{cra_seg[kind]}/{u}?overlay&size=128",
            "minotar": f"https://minotar.net/{min_seg[kind]}/{u}/128",
        }

    async def render_url(self, kind: str, uuid: str) -> str | None:
        """返回皮肤渲染图片 URL（kind: "body"/"head"）；全部源不可达时返回 None。

        多个候选源并发探测，但始终按 RENDER_KINDS 的优先级顺序取用
        （mc-heads 输出等距立体且合成外层皮肤，优先于平面渲染源）。
        """
        now = time.time()
        urls = self._render_urls(kind, uuid)
        # 1) 命中最近确认可用的高优先级源（避免每次探测）
        for source in self.RENDER_KINDS:
            if self._good_render_sources.get(source, 0) > now - self.RENDER_GOOD_TTL:
                return urls[source]
        # 2) 并发探测候选源，按优先级取第一个可用的
        results = await asyncio.gather(
            *[self._http.probe_image(urls[s]) for s in self.RENDER_KINDS],
            return_exceptions=True,
        )
        ok_map = dict(zip(self.RENDER_KINDS, results))
        for source in self.RENDER_KINDS:
            if ok_map.get(source) is True:
                self._good_render_sources[source] = now
                return urls[source]
        # 3) 全部失败：退回最近用过的源（最后一次机会）
        for source in self.RENDER_KINDS:
            last = self._good_render_sources.get(source)
            if last and now - last < self.RENDER_BAD_TTL * 6:
                return urls[source]
        return None