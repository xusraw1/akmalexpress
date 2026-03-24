"""Image optimization helpers for uploaded photos."""

from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError


MAX_WEBP_QUALITY = 95
MIN_WEBP_QUALITY = 40
DEFAULT_WEBP_QUALITY = 84
try:
    RESAMPLE_FILTER = Image.Resampling.LANCZOS
except AttributeError:  # Pillow compatibility fallback
    RESAMPLE_FILTER = Image.LANCZOS


def optimize_uploaded_image(uploaded_file, *, max_size=(1800, 1800), quality=DEFAULT_WEBP_QUALITY):
    """
    Convert uploaded image to optimized WEBP and resize to fit max_size.
    Falls back to original file if optimization fails.
    """
    if uploaded_file is None:
        return uploaded_file

    target_quality = max(MIN_WEBP_QUALITY, min(MAX_WEBP_QUALITY, int(quality)))
    try:
        uploaded_file.seek(0)
        with Image.open(uploaded_file) as source_image:
            image = ImageOps.exif_transpose(source_image)
            if image.mode not in ('RGB', 'RGBA'):
                image = image.convert('RGBA' if 'A' in image.getbands() else 'RGB')

            image.thumbnail(max_size, RESAMPLE_FILTER)

            output = BytesIO()
            image.save(
                output,
                format='WEBP',
                quality=target_quality,
                method=6,
                optimize=True,
            )
            output.seek(0)
    except (UnidentifiedImageError, OSError, ValueError, TypeError):
        try:
            uploaded_file.seek(0)
        except (AttributeError, OSError, ValueError):
            pass
        return uploaded_file

    original_name = Path(getattr(uploaded_file, 'name', 'image.webp'))
    optimized_name = f'{original_name.stem or "image"}.webp'
    return ContentFile(output.read(), name=optimized_name)
