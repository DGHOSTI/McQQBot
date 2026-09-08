# -*- coding: utf-8 -*-
"""Minecraft 服务器检测命令行工具。

用法：
    python -m mc_core.cli <服务器地址[:端口]> [--query] [--ping] [--json] [--timeout N]
"""
import argparse
import json
import sys

from .formatter import format_status_text
from .server import ServerProbe

__all__ = ["main", "build_parser"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Minecraft Java 服务器状态检测 (支持 SRV 解析)",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("address", help="服务器地址，可带端口 如 host 或 host:25566")
    parser.add_argument("--query", action="store_true", help="附带全量玩家列表查询")
    parser.add_argument("--ping", action="store_true", help="只测延迟")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--timeout", type=int, default=10, help="超时秒数 (默认10)")
    return parser


def main(argv=None) -> int:
    # 中文 Windows(GBK) 下输出零宽/emoji/特殊字符可能报 UnicodeEncodeError，
    # 这里兜底：无法编码的字符替换为 ? 而不是崩溃
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass

    args = build_parser().parse_args(argv)
    probe = ServerProbe(args.address, timeout=args.timeout)
    try:
        if args.ping:
            result = {"address": args.address, "online": True, **probe.ping()}
        else:
            result = probe.check(with_query=args.query)
    except ConnectionError as error:
        result = {"address": args.address, "online": False, "error": str(error)}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1
        print(f"[离线] 连接失败: {error}")
        return 1
    except Exception as error:
        result = {"address": args.address, "online": False, "error": str(error)}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 2
        print(f"[失败] 检测失败: {error}")
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(format_status_text(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())