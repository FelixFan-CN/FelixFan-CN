"""把明日方舟玩家详情整理成渲染层需要的扁平结构，并生成名片用到的统计项。"""

import time

# 森空岛 charInfoMap 里 rarity 为 0 起始索引：0 = 一星 … 5 = 六星
SIX_STAR_INDEX = 5


def _pick(mapping, *keys, default=None):
    for key in keys:
        value = mapping.get(key) if isinstance(mapping, dict) else None
        if value not in (None, "", [], {}):
            return value
    return default


def _days_since(timestamp):
    if not timestamp:
        return None
    return max(0, int((time.time() - int(timestamp)) // 86400))


def summarize(payload):
    status = payload.get("status") or {}
    chars = payload.get("chars") or []
    # chars 里每条只带养成立项，星级/职业等静态信息在 charInfoMap 中
    char_info = payload.get("charInfoMap") or {}
    routine = payload.get("routine") or {}

    six_star = 0
    elite_two = 0
    for char in chars:
        if not isinstance(char, dict):
            continue
        info = char_info.get(char.get("charId")) or {}
        if info.get("rarity") == SIX_STAR_INDEX:
            six_star += 1
        if (char.get("evolvePhase") or 0) >= 2:
            elite_two += 1

    ap = status.get("ap") or {}
    daily = routine.get("daily") or {}
    weekly = routine.get("weekly") or {}

    ap_current = ap.get("current")
    ap_max = ap.get("max")
    if ap_current is not None and ap_max is not None:
        ap_text = f"{ap_current} / {ap_max}"
    else:
        ap_text = None

    return {
        "nickname": _pick(status, "name", default="博士"),
        "level": _pick(status, "level", default=""),
        "uid": _pick(status, "uid", default=""),
        "register_days": _days_since(status.get("registerTs")),
        "main_stage": _pick(status, "mainStageProgress", default=""),
        "ap": ap_text,
        "ap_current": ap_current,
        "ap_max": ap_max,
        "operator_count": len(chars) or status.get("charCnt"),
        "six_star_count": six_star or None,
        "elite_two_count": elite_two or None,
        "skin_count": _pick(status, "skinCnt", default=None),
        "daily": _routine_text(daily),
        "weekly": _routine_text(weekly),
    }


def _routine_text(routine):
    """把 {current,total} 组装成 "已完成 / 总数" 文本。"""
    if not isinstance(routine, dict):
        return None
    current = routine.get("current")
    total = routine.get("total")
    if current is None or not total:
        return None
    return f"{current} / {total}"