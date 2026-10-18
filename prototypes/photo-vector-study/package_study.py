# /// script
# requires-python = ">=3.12"
# dependencies = ["pillow==12.0.0"]
# ///
"""Prepare compact, tracked gallery assets and the optional download bundle."""

import io
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image

ROOT = Path(__file__).resolve().parent


def main() -> None:
    output = ROOT / "output"
    for path in sorted(output.rglob("*")):
        if path.suffix in {".svg", ".json", ".html"}:
            text = "\n".join(line.rstrip() for line in path.read_text().splitlines())
            path.write_text(text.rstrip() + "\n")
        elif path.suffix == ".png" and path.stat().st_size > 480 * 1024:
            image = Image.open(path)
            for colors in (256, 128, 96, 64):
                buffer = io.BytesIO()
                image.quantize(colors=colors, dither=Image.Dither.NONE).save(
                    buffer, format="PNG", optimize=True
                )
                if buffer.tell() <= 480 * 1024:
                    path.write_bytes(buffer.getvalue())
                    break
            else:
                raise ValueError(
                    f"Gallery image still exceeds the asset budget: {path}"
                )
    with ZipFile(output / "study.zip", "w", ZIP_DEFLATED) as archive:
        for path in sorted(ROOT.glob("*.py")):
            archive.write(path, path.name)
        for name in ("README.md", "INTERACTION.md", "NEXT_EXPERIMENT.md"):
            archive.write(ROOT / name, name)
        for path in sorted((ROOT / "edits").glob("*.json")):
            archive.write(path, str(path.relative_to(ROOT)))
        archive.write(ROOT / "BIZARRE_LICENSE.txt", "BIZARRE_LICENSE.txt")
        for path in sorted(output.rglob("*")):
            if path.is_file() and path.suffix != ".zip":
                archive.write(path, str(path.relative_to(ROOT)))
    print("Gallery assets prepared; download bundle: output/study.zip")


if __name__ == "__main__":
    main()
