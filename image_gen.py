import textwrap
import random
import os
import tempfile
from PIL import Image, ImageDraw, ImageFont

# ─── COURSE-SPECIFIC COLOR THEMES ────────────────────────────────────────────
# TikTok Course: Dark Navy + Cyan
TIKTOK_THEMES = [
    {"bg": "#0A0F1C", "text": "#FFFFFF", "accent": "#00FFD1", "highlight": "#00B894"},
    {"bg": "#0D1B2A", "text": "#FFFFFF", "accent": "#00FFD1", "highlight": "#1B998B"},
    {"bg": "#101820", "text": "#FFFFFF", "accent": "#00E5CC", "highlight": "#00B4D8"},
]

# Instagram Course: Dark + Hot Pink + Gold
INSTAGRAM_THEMES = [
    {"bg": "#1A1A2E", "text": "#FFFFFF", "accent": "#FF1493", "highlight": "#FFD700"},
    {"bg": "#16213E", "text": "#FFFFFF", "accent": "#FF69B4", "highlight": "#FFC107"},
    {"bg": "#0F0E17", "text": "#FFFFFF", "accent": "#FF1493", "highlight": "#E6B800"},
]

# Neutral (for engagement/general posts)
NEUTRAL_THEMES = [
    {"bg": "#1A1A2E", "text": "#FFFFFF", "accent": "#7C3AED", "highlight": "#A78BFA"},
    {"bg": "#212529", "text": "#FFFFFF", "accent": "#FFC107", "highlight": "#FF9800"},
]

# ─── FONTS ────────────────────────────────────────────────────────────────────
FONT_BOLD    = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf"
FALLBACK_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FALLBACK_REG  = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def get_font(path: str, fallback: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except:
        try:
            return ImageFont.truetype(fallback, size)
        except:
            return ImageFont.load_default()


def wrap_text(text: str, font, max_width: int, draw) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _pick_theme(course: str) -> dict:
    """Pick a color theme based on course type."""
    if course == "tiktok":
        return random.choice(TIKTOK_THEMES)
    elif course == "instagram":
        return random.choice(INSTAGRAM_THEMES)
    else:
        return random.choice(NEUTRAL_THEMES)


def _draw_gradient_bar(draw, y: int, width: int, height: int, color_start: tuple, color_end: tuple):
    """Draw a horizontal gradient bar."""
    for x in range(width):
        ratio = x / max(width - 1, 1)
        r = int(color_start[0] + (color_end[0] - color_start[0]) * ratio)
        g = int(color_start[1] + (color_end[1] - color_start[1]) * ratio)
        b = int(color_start[2] + (color_end[2] - color_start[2]) * ratio)
        draw.line([(x, y), (x, y + height - 1)], fill=(r, g, b))


def _draw_category_badge(draw, category: str, acc_rgb: tuple, W: int):
    """Draw a small category badge in top-right corner."""
    labels = {
        "value": "💡 FREE TIP",
        "curiosity": "👀 STORY",
        "proof": "✅ PROOF",
        "offer": "🔥 OFFER",
        "engagement": "💬 JOIN IN",
    }
    label = labels.get(category, "")
    if not label:
        return

    font_badge = get_font(FONT_BOLD, FALLBACK_BOLD, 22)
    bbox = draw.textbbox((0, 0), label, font=font_badge)
    bw = bbox[2] - bbox[0] + 24
    bh = bbox[3] - bbox[1] + 14
    bx = W - bw - 30
    by = 25

    # Badge background
    draw.rounded_rectangle(
        [(bx, by), (bx + bw, by + bh)],
        radius=8,
        fill=acc_rgb,
    )
    # Badge text
    draw.text((bx + 12, by + 5), label, fill=(0, 0, 0), font=font_badge)


def _draw_price_tag(draw, price: str, acc_rgb: tuple, hi_rgb: tuple, W: int, H: int):
    """Draw a price tag for offer-type posts."""
    font_price = get_font(FONT_BOLD, FALLBACK_BOLD, 48)
    bbox = draw.textbbox((0, 0), price, font=font_price)
    pw = bbox[2] - bbox[0] + 40
    ph = bbox[3] - bbox[1] + 20
    px = (W - pw) // 2
    py = H - 100

    # Price bg
    draw.rounded_rectangle(
        [(px, py), (px + pw, py + ph)],
        radius=12,
        fill=hi_rgb,
    )
    draw.text((px + 20, py + 8), price, fill=(0, 0, 0), font=font_price)


# ─── MAIN IMAGE GENERATOR ────────────────────────────────────────────────────
def generate_image(main_text: str, sub_text: str = "", category: str = "value", course: str = "tiktok") -> str:
    """
    Generate a category-specific, course-themed marketing image.
    Returns path to saved temp JPEG file.

    Args:
        main_text: Primary headline text
        sub_text: Secondary text below the headline
        category: One of 'value', 'curiosity', 'proof', 'offer', 'engagement'
        course: One of 'tiktok', 'instagram'
    """
    W, H = 1200, 630
    theme = _pick_theme(course)

    bg_rgb  = hex_to_rgb(theme["bg"])
    txt_rgb = hex_to_rgb(theme["text"])
    acc_rgb = hex_to_rgb(theme["accent"])
    hi_rgb  = hex_to_rgb(theme["highlight"])

    img  = Image.new("RGB", (W, H), color=bg_rgb)
    draw = ImageDraw.Draw(img)

    # ── Gradient accent bars (top + bottom) ───────────────────────────────────
    _draw_gradient_bar(draw, 0, W, 6, acc_rgb, hi_rgb)
    _draw_gradient_bar(draw, H - 6, W, 6, hi_rgb, acc_rgb)

    # ── Side accent line (left) ───────────────────────────────────────────────
    draw.rectangle([(0, 6), (4, H - 6)], fill=acc_rgb)

    # ── Category badge ────────────────────────────────────────────────────────
    _draw_category_badge(draw, category, acc_rgb, W)

    # ── Main text ─────────────────────────────────────────────────────────────
    font_main = get_font(FONT_BOLD, FALLBACK_BOLD, 72)
    padding = 100
    max_w = W - padding * 2

    lines = wrap_text(main_text, font_main, max_w, draw)
    line_h = 85
    total_h = len(lines) * line_h
    sub_h = 50 if sub_text else 0
    block_h = total_h + sub_h + (20 if sub_text else 0)

    # Shift up slightly for offer posts to make room for price tag
    y_offset = -30 if category == "offer" else 0
    start_y = (H - block_h) // 2 + y_offset

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_main)
        lw = bbox[2] - bbox[0]
        x = (W - lw) // 2
        y = start_y + i * line_h

        # Shadow
        draw.text((x + 3, y + 3), line, fill=(0, 0, 0), font=font_main)
        # Main text
        draw.text((x, y), line, fill=txt_rgb, font=font_main)

    # ── Sub text ──────────────────────────────────────────────────────────────
    if sub_text:
        font_sub = get_font(FONT_REGULAR, FALLBACK_REG, 36)
        bbox = draw.textbbox((0, 0), sub_text, font=font_sub)
        sw = bbox[2] - bbox[0]
        sx = (W - sw) // 2
        sy = start_y + total_h + 20
        draw.text((sx, sy), sub_text, fill=acc_rgb, font=font_sub)

    # ── Price tag for offer posts ─────────────────────────────────────────────
    if category == "offer":
        _draw_price_tag(draw, "ONLY $7", acc_rgb, hi_rgb, W, H)

    # ── Decorative dots (subtle) ──────────────────────────────────────────────
    for _ in range(15):
        dx = random.randint(30, W - 30)
        dy = random.randint(30, H - 30)
        dr = random.randint(2, 5)
        opacity_rgb = tuple(max(0, c - 40) for c in bg_rgb)
        highlight_dot = (*acc_rgb, )
        draw.ellipse([(dx - dr, dy - dr), (dx + dr, dy + dr)],
                     fill=highlight_dot if random.random() < 0.3 else opacity_rgb)

    # ── Save ──────────────────────────────────────────────────────────────────
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    img.save(tmp.name, "JPEG", quality=95)
    tmp.close()
    return tmp.name
