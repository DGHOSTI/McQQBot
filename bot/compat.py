# -*- coding: utf-8 -*-
"""botpy 兼容补丁：支持 QQ「群聊普通消息」事件。

QQ 机器人可能订阅到两种群消息：
- GROUP_AT_MESSAGE_CREATE  （@机器人消息，botpy 原生支持）
- GROUP_MESSAGE_CREATE    （群普通消息，botpy 1.2.1 未实现 → 日志报
  "unknown event group_message_create" 并被丢弃）

这里在运行时往 ``ConnectionState.parsers`` 注入该事件的解析器，
将消息以 GroupMessage 实例分发到 ``on_group_message_create``。
"""
import botpy.connection as _botpy_connection
from botpy.message import GroupMessage

_APPLIED = False


def apply() -> None:
    """注入群普通消息事件解析器（幂等）。"""
    global _APPLIED
    if _APPLIED:
        return
    _APPLIED = True

    original_init = _botpy_connection.ConnectionState.__init__

    def patched_init(state, dispatch, api):
        original_init(state, dispatch, api)
        if "group_message_create" not in state.parsers:
            def parse_group_message_create(payload):
                message = GroupMessage(
                    state.api,
                    payload.get("id", None),
                    payload.get("d", {}),
                )
                dispatch("group_message_create", message)
            state.parsers["group_message_create"] = parse_group_message_create

    _botpy_connection.ConnectionState.__init__ = patched_init


__all__ = ["apply"]