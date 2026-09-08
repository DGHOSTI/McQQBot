# -*- coding: utf-8 -*-
"""Minecraft Java 服务器检测：ServerProbe(协议探测) 与 ServerIconService(图标)。"""
import time

from mcstatus import JavaServer

from .net import HttpClient
from .text import motd_to_text

__all__ = ["ServerProbe", "ServerIconService", "host_of"]


def host_of(address: str) -> str:
    """从 'host:port' 形式的服务器地址中取出域名/IP（支持 IPv6）。"""
    addr = str(address).strip()
    if addr.startswith("["):
        return addr[1:].split("]")[0]
    if ":" in addr:
        return addr.rsplit(":", 1)[0]
    return addr


class ServerProbe:
    """封装 mcstatus：支持 SRV 解析、地址带端口、超时设置。"""

    DEFAULT_PORT = 25565

    def __init__(self, address: str, timeout: int = 10):
        self.address = str(address)
        self.timeout = timeout
        # lookup() 会自动解析 SRV 记录，隐藏真实 IP/端口的域名也能直连
        server = JavaServer.lookup(self.address, timeout=timeout)
        resolved = getattr(server, "address", None)
        if resolved is not None and getattr(resolved, "host", None):
            self.resolved_host = resolved.host
            self.resolved_port = resolved.port
        else:
            self.resolved_host = self.address
            self.resolved_port = self.DEFAULT_PORT
        self._server = server

    @property
    def resolved_address(self) -> str:
        """SRV 解析后的真实 host:port。"""
        return f"{self.resolved_host}:{self.resolved_port}"

    def status(self) -> dict:
        """一次握手取状态+延迟（延迟由 mcstatus 内部测量）。"""
        status = self._server.status()
        return {
            "motd": motd_to_text(status.description),
            "version": status.version.name,
            "protocol": status.version.protocol,
            "players_online": status.players.online,
            "players_max": status.players.max,
            "latency": round(status.latency, 1),
            "has_icon": bool(getattr(status, "icon", None)),
            # sample 仅在在线人数不多时由服务器返回
            "sample": [getattr(p, "name", "") for p in (status.players.sample or [])],
        }

    def ping(self) -> dict:
        """只测握手延迟。"""
        return {"latency": round(self._server.ping(), 1)}

    def query(self) -> dict:
        """全量查询（需要服务器开启 enable-query=true）。"""
        query = self._server.query()
        return {
            "motd": motd_to_text(
                query.motd.to_plain() if hasattr(query.motd, "to_plain") else query.motd
            ),
            "map": query.map,
            "brand": query.software.brand,
            "software": query.software.version,
            "plugins": query.software.plugins,
            "players_online": query.players.online,
            "players_max": query.players.max,
            "players": sorted(query.players.names),
        }

    def check(self, with_query: bool = False) -> dict:
        """组合为统一的检测结果 dict。"""
        result = {
            "address": self.address,
            "resolved": self.resolved_address,
            "online": True,
            **self.status(),
        }
        if with_query:
            try:
                result["query"] = self.query()
            except Exception as error:
                result["query"] = None
                result["query_error"] = str(error)
        return result


class ServerIconService:
    """服务器图标查询（mcsrvstat），带可达性探测与结果缓存。"""

    CACHE_TTL = 1800   # 探测结果缓存 30 分钟
    PROBE_TIMEOUT = 6.0

    def __init__(self, http: HttpClient | None = None):
        self._http = http or HttpClient()
        self._cache: dict[str, dict] = {}   # host -> {"ts": float, "url": str | None}

    async def icon_url(self, address: str) -> str | None:
        """返回服务器图标图片 URL；未设图标或源不可达时返回 None。"""
        host = host_of(address)
        now = time.time()
        cached = self._cache.get(host)
        if cached and now - cached["ts"] < self.CACHE_TTL:
            return cached["url"]

        url = f"https://api.mcsrvstat.us/icon/{host}"
        ok = await self._http.probe_image(url, timeout=self.PROBE_TIMEOUT)
        self._cache[host] = {"ts": now, "url": url if ok else None}
        return url if ok else None