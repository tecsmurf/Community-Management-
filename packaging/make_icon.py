"""Draws the app icon. Run once after changing it:  python packaging/make_icon.py"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SAFFRON, WHITE = (181, 84, 28), (255, 255, 255)


def draw(size=512):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=size // 5, fill=SAFFRON)
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(size * 0.62))
    d.text((size / 2, size * 0.53), "A", font=font, fill=WHITE, anchor="mm")
    d.ellipse([size * 0.12, size * 0.12, size * 0.88, size * 0.88], outline=(255, 255, 255, 110),
              width=max(2, size // 40))
    return img


def draw_flat(size):
    """Full-bleed saffron square with the mark (for round launcher icons)."""
    img = Image.new("RGBA", (size, size), SAFFRON + (255,))
    mark = draw_mark(int(size * 0.8))
    img.paste(mark, ((size - mark.width) // 2, (size - mark.height) // 2), mark)
    return img


def draw_mark(size):
    """The white letter and ring on a transparent background."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", int(size * 0.62))
    d.text((size / 2, size * 0.53), "A", font=font, fill=WHITE, anchor="mm")
    d.ellipse([size * 0.06, size * 0.06, size * 0.94, size * 0.94], outline=(255, 255, 255, 110),
              width=max(2, size // 40))
    return img


if __name__ == "__main__":
    img = draw()
    img.resize((180, 180), Image.LANCZOS).save(ROOT / "community_manager/static/icon.png")
    img.resize((64, 64), Image.LANCZOS).save(ROOT / "community_manager/static/favicon.png")
    # Icons for installing the online version on a phone or computer.
    for size in (192, 512):
        draw(size * 2).resize((size, size), Image.LANCZOS).save(ROOT / f"community_manager/static/icon-{size}.png")
    maskable = Image.new("RGBA", (1024, 1024), SAFFRON + (255,))
    mark = draw_mark(640)
    maskable.paste(mark, (192, 192), mark)
    maskable.resize((512, 512), Image.LANCZOS).save(ROOT / "community_manager/static/icon-maskable-512.png")
    img.save(ROOT / "packaging/app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    # Android app icons, named the way Briefcase expects.
    big = draw(1280)
    out = ROOT / "mobile/icons"
    out.mkdir(parents=True, exist_ok=True)
    for size in (48, 72, 96, 144, 192):
        big.resize((size, size), Image.LANCZOS).save(out / f"community_app-square-{size}.png")
        round_icon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
        round_icon.paste(draw_flat(size), (0, 0), mask)
        round_icon.save(out / f"community_app-round-{size}.png")
    for size in (108, 162, 216, 324, 432):
        # Adaptive icon foreground: the launcher crops it, so keep the mark in the middle.
        fg = Image.new("RGBA", (size, size), SAFFRON + (255,))
        mark = draw_mark(int(size * 0.6))
        fg.paste(mark, ((size - mark.width) // 2, (size - mark.height) // 2), mark)
        fg.save(out / f"community_app-adaptive-{size}.png")
    for size in (320, 480, 640, 960, 1280):
        big.resize((size, size), Image.LANCZOS).save(out / f"community_app-square-{size}.png")
    print("icons written")
