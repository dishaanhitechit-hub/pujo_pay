import os
from PIL import Image, ImageDraw, ImageFont

# Font paths (DejaVu is always available on Ubuntu/Debian)
_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = _FONT_PATHS[::2] if bold else _FONT_PATHS[1::2]
    for path in candidates:
        if os.path.isfile(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _center_x(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return (width - (bbox[2] - bbox[0])) // 2


def generate_membership_card(user, org_name: str, save_dir: str) -> str:
    """Generate a membership card PNG, save to save_dir, return absolute path."""
    os.makedirs(save_dir, exist_ok=True)

    W, H = 900, 500

    # ── Background ────────────────────────────────────────────────────────────
    img = Image.new("RGB", (W, H), color=(10, 20, 50))   # deep navy
    draw = ImageDraw.Draw(img)

    # Gradient-style top strip
    for y in range(80):
        alpha = int(180 * (1 - y / 80))
        draw.line([(0, y), (W, y)], fill=(255, 140, 0, alpha))

    # Top strip (solid orange band)
    draw.rectangle([0, 0, W, 6], fill=(255, 140, 0))

    # Bottom strip
    draw.rectangle([0, H - 6, W, H], fill=(255, 140, 0))

    # Side strips
    draw.rectangle([0, 0, 6, H], fill=(255, 140, 0))
    draw.rectangle([W - 6, 0, W, H], fill=(255, 140, 0))

    # Subtle inner border
    draw.rectangle([14, 14, W - 14, H - 14], outline=(255, 140, 0, 60), width=1)

    # ── Org name ──────────────────────────────────────────────────────────────
    f_org = _font(30, bold=True)
    org_text = f"🙏  {org_name.upper()}"
    draw.text((_center_x(draw, org_text, f_org, W), 30), org_text, font=f_org, fill=(255, 200, 80))

    # Divider
    draw.line([(60, 80), (W - 60, 80)], fill=(255, 140, 0), width=2)

    # MEMBERSHIP CARD label
    f_label = _font(14, bold=False)
    card_label = "✦  MEMBERSHIP CARD  ✦"
    draw.text((_center_x(draw, card_label, f_label, W), 92), card_label, font=f_label, fill=(200, 200, 200))

    # ── Member details ────────────────────────────────────────────────────────
    f_name  = _font(36, bold=True)
    f_val   = _font(20, bold=False)
    f_key   = _font(13, bold=False)

    name_display = user.name or "Member"
    draw.text((_center_x(draw, name_display, f_name, W), 130), name_display, font=f_name, fill=(255, 255, 255))

    rows = [
        ("MEMBER ID",     user.member_id or "—"),
        ("CATEGORY",      (user.member_category or "General").title()),
        ("MEMBER SINCE",  user.member_since.strftime("%d %b %Y") if user.member_since else "—"),
    ]

    col_x = [120, 380, 640]
    row_y = 220
    for i, (key, val) in enumerate(rows):
        x = col_x[i % len(col_x)]
        draw.text((x, row_y), key, font=f_key, fill=(180, 180, 180))
        draw.text((x, row_y + 22), val, font=f_val, fill=(255, 220, 100))

    # Divider
    draw.line([(60, 310), (W - 60, 310)], fill=(80, 80, 120), width=1)

    # ── Footer ────────────────────────────────────────────────────────────────
    f_foot = _font(15, bold=False)
    footer = "Thank you for being a valued member  •  Shubho Pujo! 🎉"
    draw.text((_center_x(draw, footer, f_foot, W), 330), footer, font=f_foot, fill=(160, 160, 200))

    # Decorative dots
    for dx in range(20, W - 20, 30):
        draw.ellipse([dx, H - 40, dx + 3, H - 37], fill=(255, 140, 0, 60))

    # ── Save ──────────────────────────────────────────────────────────────────
    safe_id = (user.member_id or str(user.id)).replace("/", "_").replace(" ", "_")
    filename = f"card_{safe_id}.png"
    path = os.path.join(save_dir, filename)
    img.save(path, "PNG", optimize=True)
    return path
