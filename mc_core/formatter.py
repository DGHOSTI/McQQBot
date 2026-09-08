# -*- coding: utf-8 -*-
"""检测结果格式化：将 status/ping/query 的结果 dict 转成人类可读文本。"""
__all__ = ["format_status_text"]


def format_status_text(result: dict) -> str:
    """格式化 ServerProbe.check()/ping() 的结果；兼容 status / ping / query。"""
    if not result.get("online"):
        return f"[离线] {result.get('error', '未知错误')}"

    # 只测延迟模式
    if "resolved" not in result:
        latency = result.get("latency", "?")
        return "[在线] 服务器在线\n地址: {}\n延迟: {}ms".format(
            result.get("address", "?"), latency
        )

    version = result.get("version", "?")
    lines = [
        "[在线] 服务器在线",
        f"地址: {result['address']} → {result['resolved']}",
        f"MOTD: {result.get('motd', '') or '(空)'}",
        f"版本: {version}",
        f"在线: {result['players_online']}/{result['players_max']}",
        f"延迟: {result['latency']}ms",
    ]

    sample = result.get("sample") or []
    if sample:
        shown = sample[:10]
        lines.append("玩家: " + ", ".join(shown) + (" ..." if len(sample) > 10 else ""))

    query = result.get("query")
    if "query" in result:
        if query:
            lines.append(f"地图: {query['map']}  服务端: {query['brand']} {query['software']}")
            players = query.get("players") or []
            lines.append(
                "在服玩家(%d): %s" % (len(players), ", ".join(players)) if players
                else "在服玩家: (无)"
            )
        else:
            lines.append(f"玩家列表不可用(query未开启): {result.get('query_error', '')}")

    return "\n".join(lines)