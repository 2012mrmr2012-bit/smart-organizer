"""يحوّل app.png إلى app.ico (بكل المقاسات اللي ويندوز محتاجها).
الاستخدام:  python make_icon.py            (بيدوّر على app.png جنب الملف)
"""
import sys
from pathlib import Path

from PIL import Image

SIZES = [16, 24, 32, 48, 64, 128, 256]


def main():
    here = Path(__file__).resolve().parent
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "app.png"
    dst = here / "app.ico"
    if not src.exists():
        print(f"مش لاقي {src}")
        sys.exit(1)
    img = Image.open(src).convert("RGBA")
    # نخليها مربعة من غير ما نشوّه الصورة
    side = max(img.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    square = square.resize((256, 256), Image.LANCZOS)
    square.save(dst, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"تم إنشاء {dst}")


if __name__ == "__main__":
    main()
