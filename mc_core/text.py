# -*- coding: utf-8 -*-
"""Minecraft 文本处理：清理颜色代码、解析 MOTD。"""
import re

COLOR_CODE = re.compile(r"§.")


def strip_color(text: str) -> str:
    """去掉 Minecraft 按钮/格式代码（§a 之类）。"""
    return COLOR_CODE.sub("", text)


def motd_to_text(description) -> str:
    """把 status/query 返回的 description（str 或嵌套 dict）转为纯文本。"""
    if isinstance(description, str):
        return strip_color(description)
    if isinstance(description, dict):
        parts = [description.get("text") or ""]
        for extra in description.get("extra") or []:
            parts.append(motd_to_text(extra))
        return strip_color("".join(parts))
    return strip_color(str(description))


__all__ = ["strip_color", "motd_to_text"]