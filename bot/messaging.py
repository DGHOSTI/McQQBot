# -*- coding: utf-8 -*-
"""回复通道：统一封装群聊 / 私聊的被动回复发送。"""
__all__ = ["ReplyChannel"]


class ReplyChannel:
    """把 botpy 的群聊/C2C 发送 API 封装成一致的 text/image 接口。

    同一事件可连续回复多条（msg_seq 自动递增）。
    """

    def __init__(self, api, kind: str, msg_id: str, **target):
        """kind: "group" 或 "c2c"；target 为 {"group_openid":...} 或 {"openid":...}。"""
        self._api = api
        self._kind = kind
        self._target = target
        self._msg_id = msg_id
        self._seq = 0

    async def _post(self, **payload):
        self._seq += 1
        payload.setdefault("msg_id", self._msg_id)
        payload["msg_seq"] = self._seq
        if self._kind == "group":
            return await self._api.post_group_message(**self._target, **payload)
        return await self._api.post_c2c_message(**self._target, **payload)

    async def send_text(self, content: str):
        return await self._post(msg_type=0, content=content)

    async def send_image(self, url: str):
        """先上传媒体（拿 file_info）再发送图片消息（msg_type=7）。"""
        if self._kind == "group":
            media = await self._api.post_group_file(
                file_type=1, url=url, srv_send_msg=False, **self._target
            )
        else:
            media = await self._api.post_c2c_file(
                file_type=1, url=url, srv_send_msg=False, **self._target
            )
        return await self._post(msg_type=7, media=media)