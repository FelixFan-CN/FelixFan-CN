"""把明日方舟玩家详情整理成渲染层需要的扁平结构，并生成名片用到的统计项。"""

import time

# 森空岛返回的干员星级是 0 起始索引：0 = 一星 … 5 = 六星
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
    building = payload.get("building") or {}
    routine = payload.get("routine") or {}
    campaign = payload.get("campaign") or {}

    six_star = 0
    elite_two = 0
    for char in chars:
        if not isinstance(char, dict):
            continue
        if char.get("rarity") == SIX_STAR_INDEX:
            six_star += 1
        if (char.get("evolvePhase") or 0) >= 2:
            elite_two += 1

    ap = status.get("ap") or {}
    daily = routine.get("daily") or {}
    weekly = routine.get("weekly") or {}

    return {
        "nickname": _pick(status, "name", default="博士"),
        "level": _pick(status, "level", default=""),
        "uid": _pick(status, "uid", default=""),
        "register_days": _days_since(status.get("registerTs")),
        "main_stage": _pick(status, "mainStageProgress", default=""),
        "ap": _pick(ap, "current", default=None),
        "operator_count": len(chars),
        "six_star_count": six_star,
        "elite_two_count": elite_two,
        "furniture": _pick(building, "furniture", default=None),
        "daily_done": daily.get("current") if isinstance(daily, dict) else None,
        "weekly_done": weekly.get("current") if isinstance(weekly, dict) else None,
        "campaign": campaign.get("reward") if isinstance(campaign, dict) else None,
    }