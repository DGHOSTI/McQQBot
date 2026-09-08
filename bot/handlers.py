# -*- coding: utf-8 -*-
"""业务指令：Command handler 的定义与装配（依赖注入）。

通过 ``build_dispatcher`` 把 PlayerService / ServerIconService / SkinRenderer /
ImageHost 等依赖注入给各 handler，模块之间不直接引用具体服务实例。
"""
import asyncio
import logging

from mc_core import PlayerService, ServerIconService, ServerProbe, format_status_text
from mc_core.render import SkinRenderer

from .commands import Command, CommandDispatcher, CommandHandler
from .uploader import ImageHost

_logger = logging.getLogger(__name__)

__all__ = ["build_dispatcher"]


def build_dispatcher(
    *,
    players: PlayerService,
    icons: ServerIconService,
    renderer: SkinRenderer,
    uploader: ImageHost,
    default_server: str | None,
    mc_timeout: int,
) -> CommandDispatcher:
    """装配指令分发器。"""
    dispatcher = CommandDispatcher()

    def _static_handler(text: str) -> CommandHandler:
        async def handler(channel, args):
            await channel.send_text(text)
        return handler

    def _resolve_address(args: str) -> str | None:
        return args or default_server

    # ---- /server --------------------------------------------------------
    async def server_cmd(channel, args):
        address = _resolve_address(args)
        if not address:
            return await channel.send_text("用法: /server <address>\n(未配置默认服务器)")
        probe = ServerProbe(address, timeout=mc_timeout)
        result = await asyncio.to_thread(probe.check)
        text = format_status_text(result)
        # 服务器设置了图标才附带图标图，否则只发文字状态
        if result.get("online") and result.get("has_icon"):
            icon_url = await icons.icon_url(address)
            if icon_url:
                await channel.send_image(icon_url)
        await channel.send_text(text)

    dispatcher.register(Command(
        name="server", handler=server_cmd,
        aliases=("status",),
        usage="[address]", description="服务器状态",
    ))

    # ---- /skin /head ----------------------------------------------------
    async def _render_and_send(channel, info, kind, label_cn):
        """渲染 3D 图 -> 图床 -> 发送；成功返回 True"""
        profile = await players.profile(info["uuid"])
        skin_url = profile.get("skin_url")
        if not skin_url:
            await channel.send_text(f"{info['name']} 的皮肤数据不可用, 无法渲染")
            return False
        try:
            if kind == "head":
                png = await renderer.render_head(info["uuid"], skin_url)
            else:
                png = await renderer.render_full_body(info["uuid"], skin_url)
        except Exception as error:
            _logger.warning("渲染 %s 失败: %r", info["name"], error)
            await channel.send_text(f"渲染 {info['name']} 失败, 请稍后再试")
            return False
        url = await uploader.upload_png(png)
        if not url:
            await channel.send_text("图片托管暂不可用, 请稍后再试")
            return False
        await channel.send_text(f"玩家 {info['name']} 的{label_cn}预览:")
        await channel.send_image(url)
        return True

    def make_render_cmd(kind: str, label_cn: str, command_word: str) -> CommandHandler:
        async def handler(channel, args):
            if not args:
                return await channel.send_text(f"用法: /{command_word} <玩家名>")
            info = await players.lookup_uuid(args)
            if not info:
                return await channel.send_text(
                    f"未找到玩家 {args}:\n可能是非正版账号(离线服玩家)或昵称不存在")
            await _render_and_send(channel, info, kind, label_cn)
        return handler

    dispatcher.register(Command(
        name="skin", handler=make_render_cmd("body", "皮肤", "skin"),
        usage="<player>", description="皮肤全身预览图",
    ))
    dispatcher.register(Command(
        name="head", handler=make_render_cmd("head", "头像", "head"),
        usage="<player>", description="3D 头像",
    ))

    # ---- /cape ----------------------------------------------------------
    async def cape_cmd(channel, args):
        if not args:
            return await channel.send_text("用法: /cape <玩家名>")
        info = await players.lookup_uuid(args)
        if not info:
            return await channel.send_text(
                f"未找到玩家 {args}:\n可能是非正版账号(离线服玩家)或昵称不存在")

        profile = await players.profile(info["uuid"])
        cape_url = profile.get("cape_url")
        skin_url = profile.get("skin_url")
        display_name = profile.get("name") or info["name"]

        if cape_url and skin_url:
            try:
                png = await renderer.render_back_with_cape(
                    info["uuid"], skin_url, cape_url)
            except Exception as error:
                _logger.warning("披风渲染 %s 失败: %r", display_name, error)
                return await channel.send_text(f"渲染 {display_name} 的披风失败, 请稍后再试")
            url = await uploader.upload_png(png)
            if not url:
                return await channel.send_text("图片托管暂不可用, 请稍后再试")
            await channel.send_text(f"{display_name} 的 Mojang 原版披风(背面视角):")
            await channel.send_image(url)
            return

        # 仅支持 Mojang 原版披风；无原版披风则直接提示（不查询第三方披风）
        await channel.send_text(f"{display_name} 没有 Mojang 原版披风")

    dispatcher.register(Command(
        name="cape", handler=cape_cmd,
        usage="<player>", description="查看披风",
    ))

    # ---- /profile -------------------------------------------------------
    async def profile_cmd(channel, args):
        if not args:
            return await channel.send_text("用法: /profile <玩家名>")
        info = await players.lookup_uuid(args)
        if not info:
            return await channel.send_text(
                f"未找到玩家 {args}:\nMojang 账号不存在(离线服玩家也无法通过名字查询)")
        profile = await players.profile(info["uuid"])
        model = "Alex(细手臂)" if profile["model"] == "slim" else "Steve(粗手臂)"
        await channel.send_text("\n".join([
            f"玩家: {profile.get('name') or info['name']}",
            f"UUID: {info['uuid']}",
            "账号: 正版 Java 账号",
            f"皮肤模型: {model}",
            f"Mojang 原版披风: {'有' if profile.get('cape_url') else '无'}",
        ]))

    dispatcher.register(Command(
        name="profile", handler=profile_cmd,
        aliases=("uuid",),
        usage="<player>", description="UUID/皮肤模型等档案",
    ))

    # ---- /ping ----------------------------------------------------------
    async def ping_cmd(channel, args):
        address = _resolve_address(args)
        if not address:
            return await channel.send_text("用法: /ping <address>\n(未配置默认服务器)")
        probe = ServerProbe(address, timeout=mc_timeout)
        try:
            latency = (await asyncio.to_thread(probe.ping))["latency"]
            await channel.send_text(f"[在线] {address} 延迟: {latency}ms")
        except Exception as error:
            await channel.send_text(f"[离线] {address} 无法连接: {error}")

    dispatcher.register(Command(
        name="ping", handler=ping_cmd,
        usage="[address]", description="测服务器延迟",
    ))

    # ---- /list ----------------------------------------------------------
    async def list_cmd(channel, args):
        address = _resolve_address(args)
        if not address:
            return await channel.send_text("用法: /list <address>\n(未配置默认服务器)")
        probe = ServerProbe(address, timeout=mc_timeout)
        try:
            query = await asyncio.to_thread(probe.query)
        except Exception as error:
            return await channel.send_text(
                f"[{address}] 无法获取玩家名单: {error}\n(需服务器开启 enable-query)")
        online_players = query.get("players") or []
        head = f"[{address}] 在线 {query.get('players_online')}/{query.get('players_max')}:"
        content = head + ("\n" + ", ".join(online_players) if online_players else "\n(无人在线)")
        await channel.send_text(content)

    dispatcher.register(Command(
        name="list", handler=list_cmd,
        usage="[address]", description="在线玩家名单",
    ))

    # ---- /help -----------------------------------------------------------
    dispatcher.register(Command(
        name="help",
        handler=_static_handler(dispatcher.help_text()),
        description="本菜单",
    ))

    return dispatcher