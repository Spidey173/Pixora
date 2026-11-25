"""Reproducible image optimization script for Pixora thumbnails.

Resizes game thumbnails in static/Games/Images/ to max 640px wide (WebP q=75)
and generates 320w responsive variants (<stem>-320w.webp).
"""
from pathlib import Path
from PIL import Image

IMAGES_DIR = Path(__file__).resolve().parent.parent / "static" / "Games" / "Images"


def optimize_directory(target_dir: Path = IMAGES_DIR, quality: int = 75) -> None:
    """Optimize all WebP thumbnails in target_dir and emit 320w variants."""
    if not target_dir.exists():
        print(f"Directory not found: {target_dir}")
        return

    for path in sorted(target_dir.glob("*.webp")):
        if path.stem.endswith("-320w"):
            continue
        before_kb = path.stat().st_size / 1024
        with Image.open(path) as img:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")

            # Resize main asset to max 640px wide
            if img.width > 640:
                new_h = int(img.height * (640 / img.width))
                main_img = img.resize((640, new_h), Image.Resampling.LANCZOS)
            else:
                main_img = img
            main_img.save(path, "WEBP", quality=quality, method=6)

            # Generate 320w responsive variant
            w320_path = path.with_name(f"{path.stem}-320w.webp")
            if img.width > 320:
                h320 = int(img.height * (320 / img.width))
                small_img = img.resize((320, h320), Image.Resampling.LANCZOS)
            else:
                small_img = img
            small_img.save(w320_path, "WEBP", quality=quality, method=6)

        after_kb = path.stat().st_size / 1024
        small_kb = w320_path.stat().st_size / 1024
        print(f"{path.name:30s} {before_kb:6.1f} KB -> {after_kb:5.1f} KB (320w: {small_kb:5.1f} KB)")


if __name__ == "__main__":
    optimize_directory()
