"""Validate and re-encode JPEG uploads before any database mutation."""
from io import BytesIO
import warnings
from PIL import Image, UnidentifiedImageError
from .domain import ValidationError


def read_cover(upload):
    if not upload or not upload.filename:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(upload.stream) as image:
                if image.format != "JPEG" or image.width * image.height > 16000000:
                    raise ValidationError("Envie uma imagem JPEG de até 16 megapixels.")
                image.load()
                output = BytesIO()
                image.convert("RGB").save(output, "JPEG")
                content = output.getvalue()
                if len(content) > 2 * 1024 * 1024:
                    raise ValidationError("Imagem reencodificada excede 2 MiB.")
                return content
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ValidationError("Imagem JPEG inválida.") from None
