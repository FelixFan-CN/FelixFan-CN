"""森空岛（Skland）API 客户端。

负责：鹰角通行证 token -> grant code -> cred 的认证链路，
以及带 sign 签名的接口请求。

注意：森空岛接口为非官方接口，鹰角可能随时调整签名方式或字段。
所有可变点集中在文件顶部常量，便于失效后快速修正。
"""

import hashlib
import hmac
import json
import time
import urllib.parse

import requests

# ---------- 可变常量（接口变更时优先检查这里） ----------

AS_HOST = "https://as.hypergryph.com"
ZONAI_HOST = "https://zonai.skland.com"

# 明日方舟在鹰角通行证体系中的固定 appCode
APP_CODE_ARKNIGHTS = "4ca99fa6b56cc2ba"

# 请求头里用于签名的固定字段
PLATFORM = "1"
VNAME = "1.21.0"
USER_AGENT = (
    "Skland/1.21.0 (com.hypergryph.skland; build:1001210; Android 12; ) OkHttp/4.9.3"
)

# 签名时间戳刻意回拨 2 秒，规避客户端与服务端的时钟偏差
SIGN_TIME_OFFSET = 2

TIMEOUT = 20


class SklandError(RuntimeError):
    """森空岛接口调用失败。"""


def _unwrap(payload, context):
    """兼容两种响应外壳：as 域的 status，zonai 域的 code。"""
    code = payload.get("code", payload.get("status"))
    if code != 0:
        raise SklandError(f"{context} 失败：{payload}")
    return payload.get("data") or {}


def _build_signed_headers(sign_token, path, body_or_query, cred=None):
    """构造带 sign 的请求头。

    签名算法（V1，明日方舟使用）：
        sign = md5(hmac_sha256(sign_token, path + body_or_query + timestamp + header_json))
    其中 header_json 是 {"platform","timestamp","dId","vName"} 的紧凑 JSON。
    """
    timestamp = str(int(time.time()) - SIGN_TIME_OFFSET)
    sign_fields = {
        "platform": PLATFORM,
        "timestamp": timestamp,
        "dId": "",
        "vName": VNAME,
    }
    header_json = json.dumps(sign_fields, separators=(",", ":"))
    payload = path + body_or_query + timestamp + header_json
    digest = hmac.new(
        sign_token.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()

    headers = dict(sign_fields)
    headers["sign"] = hashlib.md5(digest.encode()).hexdigest()
    headers["User-Agent"] = USER_AGENT
    if cred:
        headers["cred"] = cred
    return headers


def get_grant_code(hg_token):
    """用鹰角通行证 token 换取一次性 grant code。"""
    resp = requests.post(
        f"{AS_HOST}/user/oauth2/v2/grant",
        json={"appCode": APP_CODE_ARKNIGHTS, "token": hg_token, "type": 0},
        timeout=TIMEOUT,
    )
    return _unwrap(resp.json(), "获取 grant code")["code"]


def get_cred(grant_code):
    """用 grant code 换取 cred；同时返回后续签名用的 sign token。"""
    resp = requests.post(
        f"{ZONAI_HOST}/web/v1/user/auth/generate_cred_by_code",
        json={"code": grant_code, "kind": 1},
        timeout=TIMEOUT,
    )
    data = _unwrap(resp.json(), "换取 cred")
    return data["cred"], data["token"]


def api_get(path, query, cred, sign_token):
    """发起一个带签名的 GET 请求。"""
    query_string = "?" + urllib.parse.urlencode(query) if query else ""
    headers = _build_signed_headers(sign_token, path, query_string, cred=cred)
    resp = requests.get(
        f"{ZONAI_HOST}{path}{query_string}", headers=headers, timeout=TIMEOUT
    )
    return _unwrap(resp.json(), f"GET {path}")


def get_bindings(cred, sign_token):
    """获取账号下已绑定的游戏角色列表。"""
    return api_get("/api/v1/game/player/binding", {}, cred, sign_token)


def get_arknights_player_info(cred, sign_token, uid):
    """获取明日方舟玩家详情（含 status / chars / building / campaign 等）。"""
    return api_get("/api/v1/game/player/info", {"uid": uid}, cred, sign_token)


def resolve_arknights_uid(bindings, preferred_uid=None):
    """从绑定列表中取出明日方舟的 uid。

    传入 preferred_uid 时优先校验它是否在绑定列表内，避免拉错账号。
    """
    for item in bindings.get("list", []):
        if item.get("appCode") != APP_CODE_ARKNIGHTS:
            continue
        entries = item.get("bindingList") or []
        if preferred_uid:
            for entry in entries:
                if str(entry.get("uid")) == str(preferred_uid):
                    return str(entry["uid"])
        if entries:
            default = next(
                (e for e in entries if e.get("isDefault")), entries[0]
            )
            return str(default["uid"])
    return None


def fetch_arknights(hg_token, preferred_uid=None):
    """完整链路：token -> cred -> 绑定列表 -> 玩家详情。"""
    grant_code = get_grant_code(hg_token)
    cred, sign_token = get_cred(grant_code)
    bindings = get_bindings(cred, sign_token)
    uid = resolve_arknights_uid(bindings, preferred_uid)
    if not uid:
        raise SklandError("该账号下没有找到明日方舟角色，请先在森空岛绑定游戏角色")
    return get_arknights_player_info(cred, sign_token, uid)