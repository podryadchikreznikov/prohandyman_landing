from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image, ImageFilter
except ImportError:  # pragma: no cover
    print("[cleanup_partner_logos] Требуется библиотека Pillow. Установи её командой: pip install Pillow", file=sys.stderr)
    sys.exit(1)


def remove_black_background(image: Image.Image, threshold: int = 5) -> Image.Image:
    """Заменяет почти чёрные пиксели (фон) на прозрачные.

    threshold — допуск яркости (0-255). Чем выше, тем больше тёмных оттенков станет прозрачными.
    """

    image = image.convert("RGBA")
    pixels = image.getdata()

    new_pixels = []
    for r, g, b, a in pixels:
        if a == 0:
            new_pixels.append((r, g, b, a))
            continue

        # почти чистый чёрный фон
        if r <= threshold and g <= threshold and b <= threshold:
            new_pixels.append((r, g, b, 0))
        else:
            new_pixels.append((r, g, b, a))

    image.putdata(new_pixels)
    return image


def add_soft_shadow(image: Image.Image, opacity: float = 0.35, blur_radius: int = 6) -> Image.Image:
    """Добавляет мягкую чёрную тень по форме альфа-канала изображения.

    Тень делается как лёгкое "свечение" вокруг логотипа, без квадратного прямоугольника.
    """

    image = image.convert("RGBA")
    r, g, b, a = image.split()

    # Размываем альфу, чтобы получить мягкий контур тени
    blurred_alpha = a.filter(ImageFilter.GaussianBlur(blur_radius))

    # Масштабируем прозрачность тени
    def _scale_alpha(value: int) -> int:
        return int(value * opacity)

    shadow_alpha = blurred_alpha.point(_scale_alpha)

    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha)

    # Накладываем тень под оригинальное изображение
    combined = Image.alpha_composite(shadow, image)
    return combined


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    assets_dir = project_root / "assets" / "handyman_images"

    logo_files = [assets_dir / f"logo_partner_{i:02}.png" for i in range(1, 13)]

    print("[cleanup_partner_logos] Обработка файлов:")
    for path in logo_files:
        if not path.exists():
            print(f"  - {path.name}: файл не найден, пропускаю")
            continue

        try:
            img = Image.open(path)
        except Exception as exc:  # pragma: no cover
            print(f"  - {path.name}: ошибка при открытии: {exc}")
            continue

        processed = remove_black_background(img)

        # Для отдельных логотипов добавляем мягкую тень по форме
        if path.name in {"logo_partner_02.png", "logo_partner_12.png"}:
            processed = add_soft_shadow(processed)
        processed.save(path)
        print(f"  - {path.name}: фон обновлён (чёрный → прозрачный)")

    print("[cleanup_partner_logos] Готово.")


if __name__ == "__main__":  # pragma: no cover
    main()
