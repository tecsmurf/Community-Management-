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


if __name__ == "__main__":
    img = draw()
    img.resize((180, 180), Image.LANCZOS).save(ROOT / "community_manager/static/icon.png")
    img.resize((64, 64), Image.LANCZOS).save(ROOT / "community_manager/static/favicon.png")
    img.save(ROOT / "packaging/app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icons written")
