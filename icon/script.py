# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "resvg-py>=0.5,<0.6"]
# ///

import io
from html import escape
from pathlib import Path

import resvg_py
from PIL import Image


PNG_SIZES = (
    16, 20, 24, 29, 32, 40, 48, 58, 60, 64, 72, 76, 80, 87,
    96, 120, 128, 144, 152, 167, 180, 192, 256, 310, 384, 512, 1024,
)


def main():
    output_dir = Path(__file__).resolve().parent
    # Render SVG gradients and their opacity with resvg before resizing.
    png = resvg_py.svg_to_bytes(
        svg_path=str(output_dir / "icon.svg"), width=1024, height=1024
    )
    with Image.open(io.BytesIO(png)) as image:
        master = image.convert("RGBA")

    for size in PNG_SIZES:
        master.resize((size, size), Image.Resampling.LANCZOS).save(
            output_dir / f"icon-{size}x{size}.png"
        )

    master.resize((180, 180), Image.Resampling.LANCZOS).save(
        output_dir / "apple-touch-icon.png"
    )
    master.save(
        output_dir / "icon.ico",
        format="ICO",
        sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)],
    )
    master.save(
        output_dir / "favicon.ico",
        format="ICO",
        sizes=[(size, size) for size in (16, 32, 48)],
    )
    filenames = [f"icon-{size}x{size}.png" for size in PNG_SIZES]
    filenames += ["apple-touch-icon.png", "icon.ico", "favicon.ico", "icon.svg"]
    links = "\n".join(
        f'<li><a href="{escape(name, quote=True)}">'
        f'<img src="{escape(name, quote=True)}" alt="" loading="lazy">'
        f'<span>{escape(name)}</span></a></li>'
        for name in filenames
    )
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>is-up.to icons</title>
  <style>
    :root { color-scheme: light dark; }
    body { margin: 0 auto; padding: 2rem; max-width: 70rem;
           font-family: system-ui, sans-serif; background: #f5f5f7; color: #20202a; }
    ul { list-style: none; padding: 0; display: grid; gap: 1rem;
         grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); }
    a { display: flex; flex-direction: column; align-items: center; gap: 1rem;
        padding: 1rem; background: white; border-radius: 12px; color: #49309a; }
    a:hover, a:focus-visible { outline: 2px solid #7953cf; }
    img { width: 96px; height: 96px; object-fit: contain; }
    @media (prefers-color-scheme: dark) {
      body { background: #16161d; color: #ededf4; }
      a { background: #252530; color: #cbb7ff; }
      a:hover, a:focus-visible { outline-color: #b99aff; }
    }
  </style>
</head>
<body>
  <h1>is-up.to icons</h1>
  <p>is-up.to site logo</p>
  <ul>
""" + links + """
  </ul>
</body>
</html>
"""
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"Created {len(PNG_SIZES) + 3} icon files and index.html in {output_dir}")


if __name__ == "__main__":
    main()
