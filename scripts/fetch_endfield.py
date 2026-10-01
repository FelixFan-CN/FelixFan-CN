"""终末地玩家数据：走 Enka.Network 公开接口。

Enka 只需 UID，不需要森空岛登录凭证，因此终末地这条路没有凭证过期问题。
UID 取游戏内 9 位账号 ID（森空岛绑定列表里的 roleId）。

响应结构（已对真实账号验证）：
    { "playerInfo": { "businessCard": { name, signature, adventureLevel,
      worldLevel, shortId, statistic: {charNum, weaponNum, docNum},
      achievement: {display: [...]}, charList: [{templateId, level}] } },
      "uid": "...", "region": "CN" }
"""

import time

import requests

ENKA_HOST = "https://enka.network"
USER_AGENT = "FelixFan-CN-ProfileCard/1.0 (+https://github.com/FelixFan-CN)"
TIMEOUT = 30


class EnkaError(RuntimeError):
    """Enka 接口调用失败。"""


def fetch_endfield(uid):
    """拉取终末地玩家展示数据。"""
    url = f"{ENKA_HOST}/api/ef/uid/{uid}/"
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)

    if resp.status_code == 429:
        raise EnkaError("Enka 限流（429），请稍后重试")
    if resp.status_code != 200:
        raise EnkaError(f"Enka 返回 {resp.status_code}：{resp.text[:200]}")

    payload = resp.json()
    if isinstance(payload, dict) and payload.get("detail"):
        raise EnkaError(f"Enka 返回错误：{payload['detail']}")
    return payload


def _pick(mapping, *keys, default=None):
    """按顺序取第一个存在且非空的键，用于兼容 Enka 的字段变动。"""
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
    """把 Enka 原始响应整理成渲染层需要的扁平结构。"""
    player = payload.get("playerInfo") or {}
    card = player.get("businessCard") or player
    statistic = card.get("statistic") or {}
    achievement = card.get("achievement") or {}
    showcase = card.get("charList") or []

    display = achievement.get("display") or []
    info_list = achievement.get("infoList") or []
    achievement_count = len(display) or len(info_list)

    return {
        "nickname": _pick(card, "name", "nickname", default="管理员"),
        "level": _pick(card, "adventureLevel", "level", default=""),
        "world_level": _pick(card, "worldLevel", default=""),
        "signature": _pick(card, "signature", default=""),
        "short_id": _pick(card, "shortId", default=""),
        "uid": _pick(card, "platformRoleId", default=_pick(payload, "uid", default="")),
        "play_days": _days_since(card.get("createTime")),
        "character_count": _pick(statistic, "charNum", default=None),
        "weapon_count": _pick(statistic, "weaponNum", default=None),
        "doc_count": _pick(statistic, "docNum", default=None),
        "achievement": achievement_count or None,
        "showcase_count": len(showcase) or None,
    }