# -*- coding: utf-8 -*-
"""机器人配置：从 config.yaml 加载为类型化的 BotConfig。"""
import os
from dataclasses import dataclass

from botpy.ext.cog_yaml import read

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

DEFAULT_MC_TIMEOUT = 5


@dataclass(frozen=True)
class BotConfig:
    """机器人运行所需的全部配置。"""

    app_id: str
    secret: str
    default_server: str | None = None   # 可选；不配置则需在指令中显式带地址
    mc_timeout: int = DEFAULT_MC_TIMEOUT
    admin_user_openids: frozenset = frozenset()    # 私聊管理员（user_openid）
    admin_group_openids: frozenset = frozenset()   # 群管理员（member_openid）

    @classmethod
    def from_yaml(cls, path: str | None = None) -> "BotConfig":
        raw = read(path or CONFIG_PATH)
        default_server = str(raw.get("default_server") or "").strip() or None
        return cls(
            app_id=str(raw.get("appid") or ""),
            secret=str(raw.get("secret") or ""),
            default_server=default_server,
            mc_timeout=int(raw.get("mc_timeout") or DEFAULT_MC_TIMEOUT),
            admin_user_openids=frozenset(raw.get("admin_user_openids") or []),
            admin_group_openids=frozenset(raw.get("admin_group_openids") or []),
        )


__all__ = ["BotConfig", "CONFIG_PATH"]