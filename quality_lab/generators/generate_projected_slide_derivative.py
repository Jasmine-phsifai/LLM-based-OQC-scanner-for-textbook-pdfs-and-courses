"""Generate the fixed perspective, glare, and JPEG slide derivative."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


PROJECTED_SIZE = (2880, 1800)
PERSPECTIVE_COEFFICIENTS = (
    1.0887639610426938,
    0.07406557558113566,
    -257.3038095688652,
    0.06221387559829089,
    1.0887428229700915,
    -274.9853301444459,
    1.2027062903952433e-05,
    6.224015580343351e-05,
)


def generate_projected_slide_derivative(
    clean_slide_path: Path,
    output_path: Path,
) -> Path:
    """Write the deterministic lossy projection derived from the clean slide."""
    with Image.open(clean_slide_path) as clean_slide:
        source = clean_slide.convert("RGBA")
    warped = source.transform(
        PROJECTED_SIZE,
        Image.Transform.PERSPECTIVE,
        PERSPECTIVE_COEFFICIENTS,
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )
    source.close()

    canvas = Image.new("RGBA", PROJECTED_SIZE, color=(37, 42, 49, 255))
    shadow_alpha = Image.new("L", PROJECTED_SIZE, color=0)
    shadow_alpha.paste(warped.getchannel("A"), (24, 30))
    shadow_alpha = shadow_alpha.point(lambda value: value * 105 // 255)
    shadow = Image.new("RGBA", PROJECTED_SIZE, color=(0, 0, 0, 0))
    shadow.putalpha(shadow_alpha)
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(warped)

    glare_mask_small = _build_glare_mask()
    glare_mask = glare_mask_small.resize(PROJECTED_SIZE, Image.Resampling.BILINEAR)
    glare = Image.new("RGBA", PROJECTED_SIZE, color=(255, 250, 232, 0))
    glare.putalpha(glare_mask)
    canvas.alpha_composite(glare)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rgb = canvas.convert("RGB")
    rgb.save(
        output_path,
        format="JPEG",
        quality=72,
        subsampling=2,
        optimize=False,
        progressive=False,
    )
    rgb.close()
    glare.close()
    glare_mask.close()
    glare_mask_small.close()
    shadow.close()
    shadow_alpha.close()
    warped.close()
    canvas.close()
    return output_path


def _build_glare_mask() -> Image.Image:
    mask = Image.new("L", (720, 450), color=0)
    pixels = mask.load()
    center_x, center_y = 515, 105
    radius_x, radius_y = 170, 72
    denominator = radius_x * radius_x * radius_y * radius_y
    for y in range(mask.height):
        dy = y - center_y
        for x in range(mask.width):
            dx = x - center_x
            numerator = (
                dx * dx * radius_y * radius_y
                + dy * dy * radius_x * radius_x
            )
            if numerator < denominator:
                pixels[x, y] = (
                    92 * (denominator - numerator) * (denominator - numerator)
                    // (denominator * denominator)
                )
    return mask
