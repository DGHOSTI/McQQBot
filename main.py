# -*- coding: utf-8 -*-
"""QQ 机器人入口：初始化日志 → 加载配置 → 组装依赖 → 启动。

运行：
    python main.py
"""
import botpy

from bot.client import McBotClient
from bot.compat import apply as apply_botpy_compat
from bot.config import BotConfig
from bot.handlers import build_dispatcher
from bot.logging_setup import setup_logging
from bot.uploader import ImageHost
from mc_core import HttpClient, PlayerService, ServerIconService
from mc_core.render import SkinRenderer


def main() -> None:
    setup_logging()
    apply_botpy_compat()   # 支持 QQ 群聊普通消息(GROUP_MESSAGE_CREATE)
    config = BotConfig.from_yaml()

    # 共享同一 HttpClient，避免重复建立连接
    http = HttpClient()
    players = PlayerService(http=http)
    icons = ServerIconService(http=http)
    renderer = SkinRenderer()
    uploader = ImageHost()

    dispatcher = build_dispatcher(
        players=players,
        icons=icons,
        renderer=renderer,
        uploader=uploader,
        default_server=config.default_server,
        mc_timeout=config.mc_timeout,
    )

    intents = botpy.Intents(public_messages=True)
    client = McBotClient(dispatcher=dispatcher, intents=intents)
    client.run(appid=config.app_id, secret=config.secret)


if __name__ == "__main__":
    main()