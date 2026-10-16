"""Side-by-side page images: the reference report on the left, a rendered report on the right.

  uv run python scripts/compose-report-pages.py <target.pdf> <rendered.pdf> <out-dir> <name>

One image per page of the longer document; a missing page is left blank so a missing or extra
page is visible. Needs poppler's pdftoppm.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image


def pages(pdf: str, into: Path) -> list[Image.Image]:
    subprocess.run(["pdftoppm", "-r", "80", "-png", pdf, str(into / "p")], check=True)
    return [Image.open(path).convert("RGB") for path in sorted(into.glob("p-*.png"))]


def main() -> None:
    target, rendered, out, name = sys.argv[1:5]
    Path(out).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as left_dir, tempfile.TemporaryDirectory() as right_dir:
        left, right = pages(target, Path(left_dir)), pages(rendered, Path(right_dir))
        width, height = left[0].size
        for index in range(max(len(left), len(right))):
            sheet = Image.new("RGB", (width * 2 + 20, height), "#888888")
            if index < len(left):
                sheet.paste(left[index], (0, 0))
            if index < len(right):
                sheet.paste(right[index].resize((width, height)), (width + 20, 0))
            sheet.save(Path(out) / f"{name}-page-{index + 1:02d}.png", optimize=True)


main()
