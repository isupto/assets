# /// script
# requires-python = ">=3.10"
# dependencies = ["fonttools", "pillow", "resvg-py>=0.5,<0.6", "uharfbuzz"]
# ///

import hashlib
import io
import math
import random
import re
import tempfile
import urllib.request
from dataclasses import dataclass
from html import escape
from pathlib import Path

import resvg_py
import uharfbuzz as hb
from fontTools.misc.transform import Transform
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from PIL import Image


# Recursive, the site's typeface (SIL Open Font License 1.1). Text is written into the SVGs as outlines.
FONT_URL = (
    "https://raw.githubusercontent.com/google/fonts/8b0a1d0f5983c89bc2b93f1b5fb55f9e252744b5"
    "/ofl/recursive/Recursive%5BCASL,CRSV,MONO,slnt,wght%5D.ttf"
)
FONT_SHA256 = "653221ca467f4732fe6856ac493f6c409e9f56a7674abe36b2364acc89796f7c"

# The site's light theme (service/app/globals.css) and the "Studio" preview theme.
PAPER = "#f5f4f8"
SURFACE = "#ffffff"
INK = "#1e1a2e"
INK_SOFT = "#5b5670"
LINE = "#e3dfeb"
VIOLET = "#6d3fd6"
TONES = {"up": "#1e9e5a", "busy": "#d98a00", "down": "#d6334a", "info": "#2764e7", "idle": "#9a95ab"}

# Recursive's axes give one family three voices, each with the site's letter spacing in em.
VOICES = {
    "casual": ({"CASL": 1, "MONO": 0, "CRSV": 1}, -0.02),
    "linear": ({"CASL": 0, "MONO": 0, "CRSV": 0.5}, 0),
    "mono": ({"CASL": 0, "MONO": 1, "CRSV": 0}, -0.01),
}

TAGLINE = ("What you’re", "up to,", "on one page.")
SUMMARY = "Services, presence and schedule."
HOST = "yourname.is-up.to"
ALT = (
    "is-up.to: what you’re up to, on one page. The is-up.to logo inside a ring of status-coloured dots."
)


def number(value):
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return "0" if text == "-0" else text


def attributes(values):
    return "".join(f' {name.replace("_", "-")}="{value}"' for name, value in values.items())


def rect(x, y, width, height, fill, radius=0, **extra):
    if radius:
        extra = {"rx": number(radius), **extra}
    return (
        f'<rect x="{number(x)}" y="{number(y)}" width="{number(width)}" height="{number(height)}" '
        f'fill="{fill}"{attributes(extra)}/>'
    )


def circle(cx, cy, r, fill, **extra):
    return f'<circle cx="{number(cx)}" cy="{number(cy)}" r="{number(r)}" fill="{fill}"{attributes(extra)}/>'


def load_font():
    cached = Path(tempfile.gettempdir()) / f"recursive-{FONT_SHA256[:16]}.ttf"
    if cached.exists() and hashlib.sha256(cached.read_bytes()).hexdigest() == FONT_SHA256:
        return cached.read_bytes()
    with urllib.request.urlopen(FONT_URL, timeout=60) as response:
        data = response.read()
    if hashlib.sha256(data).hexdigest() != FONT_SHA256:
        raise SystemExit(f"Unexpected SHA-256 for {FONT_URL}")
    cached.write_bytes(data)
    return data


@dataclass
class Text:
    font: hb.Font
    scale: float
    glyphs: list
    width: float

    def draw(self, x, baseline, fill, anchor="start"):
        x -= {"start": 0, "middle": self.width / 2, "end": self.width}[anchor]
        pen = SVGPathPen(None, ntos=number)
        for glyph, dx, dy in self.glyphs:
            transform = Transform(self.scale, 0, 0, -self.scale, x + dx, baseline - dy)
            self.font.draw_glyph_with_pen(glyph, TransformPen(pen, transform))
        return f'<path fill="{fill}" d="{pen.getCommands()}"/>'


class Typeface:
    def __init__(self, data):
        self.face = hb.Face(hb.Blob(data))
        self.fonts = {}

    def __call__(self, value, size, weight=400, voice="linear"):
        axes, tracking = VOICES[voice]
        if (weight, voice) not in self.fonts:
            font = hb.Font(self.face)
            font.set_variations({**axes, "wght": weight})
            self.fonts[weight, voice] = font
        font = self.fonts[weight, voice]
        buffer = hb.Buffer()
        buffer.add_str(value)
        buffer.guess_segment_properties()
        hb.shape(font, buffer)
        scale = size / self.face.upem
        glyphs, x = [], 0.0
        for info, position in zip(buffer.glyph_infos, buffer.glyph_positions):
            glyphs.append((info.codepoint, x + position.x_offset * scale, position.y_offset * scale))
            x += position.x_advance * scale + tracking * size
        return Text(font, scale, glyphs, x - tracking * size)


class Scene:
    def __init__(self, width, height, icon_svg):
        self.width, self.height = width, height
        self.defs, self.body = [], []
        source = icon_svg.read_text(encoding="utf-8")
        self.notice = re.search(r"<!--.*?-->", source, re.S).group(0)
        self.icon_body = re.search(r"<svg[^>]*>(.*)</svg>", source, re.S).group(1).strip()
        self.ids = 0

    def id(self, prefix):
        self.ids += 1
        return f"{prefix}-{self.ids}"

    def add(self, *elements):
        self.body.extend(elements)

    def icon(self, x, y, size):
        return (
            f'<svg x="{number(x)}" y="{number(y)}" width="{number(size)}" height="{number(size)}" viewBox="0 0 48 48">'
            f"{self.icon_body}</svg>"
        )

    def backdrop(self, glow_x, glow_y, glow_r):
        """Paper with a violet glow."""
        self.defs.append(
            f'<radialGradient id="glow" cx="{number(glow_x)}" cy="{number(glow_y)}" r="{number(glow_r)}" '
            'gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="{VIOLET}" stop-opacity=".2"/>'
            f'<stop offset=".55" stop-color="{VIOLET}" stop-opacity=".07"/>'
            f'<stop offset="1" stop-color="{VIOLET}" stop-opacity="0"/></radialGradient>'
        )
        self.add(
            rect(0, 0, self.width, self.height, PAPER),
            rect(0, 0, self.width, self.height, "url(#glow)"),
        )

    def headline(self, t, x, baseline, lines, size, accent_last=True):
        parts = []
        for index, line in enumerate(lines):
            fill = VIOLET if accent_last and index == len(lines) - 1 else INK
            parts.append(t(line, size, 800, "casual").draw(x, baseline + index * size * 1.08, fill))
        return "".join(parts)

    def summary(self, t, x, baseline, size, anchor="start", single_line=False):
        """The summary sentence, then "Free on yourname.is-up.to" with the host in the mono voice."""
        free, host = t("Free on ", size), t(HOST, size, 500, "mono")
        if single_line:
            first = t(f"{SUMMARY[:-1]}, free on ", size)
            start = x - {"start": 0, "end": first.width + host.width}[anchor]
            return first.draw(start, baseline, INK_SOFT) + host.draw(start + first.width, baseline, VIOLET)
        second = baseline + size * 1.45
        start = x - {"start": 0, "end": free.width + host.width}[anchor]
        return (
            t(SUMMARY, size).draw(x, baseline, INK_SOFT, anchor)
            + free.draw(start, second, INK_SOFT)
            + host.draw(start + free.width, second, VIOLET)
        )

    def motif(self, cx, cy, size):
        """The logo on a disc, ringed by dots in the status colours that fade outward."""
        rng = random.Random(4)
        colors = [TONES["up"], VIOLET, TONES["busy"], TONES["info"], TONES["idle"], TONES["down"]]
        weights = [70, 10, 8, 7, 4, 1]
        disc = size * 0.62
        dots = []
        for ring in range(7):
            radius = disc + 30 + ring * 23
            count = round(2 * math.pi * radius / 23)
            offset = rng.random() * 2 * math.pi
            for index, color in enumerate(rng.choices(colors, weights, k=count)):
                angle = offset + index * 2 * math.pi / count
                x, y = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
                dots.append(circle(x, y, 5.5 - ring * 0.5, color, opacity=number(1 - ring * 0.13)))
        shadow = self.id("shadow")
        self.defs.append(
            f'<filter id="{shadow}" x="-50%" y="-50%" width="200%" height="200%">'
            '<feGaussianBlur stdDeviation="22"/></filter>'
        )
        # The icon's artwork sits right of and below its viewBox center.
        return (
            "".join(dots)
            + circle(cx, cy + 18, disc * 0.92, INK, opacity=".2", filter=f"url(#{shadow})")
            + circle(cx, cy, disc, SURFACE, stroke=LINE)
            + self.icon(cx - size * 0.54, cy - size * 0.52, size)
        )

    def svg(self, title):
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f"{self.notice}\n"
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
            f'viewBox="0 0 {self.width} {self.height}" role="img" aria-label="{escape(title, quote=True)}">\n'
            f"<defs>{''.join(self.defs)}</defs>\n" + "\n".join(self.body) + "\n</svg>\n"
        )


def open_graph(scene, t):
    """1200 × 630 link preview (Open Graph, X, Slack, Discord, LinkedIn), centered on larger canvases."""
    ox, oy = (scene.width - 1200) / 2, (scene.height - 630) / 2
    scene.backdrop(ox + 920, oy + 300, 560)
    size = min(84, 520 / max(t(line, 1, 800, "casual").width for line in TAGLINE))
    scene.add(
        t("is-up.to", 34, 700, "casual").draw(ox + 72, oy + 101, INK),
        scene.headline(t, ox + 72, oy + 238, TAGLINE, size),
        scene.summary(t, ox + 72, oy + 238 + size * 2.16 + 76, 26),
        scene.motif(ox + 905, oy + 315, 200),
    )


def x_header(scene, t):
    """1500 × 500 profile header. The avatar covers the lower left, so text stays above it."""
    scene.backdrop(1180, 250, 560)
    lines = ("What you’re up to,", "on one page.")
    scene.add(
        scene.headline(t, 96, 178, lines, 70),
        scene.summary(t, 96, 178 + 70 * 1.08 + 72, 26, single_line=True),
        scene.motif(1180, 250, 170),
    )


def linkedin_cover(scene, t):
    """1128 × 191 company page cover. The logo covers the lower left, so text is right-aligned."""
    scene.backdrop(860, 95, 420)
    line = t("What you’re up to, on one page.", 38, 800, "casual")
    scene.add(
        line.draw(1128 - 64, 92, INK, "end"),
        scene.summary(t, 1128 - 64, 132, 18, "end", single_line=True),
    )


BANNERS = [
    ("og", 1200, 630, open_graph, "Link previews: Open Graph and X cards"),
    ("github-social-preview", 1280, 640, open_graph, "GitHub repository social preview"),
    ("x-header", 1500, 500, x_header, "X profile header"),
    ("linkedin-cover", 1128, 191, linkedin_cover, "LinkedIn company page cover"),
]


def main():
    output_dir = Path(__file__).resolve().parent
    t = Typeface(load_font())
    for name, width, height, build, _ in BANNERS:
        scene = Scene(width, height, output_dir.parent / "icon" / "icon.svg")
        build(scene, t)
        svg = scene.svg(ALT)
        (output_dir / f"{name}.svg").write_text(svg, encoding="utf-8")
        png = resvg_py.svg_to_bytes(svg_string=svg, skip_system_fonts=True)
        with Image.open(io.BytesIO(bytes(png))) as image:
            image.convert("RGB").save(output_dir / f"{name}.png", optimize=True)

    items = "\n".join(
        f'<li><a href="{name}.png"><img src="{name}.png" alt="" width="{width}" height="{height}" loading="lazy"></a>'
        f'<p><a href="{name}.png">{name}.png</a> · <a href="{name}.svg">svg</a> · {width} × {height} · {escape(use)}</p></li>'
        for name, width, height, _, use in BANNERS
    )
    html = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>is-up.to banners</title>
  <style>
    :root { color-scheme: light dark; }
    body { margin: 0 auto; padding: 2rem; max-width: 70rem;
           font-family: system-ui, sans-serif; background: #f5f5f7; color: #20202a; }
    ul { list-style: none; padding: 0; display: grid; gap: 2rem; }
    li { padding: 1rem; background: white; border-radius: 12px; }
    img { display: block; width: 100%; height: auto; border-radius: 6px; }
    p { margin: .75rem 0 0; }
    a { color: #49309a; }
    @media (prefers-color-scheme: dark) {
      body { background: #16161d; color: #ededf4; }
      li { background: #252530; }
      a { color: #cbb7ff; }
    }
  </style>
</head>
<body>
  <h1>is-up.to banners</h1>
  <p>Social previews and profile banners. Alt text: """ + escape(ALT) + """</p>
  <ul>
""" + items + """
  </ul>
</body>
</html>
"""
    (output_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"Created {len(BANNERS) * 2} banner files and index.html in {output_dir}")


if __name__ == "__main__":
    main()
