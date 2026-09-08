"""bot —— QQ 机器人应用层。

依赖关系：bot -> mc_core。仅在本层直接接触 botpy。
"""
from .client import McBotClient
from .commands import Command, CommandDispatcher
from .config import BotConfig
from .messaging import ReplyChannel

__all__ = [
    "BotConfig",
    "Command",
    "CommandDispatcher",
    "McBotClient",
    "ReplyChannel",
]