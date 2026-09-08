"""mc_core —— Minecraft 领域层。

纯 MC 逻辑，不依赖 botpy / QQ，可独立测试与复用。
"""
from .formatter import format_status_text
from .net import HttpClient
from .player import PlayerService, uuid_dashed
from .server import ServerIconService, ServerProbe, host_of
from .text import motd_to_text, strip_color

__all__ = [
    "format_status_text",
    "host_of",
    "HttpClient",
    "motd_to_text",
    "PlayerService",
    "ServerIconService",
    "ServerProbe",
    "strip_color",
    "uuid_dashed",
]