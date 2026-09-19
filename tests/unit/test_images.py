import pytest

from backend.images import (
    ImageValidationError,
    declared_image_mime,
    sanitize_filename,
    sniff_image_mime,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 8
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 12
GIF = b"GIF89a" + b"0" * 10
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"0" * 4


def test_sanitize_filename_strips_paths_and_rejects_empty() -> None:
    assert sanitize_filename("/etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\win.png") == "win.png"
    assert sanitize_filename("  map.png  ") == "map.png"
    with pytest.raises(ImageValidationError):
        sanitize_filename("../")
    with pytest.raises(ImageValidationError):
        sanitize_filename(None)


def test_declared_image_mime_accepts_rasters_and_rejects_others() -> None:
    assert declared_image_mime("a.png") == "image/png"
    assert declared_image_mime("a.JPG") == "image/jpeg"
    assert declared_image_mime("a.webp") == "image/webp"
    for name in ("a.svg", "a.txt", "a.exe", "noextension"):
        with pytest.raises(ImageValidationError):
            declared_image_mime(name)


def test_sniff_image_mime_recognises_common_formats() -> None:
    assert sniff_image_mime(PNG) == "image/png"
    assert sniff_image_mime(JPEG) == "image/jpeg"
    assert sniff_image_mime(GIF) == "image/gif"
    assert sniff_image_mime(WEBP) == "image/webp"


def test_sniff_image_mime_rejects_non_images() -> None:
    assert sniff_image_mime(b"<svg xmlns='http://www.w3.org/2000/svg'>") is None
    assert sniff_image_mime(b"just text") is None
    assert sniff_image_mime(b"") is None
