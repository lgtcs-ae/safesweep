"""Create SafeSweep macOS icon assets."""

from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError as exc:  # pragma: no cover - packaging helper
    raise SystemExit("Pillow is required to build the macOS icon: python3 -m pip install pillow") from exc


ROOT = Path(__file__).resolve().parent
ICONSET = ROOT / "SafeSweep.iconset"
ICNS = ROOT / "SafeSweep.icns"


def _blend(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(a[index] + (b[index] - a[index]) * t) for index in range(3))


def _make_icon(size: int) -> Image.Image:
    scale = 4
    canvas_size = size * scale
    radius = int(canvas_size * 0.23)

    icon = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    mask = Image.new("L", (canvas_size, canvas_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    inset = int(canvas_size * 0.045)
    mask_draw.rounded_rectangle(
        (inset, inset, canvas_size - inset, canvas_size - inset),
        radius=radius,
        fill=255,
    )

    gradient = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    pixels = gradient.load()
    for y in range(canvas_size):
        for x in range(canvas_size):
            diagonal = (x + y) / (2 * canvas_size)
            color = _blend((91, 61, 245), (34, 166, 112), diagonal)
            glow = max(
                0.0,
                1.0 - ((x - canvas_size * 0.32) ** 2 + (y - canvas_size * 0.20) ** 2) ** 0.5 / (canvas_size * 0.70),
            )
            pixels[x, y] = (*_blend(color, (255, 255, 255), glow * 0.20), 255)

    shadow = mask.filter(ImageFilter.GaussianBlur(max(2, int(canvas_size * 0.018))))
    shadow_layer = Image.new("RGBA", (canvas_size, canvas_size), (18, 24, 38, 52))
    icon.alpha_composite(Image.composite(shadow_layer, Image.new("RGBA", icon.size), shadow))
    icon.alpha_composite(Image.composite(gradient, Image.new("RGBA", icon.size), mask))

    draw = ImageDraw.Draw(icon)
    shield = [
        (canvas_size * 0.50, canvas_size * 0.19),
        (canvas_size * 0.72, canvas_size * 0.29),
        (canvas_size * 0.69, canvas_size * 0.58),
        (canvas_size * 0.50, canvas_size * 0.79),
        (canvas_size * 0.31, canvas_size * 0.58),
        (canvas_size * 0.28, canvas_size * 0.29),
    ]
    draw.polygon(shield, fill=(255, 255, 255, 46))
    draw.line(shield + [shield[0]], fill=(255, 255, 255, 230), width=max(4, int(canvas_size * 0.035)), joint="curve")
    draw.line(
        [
            (canvas_size * 0.39, canvas_size * 0.49),
            (canvas_size * 0.47, canvas_size * 0.58),
            (canvas_size * 0.63, canvas_size * 0.40),
        ],
        fill=(255, 255, 255, 255),
        width=max(5, int(canvas_size * 0.055)),
        joint="curve",
    )

    resampling = getattr(Image, "Resampling", Image).LANCZOS
    return icon.resize((size, size), resampling)


def main() -> None:
    ICONSET.mkdir(parents=True, exist_ok=True)
    for file in ICONSET.glob("*.png"):
        file.unlink()

    outputs = {
        "icon_16x16.png": 16,
        "icon_16x16@2x.png": 32,
        "icon_32x32.png": 32,
        "icon_32x32@2x.png": 64,
        "icon_128x128.png": 128,
        "icon_128x128@2x.png": 256,
        "icon_256x256.png": 256,
        "icon_256x256@2x.png": 512,
        "icon_512x512.png": 512,
        "icon_512x512@2x.png": 1024,
    }
    for name, size in outputs.items():
        _make_icon(size).save(ICONSET / name)

    master = Image.open(ICONSET / "icon_512x512@2x.png")
    master.save(
        ICNS,
        format="ICNS",
        sizes=[(16, 16), (32, 32), (64, 64), (128, 128), (256, 256), (512, 512), (1024, 1024)],
    )


if __name__ == "__main__":
    main()
