"""Pillow 名片渲染。

输出为深色卡片 PNG，配色对齐 GitHub Dark 主题，
以便和主页上的 3D 贡献图、Stats 卡片在视觉上是一整套。
"""

import os

from PIL import Image, ImageDraw, ImageFont

# ---------- 配色（GitHub Dark） ----------
BG = (13, 17, 23)
PANEL = (22, 27, 34)
BORDER = (48, 54, 61)
FG = (230, 237, 243)
MUTED = (139, 148, 158)
ACCENT_ARK = (57, 211, 83)  # 明日方舟：GitHub 绿
ACCENT_EF = (88, 166, 255)  # 终末地：GitHub 蓝

# ---------- 布局 ----------
CARD_W = 880
PAD = 32
TILE_H = 96
TILE_GAP = 14
TILE_COLUMNS = 4
TITLE_H = 34
CHIP_H = 40

# 字体候选：优先用 workflow 下载的思源黑体，其次回退到系统字体（便于本机调试）
FONT_PATHS = [
    ("fonts/NotoSansSC-Bold.otf", "fonts/NotoSansSC-Regular.otf"),
    (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
]


def _load_font(size, bold=False):
    for bold_path, regular_path in FONT_PATHS:
        path = bold_path if bold else regular_path
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    raise RuntimeError(
        "找不到可用的中文字体。请在 fonts/ 目录放置 NotoSansSC-Bold.otf "
        "（workflow 会自动下载），或在本机安装思源黑体 / 微软雅黑。"
    )


def _format(value, suffix=""):
    if value is None:
        return None
    return f"{value}{suffix}"


def _build_tiles(raw_tiles):
    """过滤掉取不到值的项，避免卡片上出现空白格子。"""
    tiles = []
    for label, value in raw_tiles:
        if value is None or value == "":
            continue
        tiles.append((label, str(value)))
    return tiles


def render_card(out_path, badge, nickname, subtitle, raw_tiles,
                chips=None, chips_title=None, accent=ACCENT_ARK):
    tiles = _build_tiles(raw_tiles)
    chips = [c for c in (chips or []) if c]

    font_badge = _load_font(20, bold=True)
    font_name = _load_font(34, bold=True)
    font_sub = _load_font(17)
    font_label = _load_font(15)
    font_value = _load_font(26, bold=True)
    font_chip = _load_font(17)
    font_section = _load_font(18, bold=True)

    tile_rows = (len(tiles) + TILE_COLUMNS - 1) // TILE_COLUMNS if tiles else 0

    # 先量出 chip 的排布（需要按宽度换行），据此决定卡片高度
    chip_rows = []
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    inner_w = CARD_W - PAD * 2
    current_row, current_w = [], 0
    for chip in chips:
        chip_w = int(probe.textlength(chip, font=font_chip)) + 32
        needed = chip_w if not current_row else current_w + 10 + chip_w
        if current_row and needed > inner_w:
            chip_rows.append(current_row)
            current_row, current_w = [chip], chip_w
        else:
            current_row.append(chip)
            current_w = needed
    if current_row:
        chip_rows.append(current_row)

    height = PAD
    height += 46                       # 徽标行
    height += 14 + 44                  # 昵称
    height += 8 + 24                   # 副标题
    if tile_rows:
        height += 22 + tile_rows * TILE_H + (tile_rows - 1) * TILE_GAP
    if chip_rows:
        height += 22
        if chips_title:
            height += TITLE_H
        height += len(chip_rows) * CHIP_H + (len(chip_rows) - 1) * 10
    height += PAD

    image = Image.new("RGB", (CARD_W, height), BG)
    draw = ImageDraw.Draw(image)

    # 左侧强调色竖条
    draw.rounded_rectangle([0, 0, 6, height], radius=3, fill=accent)

    y = PAD

    # 游戏徽标（用强调色描边的胶囊）
    badge_w = int(draw.textlength(badge, font=font_badge)) + 34
    draw.rounded_rectangle(
        [PAD, y, PAD + badge_w, y + 36], radius=18,
        fill=PANEL, outline=accent, width=2,
    )
    draw.text((PAD + 17, y + 18), badge, font=font_badge, fill=accent, anchor="lm")
    y += 46 + 14

    # 昵称
    draw.text((PAD, y), nickname or "未知", font=font_name, fill=FG, anchor="la")
    y += 44 + 8

    # 副标题
    if subtitle:
        draw.text((PAD, y), subtitle, font=font_sub, fill=MUTED, anchor="la")
    y += 24

    # 数据方块
    if tile_rows:
        y += 22
        tile_w = (inner_w - (TILE_COLUMNS - 1) * TILE_GAP) // TILE_COLUMNS
        for index, (label, value) in enumerate(tiles):
            row, col = divmod(index, TILE_COLUMNS)
            x = PAD + col * (tile_w + TILE_GAP)
            ty = y + row * (TILE_H + TILE_GAP)
            draw.rounded_rectangle(
                [x, ty, x + tile_w, ty + TILE_H], radius=12,
                fill=PANEL, outline=BORDER, width=1,
            )
            draw.text((x + 16, ty + 20), label, font=font_label, fill=MUTED, anchor="la")
            draw.text((x + 16, ty + 46), value, font=font_value, fill=FG, anchor="la")
        y += tile_rows * TILE_H + (tile_rows - 1) * TILE_GAP

    # 角色列表
    if chip_rows:
        y += 22
        if chips_title:
            draw.text((PAD, y), chips_title, font=font_section, fill=accent, anchor="la")
            y += TITLE_H
        for row in chip_rows:
            x = PAD
            for chip in row:
                chip_w = int(draw.textlength(chip, font=font_chip)) + 32
                draw.rounded_rectangle(
                    [x, y, x + chip_w, y + CHIP_H - 8], radius=16,
                    fill=PANEL, outline=BORDER, width=1,
                )
                draw.text(
                    (x + 16, y + (CHIP_H - 8) // 2), chip,
                    font=font_chip, fill=FG, anchor="lm",
                )
                x += chip_w + 10
            y += CHIP_H

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    image.save(out_path, "PNG")
    return out_path


def render_arknights(summary, out_path):
    """明日方舟名片。"""
    register_days = summary.get("register_days")
    return render_card(
        out_path=out_path,
        badge="明日方舟",
        nickname=summary.get("nickname"),
        subtitle=f"UID {summary['uid']}" if summary.get("uid") else "",
        accent=ACCENT_ARK,
        raw_tiles=[
            ("等级", _format(summary.get("level"))),
            ("入职天数", _format(register_days, " 天")),
            ("干员总数", _format(summary.get("operator_count"))),
            ("六星干员", _format(summary.get("six_star_count"))),
            ("精英二", _format(summary.get("elite_two_count"))),
            ("主线进度", _format(summary.get("main_stage"))),
            ("当前理智", _format(summary.get("ap"))),
            ("皮肤保有", _format(summary.get("skin_count"))),
        ],
    )


def render_endfield(summary, out_path):
    """终末地名片。"""
    return render_card(
        out_path=out_path,
        badge="明日方舟：终末地",
        nickname=summary.get("nickname"),
        subtitle=summary.get("signature") or (
            f"UID {summary['uid']}" if summary.get("uid") else ""
        ),
        accent=ACCENT_EF,
        raw_tiles=[
            ("等级", _format(summary.get("level"))),
            ("世界等级", _format(summary.get("world_level"))),
            ("干员总数", _format(summary.get("character_count"))),
            ("武器总数", _format(summary.get("weapon_count"))),
            ("档案总数", _format(summary.get("doc_count"))),
            ("展示角色", _format(summary.get("showcase_count"))),
        ],
    )