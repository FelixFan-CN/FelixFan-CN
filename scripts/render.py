"""Pillow 名片渲染。

输出为深色圆角卡片 PNG（四角透明），配色对齐 GitHub Dark 主题，
以便和主页上的 3D 贡献图、Stats 卡片在视觉上是一整套。

设计要点：
  - 顶部用强调色做一层柔和光晕渐变，避免整块死黑
  - 左侧头像圈取昵称首字，形成视觉落点
  - 数据格只保留「标签 + 大号数值 + 强调色下划线」，减少表格感
  - 所有形状层按 4 倍超采样绘制后缩放，保证圆角与圆形的边缘平滑
"""

import os

from PIL import Image, ImageDraw, ImageFont

# ---------- 配色（GitHub Dark） ----------
BG = (13, 17, 23)
PANEL = (24, 30, 39)
PANEL_BORDER = (40, 47, 57)
FG = (230, 237, 243)
MUTED = (139, 148, 158)
ACCENT_ARK = (57, 211, 83)  # 明日方舟：GitHub 绿
ACCENT_EF = (88, 166, 255)  # 终末地：GitHub 蓝

# ---------- 布局 ----------
CARD_W = 880
RADIUS = 20
PAD = 36
AVATAR = 76
TILE_H = 92
TILE_GAP = 14
TILE_COLUMNS = 4
GLOW_H = 170          # 顶部光晕高度
GAP_AFTER_HEADER = 28
GAP_BEFORE_FOOTER = 24

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


def _blend(color_a, color_b, ratio):
    """按 ratio 把 color_a 混向 color_b（0 = 全 a，1 = 全 b）。"""
    return tuple(
        int(round(a + (b - a) * ratio)) for a, b in zip(color_a, color_b)
    )


def _rounded_layer(size, radius, fill=None, outline=None, width=1, ss=4):
    """在高分辨率下画圆角形状再缩小，得到平滑边缘。"""
    w, h = size
    layer = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(
        [0, 0, w * ss - 1, h * ss - 1],
        radius=radius * ss,
        fill=fill,
        outline=outline,
        width=width * ss,
    )
    return layer.resize((w, h), Image.LANCZOS)


def _ellipse_layer(size, fill=None, outline=None, width=1, ss=4):
    w, h = size
    layer = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse(
        [0, 0, w * ss - 1, h * ss - 1],
        fill=fill,
        outline=outline,
        width=width * ss,
    )
    return layer.resize((w, h), Image.LANCZOS)


def _background(width, height, accent):
    """纵向渐变：顶部带强调色光晕，向下迅速沉回底色。"""
    glow = _blend(BG, accent, 0.16)
    column = Image.new("RGB", (1, height))
    for y in range(height):
        if y < GLOW_H:
            # 用幂次让光晕衰减更快，形成「发光」而非「渐层」
            ratio = (y / GLOW_H) ** 1.7
            column.putpixel((0, y), _blend(glow, BG, ratio))
        else:
            column.putpixel((0, y), BG)
    return column.resize((width, height), Image.BILINEAR).convert("RGBA")


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


def _fit_font(text, max_width, draw, sizes, bold=True):
    """数值过长时自动降字号，避免溢出格子。"""
    for size in sizes:
        font = _load_font(size, bold=bold)
        if draw.textlength(text, font=font) <= max_width:
            return font
    return _load_font(sizes[-1], bold=bold)


def render_card(out_path, badge, nickname, subtitle, raw_tiles,
                accent=ACCENT_ARK, footer=None):
    """绘制一张名片。

    badge    左上/右上角的游戏标识胶囊
    nickname 昵称（左侧头像圈取它的首字）
    subtitle 昵称下方的次要说明
    raw_tiles [(标签, 数值)]，数值为 None 的格子会被自动跳过
    footer   底部来源说明
    """
    tiles = _build_tiles(raw_tiles)
    inner_w = CARD_W - PAD * 2
    tile_rows = (len(tiles) + TILE_COLUMNS - 1) // TILE_COLUMNS if tiles else 0

    font_name = _load_font(36, bold=True)
    font_sub = _load_font(17)
    font_badge = _load_font(17, bold=True)
    font_label = _load_font(14)
    font_footer = _load_font(14)
    font_avatar = _load_font(36, bold=True)

    # ---- 先算总高度 ----
    height = PAD + AVATAR
    if tile_rows:
        height += GAP_AFTER_HEADER
        height += tile_rows * TILE_H + (tile_rows - 1) * TILE_GAP
    if footer:
        height += GAP_BEFORE_FOOTER + 18
    height += PAD

    # ---- 底：渐变 + 圆角 + 描边 ----
    image = _background(CARD_W, height, accent)
    mask = _rounded_layer((CARD_W, height), RADIUS, fill=(255, 255, 255, 255))
    image.putalpha(mask.getchannel("A"))
    image.alpha_composite(
        _rounded_layer(
            (CARD_W, height), RADIUS,
            outline=_blend(PANEL_BORDER, accent, 0.18), width=1,
        )
    )

    draw = ImageDraw.Draw(image)

    # ---- 头部：头像圈 + 昵称 + 副标题 ----
    ax, ay = PAD, PAD
    avatar = _ellipse_layer(
        (AVATAR, AVATAR),
        fill=_blend(BG, accent, 0.20),
        outline=_blend(accent, BG, 0.15),
        width=2,
    )
    avatar_draw = ImageDraw.Draw(avatar)
    avatar_draw.text(
        (AVATAR / 2, AVATAR / 2 + 1), (nickname or "?")[:1],
        font=font_avatar, fill=accent, anchor="mm",
    )
    image.alpha_composite(avatar, (ax, ay))

    text_x = ax + AVATAR + 18
    draw.text((text_x, ay + 4), nickname or "未知", font=font_name, fill=FG, anchor="la")
    if subtitle:
        draw.text((text_x, ay + 52), subtitle, font=font_sub, fill=MUTED, anchor="la")

    # ---- 右上角：游戏标识胶囊 ----
    badge_w = int(draw.textlength(badge, font=font_badge)) + 32
    badge_h = 32
    badge_x = CARD_W - PAD - badge_w
    badge_y = ay + 24
    image.alpha_composite(
        _rounded_layer(
            (badge_w, badge_h), badge_h // 2,
            fill=_blend(BG, accent, 0.14),
            outline=_blend(accent, BG, 0.25),
            width=1,
        ),
        (badge_x, badge_y),
    )
    draw.text(
        (badge_x + badge_w / 2, badge_y + badge_h / 2 + 1), badge,
        font=font_badge, fill=accent, anchor="mm",
    )

    # ---- 数据格 ----
    y = PAD + AVATAR
    if tile_rows:
        y += GAP_AFTER_HEADER
        tile_w = (inner_w - (TILE_COLUMNS - 1) * TILE_GAP) // TILE_COLUMNS
        for index, (label, value) in enumerate(tiles):
            row, col = divmod(index, TILE_COLUMNS)
            x = PAD + col * (tile_w + TILE_GAP)
            ty = y + row * (TILE_H + TILE_GAP)

            image.alpha_composite(
                _rounded_layer(
                    (tile_w, TILE_H), 14,
                    fill=PANEL,
                    outline=_blend(PANEL_BORDER, accent, 0.10),
                    width=1,
                ),
                (x, ty),
            )
            draw.text((x + 18, ty + 17), label, font=font_label, fill=MUTED, anchor="la")

            value_font = _fit_font(value, tile_w - 36, draw, [27, 24, 21, 18, 16])
            draw.text((x + 18, ty + 42), value, font=value_font, fill=FG, anchor="la")

            # 强调色下划线，弱化「表格」观感
            image.alpha_composite(
                _rounded_layer((26, 3), 2, fill=_blend(accent, BG, 0.10)),
                (x + 18, ty + TILE_H - 17),
            )
        y += tile_rows * TILE_H + (tile_rows - 1) * TILE_GAP

    # ---- 底部来源 ----
    if footer:
        y += GAP_BEFORE_FOOTER
        image.alpha_composite(
            _ellipse_layer((6, 6), fill=_blend(accent, BG, 0.35)), (PAD, y + 6)
        )
        draw.text((PAD + 14, y), footer, font=font_footer, fill=MUTED, anchor="la")

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    image.save(out_path, "PNG")
    return out_path


def render_arknights(summary, out_path):
    """明日方舟名片。"""
    return render_card(
        out_path=out_path,
        badge="明日方舟",
        nickname=summary.get("nickname"),
        subtitle=f"UID {summary['uid']}" if summary.get("uid") else "",
        accent=ACCENT_ARK,
        footer="数据来自森空岛 · 每日自动更新",
        raw_tiles=[
            ("等级", _format(summary.get("level"))),
            ("入职天数", _format(summary.get("register_days"), " 天")),
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
        footer="数据来自 Enka.Network · 每日自动更新",
        raw_tiles=[
            ("等级", _format(summary.get("level"))),
            ("世界等级", _format(summary.get("world_level"))),
            ("创建天数", _format(summary.get("play_days"), " 天")),
            ("干员总数", _format(summary.get("character_count"))),
            ("武器总数", _format(summary.get("weapon_count"))),
            ("档案总数", _format(summary.get("doc_count"))),
            ("展示角色", _format(summary.get("showcase_count"))),
            ("短 ID", _format(summary.get("short_id"))),
        ],
    )