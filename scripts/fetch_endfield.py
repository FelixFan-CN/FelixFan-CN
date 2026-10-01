"""终末地玩家数据：走 Enka.Network 公开接口。

Enka 只需 UID，不需要森空岛登录凭证，因此终末地这条路没有凭证过期问题。
代价是只能拿到玩家在游戏内「展示柜」中公开的角色，而非完整名册。
"""

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


def summarize(payload):
    """把 Enka 原始响应整理成渲染层需要的扁平结构。"""
    player = payload.get("playerInfo") or payload.get("player") or {}

    showcase = (
        payload.get("avatarInfoList")
        or payload.get("showcase")
        or payload.get("chars")
        or []
    )

    characters = []
    for entry in showcase:
        if not isinstance(entry, dict):
            continue
        characters.append(
            {
                "name": _pick(entry, "name", "nickname", "charName", default="未知"),
                "level": _pick(entry, "level", "lv", default=""),
                "rarity": _pick(entry, "rarity", "star", "quality", default=""),
                "profession": _pick(entry, "profession", "job", "class", default=""),
            }
        )

    return {
        "nickname": _pick(player, "nickname", "name", default="开拓者"),
        "level": _pick(player, "level", "lv", default=""),
        "signature": _pick(player, "signature", "sign", default=""),
        "world_level": _pick(player, "worldLevel", "world_level", default=""),
        "achievement": _pick(player, "achievement", "achievements", default=""),
        "uid": _pick(player, "uid", default=""),
        "characters": characters,
        "character_count": len(characters),
    }