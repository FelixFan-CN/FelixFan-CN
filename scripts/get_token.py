"""一次性获取鹰角通行证 token。

token 是长期凭证，拿到后填进 GitHub 仓库的 Secret（SKLAND_TOKEN）即可，
之后 workflow 每次运行都会用它自动换取短期的 cred，无需再人工介入。

用法：
    python scripts/get_token.py password   # 手机号 + 密码
    python scripts/get_token.py code       # 手机号 + 短信验证码

注意：token 等同于账号登录态，请勿提交到仓库或发给他人。
脚本只会把结果打印出来，并可选写入本地 token.txt（已在 .gitignore 中忽略）。
"""

import getpass
import json
import sys

import requests

AS_HOST = "https://as.hypergryph.com"
TIMEOUT = 20


def _post(path, payload, context):
    resp = requests.post(f"{AS_HOST}{path}", json=payload, timeout=TIMEOUT)
    try:
        data = resp.json()
    except ValueError:
        raise SystemExit(f"{context} 失败：服务端返回非 JSON（HTTP {resp.status_code}）")
    if data.get("status") != 0:
        raise SystemExit(f"{context} 失败：{data}")
    return data.get("data") or {}


def by_password():
    phone = input("鹰角账号手机号：").strip()
    password = getpass.getpass("密码（输入时不回显）：")
    data = _post(
        "/user/auth/v1/token_by_phone_password",
        {"phone": phone, "password": password},
        "手机号密码登录",
    )
    return data.get("token")


def by_phone_code():
    phone = input("鹰角账号手机号：").strip()
    _post("/general/v1/send_phone_code", {"phone": phone, "type": 2}, "发送验证码")
    print("验证码已发送，请查看短信（有效期约 10 分钟）。")
    code = input("验证码：").strip()
    data = _post(
        "/user/auth/v2/token_by_phone_code",
        {"phone": phone, "code": code},
        "验证码登录",
    )
    return data.get("token")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "password"
    if mode == "password":
        token = by_password()
    elif mode == "code":
        token = by_phone_code()
    else:
        raise SystemExit(f"未知模式：{mode}（可用：password / code）")

    if not token:
        raise SystemExit("登录成功但未取到 token，接口可能已调整，请检查响应结构。")

    print("\n获取成功。token 如下：\n")
    print(token)
    print("\ntoken 已写入本地 token.txt（已忽略，不会提交）。")

    with open("token.txt", "w", encoding="utf-8") as fp:
        fp.write(token)

    print(
        "\n下一步：把它填进仓库 Secret\n"
        '  gh secret set SKLAND_TOKEN --repo FelixFan-CN/FelixFan-CN --body "<token>"'
    )


if __name__ == "__main__":
    main()