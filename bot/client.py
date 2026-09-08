# -*- coding: utf-8 -*-
"""机器人客户端：处理 QQ 事件，把消息交予 CommandDispatcher 分发。"""
import logging
import time

import botpy
from botpy.message import GroupMessage

from .commands import CommandDispatcher
from .messaging import ReplyChannel

_logger = logging.getLogger(__name__)

__all__ = ["McBotClient"]


class McBotClient(botpy.Client):
    """QQ 机器人客户端，仅负责事件接收与分发。"""

    DEDUP_WINDOW = 5.0   # 同一 msg_id 在该秒数内只处理一次

    def __init__(self, dispatcher: CommandDispatcher, *args, **kwargs):
        # 禁止 botpy 默认把日志写成 cwd 下的 botpy.log，统一由 logging_setup 管理
        kwargs.setdefault("ext_handlers", False)
        super().__init__(*args, **kwargs)
        self._dispatcher = dispatcher
        self._seen_group_ids: dict[str, float] = {}

    async def _handle(self, text: str, kind: str, msg_id: str, **target) -> None:
        """统一入口：把文本交给分发器，出错时兜底回复。"""
        channel = ReplyChannel(self.api, kind, msg_id, **target)
        name, args = self._dispatcher.parse(text)
        if name is None:
            return
        _logger.info("[指令] %s 参数=%r", name, args)
        try:
            await self._dispatcher.dispatch(channel, text)
        except Exception as error:
            _logger.error("[指令异常] /%s: %r", name, error)
            try:
                await channel.send_text(f"执行 /{name} 时出错, 请稍后再试")
            except Exception:
                pass

    # -- botpy 事件 ---------------------------------------------------
    async def on_ready(self):
        _logger.info("(机器人) %s 已上线！群聊 @我 或私聊发送 /help 查看指令",
                     self.robot.name)

    async def on_group_at_message_create(self, message: GroupMessage):
        _logger.info("[群@] %s 内容: %r", message.group_openid, message.content)
        await self._on_group_message(message)

    async def on_group_message_create(self, message: GroupMessage):
        """群聊普通消息（无需 @，靠 compat.py 补丁支持）。"""
        _logger.info("[群消息] %s 内容: %r", message.group_openid, message.content)
        await self._on_group_message(message)

    async def _on_group_message(self, message: GroupMessage) -> None:
        """群消息统一入口（对 @消息与普通消息去重，避免重复回复）。"""
        msg_id = message.id
        now = time.monotonic()
        for mid, ts in list(self._seen_group_ids.items()):
            if now - ts > self.DEDUP_WINDOW:
                self._seen_group_ids.pop(mid, None)
        if msg_id in self._seen_group_ids:
            _logger.info("[群消息] 重复事件忽略 msg_id=%s", msg_id)
            return
        self._seen_group_ids[msg_id] = now
        await self._handle(
            message.content, "group", msg_id,
            group_openid=message.group_openid,
        )

    async def on_c2c_message_create(self, message):
        _logger.info("[私聊] %s 内容: %r",
                     getattr(message.author, "user_openid", None), message.content)
        await self._handle(
            message.content, "c2c", message.id,
            openid=message.author.user_openid,
        )

    async def on_group_add_robot(self, event):
        _logger.info("[加群] 机器人加入群 %s", event.group_openid)
        await event._api.post_group_message(
            group_openid=event.group_openid,
            msg_type=0,
            content="🤖 我的世界机器人已加入本群！\n\n" + self._dispatcher.help_text(),
        )