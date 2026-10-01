"""Pillow 名片渲染（hoyocard 风格）。

设计原则：
  - 一张游戏立绘铺满整张卡作为底图
  - 只用白色文字，不加任何色块、边框、图标
  - 左上角：昵称 + Lv.xx，下一行 UID
  - 底部：一排「大号数字 + 小标签」
  - 可读性靠的是「文字区域局部模糊 + 柔化压暗」，而不是把整张图压黑：
    在昵称区和数据行下面做一块边缘羽化的毛玻璃，底图其余部分保持清晰

底图放在 assets/ 下，命名 arknights-bg.* / endfield-bg.*（png/jpg/webp 均可）。
建议提供 3:1 的宽图；若不是 3:1，会以右侧为锚点裁切（左侧本就被处理过）。
"""

import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ---------- 画布 ----------
CARD_W = 1200
CARD_H = 400
RATIO = CARD_W / CARD_H  # 3:1

PAD = 40
NAME_Y = 30
NAME_SIZE = 40
LEVEL_SIZE = 22
UID_Y = 88
UID_SIZE = 18
STAT_NUMBER_Y = 292
STAT_NUMBER_SIZE = 42
STAT_LABEL_Y = 350
STAT_LABEL_SIZE = 16
STAT_AREA_RATIO = 0.72  # 底部一排统计只占左侧这些宽度，右侧留给立绘

WHITE = (255, 255, 255)
SHADOW_ALPHA = 150
SHADOW_OFFSET = 2

# ---------- 文字区域的局部模糊（保证白字可读） ----------
# 昵称 + UID 所在区域，以及底部数据行所在区域
# 面板刻意向画布外扩，只让朝内的边缘羽化，避免画布边角出现生硬的圆角
TEXT_PANELS = [
    (-80, -80, 720, 152),
    (-80, 250, CARD_W + 80, CARD_H + 80),
]
PANEL_FEATHER = 30      # 面板边缘羽化半径，避免出现生硬的矩形边界
TEXT_BLUR_RADIUS = 12   # 面板内的模糊强度
TEXT_SHADE = 0.52       # 面板内的压暗强度（0 不压暗，1 全黑）

# 全局只保留一层很轻的左侧渐隐，保证整体视觉不失衡
GLOBAL_FADE = [(0.0, 0.46), (0.5, 0.20), (1.0, 0.02)]

# 字体候选：优先用 workflow 下载的思源黑体，其次回退到系统字体（便于本机调试）
FONT_PATHS = [
    ("fonts/NotoSansSC-Bold.otf", "fonts/NotoSansSC-Regular.otf"),
    (r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\msyh.ttc"),
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
]

# 底图候选路径（按顺序探测，支持多种扩展名）
BACKGROUNDS = {
    "arknights": [
        "assets/arknights-bg.png",
        "assets/arknights-bg.jpg",
        "assets/arknights-bg.jpeg",
        "assets/arknights-bg.webp",
    ],
    "endfield": [
        "assets/endfield-bg.png",
        "assets/endfield-bg.jpg",
        "assets/endfield-bg.jpeg",
        "assets/endfield-bg.webp",
    ],
}


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


def _lerp_stops(stops, ratio):
    """在 [(位置比例, 值)] 之间做线性插值。"""
    if ratio <= stops[0][0]:
        return stops[0][1]
    for (p0, v0), (p1, v1) in zip(stops, stops[1:]):
        if ratio <= p1:
            span = p1 - p0
            t = 0 if span == 0 else (ratio - p0) / span
            return v0 + (v1 - v0) * t
    return stops[-1][1]


def _horizontal_fade(width, height, stops):
    """从左到右的黑色渐变遮罩，让左侧白字在任何底图上都可读。"""
    row = Image.new("RGBA", (width, 1))
    pixels = row.load()
    for x in range(width):
        alpha = int(255 * _lerp_stops(stops, x / max(1, width - 1)))
        pixels[x, 0] = (0, 0, 0, max(0, min(255, alpha)))
    return row.resize((width, height))


def _soft_mask(size, boxes, feather):
    """把若干矩形做成一张边缘羽化的遮罩，用于限定局部模糊的范围。"""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for box in boxes:
        draw.rounded_rectangle(box, radius=28, fill=255)
    return mask.filter(ImageFilter.GaussianBlur(feather))


def _cover(image, size, anchor="right"):
    """等比缩放后裁切填满目标尺寸；横向以右侧为锚，避免裁掉立绘主体。"""
    target_w, target_h = size
    src_w, src_h = image.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(src_w * scale + 0.5), int(src_h * scale + 0.5)
    resized = image.resize((new_w, new_h), Image.LANCZOS)

    if anchor == "right":
        left = new_w - target_w
    elif anchor == "left":
        left = 0
    else:
        left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))


def _find_background(candidates, root):
    for relative in candidates:
        path = os.path.join(root, relative)
        if os.path.exists(path):
            return path
    return None


def _base_canvas(bg_path):
    """底图铺底；没有底图时退化为深色渐变，保证流程不中断。"""
    if bg_path:
        with Image.open(bg_path) as source:
            canvas = _cover(source.convert("RGB"), (CARD_W, CARD_H))
        canvas = canvas.convert("RGBA")
    else:
        top = Image.new("RGBA", (1, CARD_H))
        pixels = top.load()
        for y in range(CARD_H):
            shade = 30 - int(18 * (y / max(1, CARD_H - 1)))
            pixels[0, y] = (shade, shade + 4, shade + 10, 255)
        canvas = top.resize((CARD_W, CARD_H))

    # 一层很轻的整体左侧渐隐
    canvas.alpha_composite(_horizontal_fade(CARD_W, CARD_H, GLOBAL_FADE))

    # 文字区域：局部模糊 + 柔化压暗，其余部分保持清晰
    mask = _soft_mask((CARD_W, CARD_H), TEXT_PANELS, PANEL_FEATHER)
    blurred = canvas.filter(ImageFilter.GaussianBlur(TEXT_BLUR_RADIUS))
    canvas = Image.composite(blurred, canvas, mask)

    shade = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    shade.putalpha(mask.point(lambda value: int(value * TEXT_SHADE)))
    canvas.alpha_composite(shade)
    return canvas


def _build_stats(raw_stats):
    """过滤掉取不到值的项，避免出现空占位。"""
    stats = []
    for label, value in raw_stats:
        if value is None or value == "":
            continue
        stats.append((label, str(value)))
    return stats


def render_card(out_path, game, nickname, level, uid, raw_stats):
    """绘制一张名片。

    game     用于定位底图（BACKGROUNDS 的键）
    nickname 左上角昵称
    level    跟在昵称后面的等级文本（如 "Lv.105"，可为空）
    uid      昵称下的 UID 文本
    raw_stats [(标签, 数值)]，数值为空则跳过；数值为大号白字，标签为小号白字
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bg_path = _find_background(BACKGROUNDS.get(game, []), root)
    if not bg_path:
        print(f"[{game}] 未找到底图（assets/{game}-bg.*），暂用深色渐变代替")

    stats = _build_stats(raw_stats)

    image = _base_canvas(bg_path)

    # 所有文字先画到独立图层，再整体合成，这样半透明与投影才能正确混合
    text_layer = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    font_name = _load_font(NAME_SIZE, bold=True)
    font_level = _load_font(LEVEL_SIZE, bold=True)
    font_uid = _load_font(UID_SIZE)
    font_number = _load_font(STAT_NUMBER_SIZE, bold=True)
    font_label = _load_font(STAT_LABEL_SIZE)

    def put(x, y, text, font, alpha):
        color = (*WHITE, alpha)
        shadow = (0, 0, 0, int(alpha * SHADOW_ALPHA / 255))
        draw.text((x + SHADOW_OFFSET, y + SHADOW_OFFSET), text, font=font, fill=shadow)
        draw.text((x, y), text, font=font, fill=color)

    # ---- 左上：昵称 + 等级 ----
    name = nickname or "未知"
    put(PAD, NAME_Y, name, font_name, 255)
    if level:
        name_w = draw.textlength(name, font=font_name)
        put(int(PAD + name_w + 12), NAME_Y + NAME_SIZE - LEVEL_SIZE - 2, level, font_level, 215)

    # ---- 昵称下方：UID ----
    if uid:
        put(PAD, UID_Y, uid, font_uid, 180)

    # ---- 底部：一排「大号数字 + 小标签」 ----
    if stats:
        pitch = int(CARD_W * STAT_AREA_RATIO / max(1, len(stats)))
        for index, (label, value) in enumerate(stats):
            x = PAD + index * pitch
            put(x, STAT_NUMBER_Y, value, font_number, 255)
            put(x, STAT_LABEL_Y, label, font_label, 185)

    image.alpha_composite(text_layer)

    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    image.convert("RGB").save(out_path, "PNG")
    return out_path


def render_arknights(summary, out_path):
    """明日方舟名片。"""
    uid = summary.get("uid")
    level = summary.get("level")
    return render_card(
        out_path=out_path,
        game="arknights",
        nickname=summary.get("nickname"),
        level=f"Lv.{level}" if level else "",
        uid=f"UID: {uid}" if uid else "",
        raw_stats=[
            ("入职天数", summary.get("register_days")),
            ("干员总数", summary.get("operator_count")),
            ("六星干员", summary.get("six_star_count")),
            ("精英二", summary.get("elite_two_count")),
            ("皮肤保有", summary.get("skin_count")),
        ],
    )


def render_endfield(summary, out_path):
    """终末地名片。"""
    uid = summary.get("uid")
    level = summary.get("level")
    return render_card(
        out_path=out_path,
        game="endfield",
        nickname=summary.get("nickname"),
        level=f"Lv.{level}" if level else "",
        uid=f"UID: {uid}" if uid else "",
        raw_stats=[
            ("创建天数", summary.get("play_days")),
            ("干员总数", summary.get("character_count")),
            ("武器总数", summary.get("weapon_count")),
            ("档案总数", summary.get("doc_count")),
            ("世界等级", summary.get("world_level")),
        ],
    )