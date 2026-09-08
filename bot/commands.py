# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# 指令基座：Command 元数据与会话无关的解析 / 分发器。
# ---------------------------------------------------------------------------
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from .messaging import ReplyChannel

# 匹配 @提及：<@!openid>（QQ 可能用数字或字母数字串）或 @昵称
_MENTION_RE = re.compile(r"<@!?[^>]*>|@[\w\u4e00-\u9fff-]+")

# 处理器签名：async (channel, args) -> None
CommandHandler = Callable[[ReplyChannel, str], Awaitable[None]]


@dataclass(frozen=True)
class Command:
    """一条指令的元数据与处理器。"""

    name: str                                  # 规范名（唯一，用于注册与路由）
    handler: CommandHandler
    aliases: tuple[str, ...] = field(default_factory=tuple)
    usage: str = ""                            # 参数用法，如 "[地址]"
    description: str = ""                      # 一句话说明

    def help_line(self) -> str:
        param = f" {self.usage}" if self.usage else ""
        return f"/{self.name}{param} - {self.description}"


class CommandDispatcher:
    """指令注册、解析与分发。"""

    def __init__(self):
        self._commands: dict[str, Command] = {}
        self._alias_map: dict[str, str] = {}

    # -- 注册 ----------------------------------------------------------
    def register(self, command: Command) -> None:
        self._commands[command.name] = command
        self._alias_map[command.name] = command.name
        for alias in command.aliases:
            self._alias_map[alias.lower()] = command.name

    # -- 解析 ----------------------------------------------------------
    @staticmethod
    def clean_content(text: str) -> str:
        """去掉 @提及，只保留指令正文。"""
        return _MENTION_RE.sub("", text or "").strip()

    def parse(self, text: str) -> tuple[str | None, str]:
        """把消息文本解析为 (规范命令名, 参数)；非指令返回 (None, "")。"""
        body = self.clean_content(text)
        if not body.startswith("/"):
            return None, ""
        body = body[1:].strip()
        if not body:
            return None, ""

        parts = body.split(None, 1)
        token = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""
        name = self._alias_map.get(token)
        if name is not None:
            return name, args
        return None, ""

    # -- 分发 ----------------------------------------------------------
    async def dispatch(self, channel: ReplyChannel, text: str) -> bool:
        """分发一条消息；命中指令返回 True，否则返回 False。异常由调用方处理。"""
        name, args = self.parse(text)
        if name is None:
            return False
        await self._commands[name].handler(channel, args)
        return True

    # -- 帮助文本 ------------------------------------------------------
    def help_text(self) -> str:
        return "\n".join(cmd.help_line() for cmd in self._commands.values())


__all__ = ["Command", "CommandDispatcher", "CommandHandler"]