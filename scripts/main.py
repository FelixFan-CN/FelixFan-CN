"""名片生成入口。

逐款游戏独立执行，任一失败都不影响另一款：
明日方舟走森空岛链路（需要 SKLAND_TOKEN），终末地走 Enka（只需要 UID）。
"""

import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch_arknights as ark_summary
import fetch_endfield as endfield_api
import render
from skland_api import SklandError
from skland_api import fetch_arknights as fetch_arknights_raw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(ROOT, "assets")


def _load_config():
    with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as fp:
        return json.load(fp)


def _resolve(section, env_key):
    """UID 允许用环境变量覆盖，方便不改配置文件就切换账号。"""
    return os.environ.get(env_key) or section.get("uid") or ""


def generate_arknights(section, token):
    uid = _resolve(section, "ARKNIGHTS_UID")
    if not token:
        print("[明日方舟] 跳过：未配置 SKLAND_TOKEN")
        return None
    payload = fetch_arknights_raw(token, uid or None)
    summary = ark_summary.summarize(payload)
    print(f"[明日方舟] 拉到数据：{summary['nickname']}，干员 {summary['operator_count']} 名")
    return render.render_arknights(
        summary, os.path.join(ASSETS_DIR, "arknights-card.png")
    )


def generate_endfield(section):
    uid = _resolve(section, "ENDFIELD_UID")
    if not uid:
        print("[终末地] 跳过：未配置 UID")
        return None
    payload = endfield_api.fetch_endfield(uid)
    summary = endfield_api.summarize(payload)
    print(f"[终末地] 拉到数据：{summary['nickname']}，干员 {summary['character_count']} 名")
    return render.render_endfield(
        summary, os.path.join(ASSETS_DIR, "endfield-card.png")
    )


def main():
    config = _load_config()
    token = os.environ.get("SKLAND_TOKEN", "").strip()
    produced, failed = [], []

    jobs = [
        ("arknights", lambda: generate_arknights(config["arknights"], token)),
        ("endfield", lambda: generate_endfield(config["endfield"])),
    ]

    for name, job in jobs:
        if not config.get(name, {}).get("enabled", True):
            print(f"[{name}] 已在配置中禁用")
            continue
        try:
            result = job()
            if result:
                produced.append(result)
        except (SklandError, endfield_api.EnkaError) as error:
            failed.append((name, str(error)))
            print(f"[{name}] 失败：{error}")
        except Exception:  # noqa: BLE001 - 保证单款失败不拖垮整体
            failed.append((name, "未知异常"))
            traceback.print_exc()

    print(f"\n完成：生成 {len(produced)} 张，失败 {len(failed)} 张")
    for path in produced:
        print(f"  - {os.path.relpath(path, ROOT)}")

    if failed and not produced:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())