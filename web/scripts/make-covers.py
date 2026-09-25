"""Draws the course covers in web/public/covers as SVG posters.

Dark, gridded and grainy, a lime label, the topic in big type with a lime dot,
and a drawing of the craft on the right. Run from anywhere:

    python3 web/scripts/make-covers.py
"""

import math
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "public" / "covers"
W, H = 1600, 900
LIME = "#b5f23d"
SANS = "Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif"
MONO = "'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace"


def polar(cx, cy, r, deg):
    a = math.radians(deg)
    return cx + r * math.cos(a), cy + r * math.sin(a)


def pts(*points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def label(x, y, text, fill="#ffffff", opacity=0.45, size=20, anchor="start"):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-family="{MONO}" font-size="{size}" '
        f'letter-spacing="4" fill="{fill}" fill-opacity="{opacity}">{text}</text>'
    )


def cover(slug, number, topic, tool, word, accent, art, size=210):
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <defs>
    <radialGradient id="glow" cx="0.7" cy="0.44" r="0.62">
      <stop offset="0" stop-color="{accent}" stop-opacity="0.36"/>
      <stop offset="0.5" stop-color="{accent}" stop-opacity="0.09"/>
      <stop offset="1" stop-color="{accent}" stop-opacity="0"/>
    </radialGradient>
    <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse">
      <path d="M48 0H0V48" fill="none" stroke="#ffffff" stroke-opacity="0.05"/>
    </pattern>
    <linearGradient id="shade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0.5" stop-color="#0a0a0b" stop-opacity="0"/>
      <stop offset="1" stop-color="#0a0a0b" stop-opacity="0.94"/>
    </linearGradient>
    <filter id="grain" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="2" stitchTiles="stitch"/>
      <feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0.14 0 0 0 0"/>
    </filter>
    <filter id="soft" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="28"/>
    </filter>
  </defs>
  <rect width="{W}" height="{H}" fill="#0a0a0b"/>
  <rect width="{W}" height="{H}" fill="url(#glow)"/>
  <rect width="{W}" height="{H}" fill="url(#grid)"/>
  {art}
  <rect width="{W}" height="{H}" fill="url(#shade)"/>
  {label(96, 132, f"ONER · {number} — {topic.upper()}", fill=LIME, opacity=1, size=28)}
  {label(W - 96, 132, tool, opacity=0.5, size=26, anchor="end")}
  <text x="88" y="806" font-family="{SANS}" font-size="{size}" font-weight="700" letter-spacing="{-size * 0.045:.1f}" fill="#ffffff">{word}<tspan fill="{LIME}">.</tspan></text>
  <rect width="{W}" height="{H}" filter="url(#grain)"/>
</svg>
'''
    (OUT / f"{slug}.svg").write_text(svg)


def color_grading():
    def wheel(cx, cy, r, puck, name):
        out = []
        for i in range(36):
            x0, y0 = polar(cx, cy, r, i * 10)
            x1, y1 = polar(cx, cy, r, i * 10 + 8.5)
            out.append(f'<path d="M{x0:.1f} {y0:.1f}A{r} {r} 0 0 1 {x1:.1f} {y1:.1f}" fill="none" stroke="hsl({i * 10},86%,62%)" stroke-width="16"/>')
        px, py = cx + puck[0], cy + puck[1]
        out += [
            f'<circle cx="{cx}" cy="{cy}" r="{r - 24}" fill="#0f0f12" stroke="#ffffff" stroke-opacity="0.08"/>',
            f'<path d="M{cx - r + 40} {cy}H{cx + r - 40}M{cx} {cy - r + 40}V{cy + r - 40}" stroke="#ffffff" stroke-opacity="0.12"/>',
            f'<line x1="{cx}" y1="{cy}" x2="{px}" y2="{py}" stroke="{LIME}" stroke-opacity="0.5" stroke-width="2"/>',
            f'<circle cx="{px}" cy="{py}" r="12" fill="#0a0a0b" stroke="{LIME}" stroke-width="4"/>',
            label(cx, cy + r + 58, name, size=22, anchor="middle"),
        ]
        return "\n  ".join(out)

    art = "\n  ".join([wheel(880, 380, 120, (-26, 18), "LIFT"), wheel(1150, 380, 120, (10, -34), "GAMMA"), wheel(1420, 380, 120, (30, 12), "GAIN")])
    cover("color-grading-resolve", "01", "Цвет", "DaVinci Resolve", "Цвет", "#ff6a3d", art)


def editing():
    parts = []
    x0, x1 = 760, 1504
    parts.append(f'<path d="M{x0} 250H{x1}" stroke="#ffffff" stroke-opacity="0.22"/>')
    for x in range(x0, x1 + 1, 34):
        major = (x - x0) % 136 == 0
        parts.append(f'<path d="M{x} 250V{234 if major else 243}" stroke="#ffffff" stroke-opacity="{0.4 if major else 0.2}"/>')
    for i, x in enumerate(range(x0, x1, 136)):
        parts.append(f'<text x="{x + 6}" y="226" font-family="{MONO}" font-size="18" fill="#ffffff" fill-opacity="0.38">00:{i * 4:02d}:00</text>')
    video = [
        ("V2", 282, [(770, 200, "#7c5cff"), (990, 140, "#a594ff"), (1150, 250, "#7c5cff"), (1420, 84, "#a594ff")]),
        ("V1", 360, [(770, 330, LIME), (1120, 170, "#dcf7a0"), (1310, 194, LIME)]),
    ]
    for name, y, clips in video:
        parts.append(f'<text x="712" y="{y + 36}" font-family="{MONO}" font-size="18" fill="#ffffff" fill-opacity="0.45">{name}</text>')
        for x, w, c in clips:
            parts.append(f'<rect x="{x}" y="{y}" width="{w - 8}" height="62" rx="10" fill="{c}" fill-opacity="0.88"/>')
            parts.append(f'<rect x="{x + 10}" y="{y + 10}" width="{min(70, w - 28)}" height="42" rx="6" fill="#0a0a0b" fill-opacity="0.25"/>')
    for name, y, strong in [("A1", 438, True), ("A2", 516, False)]:
        parts.append(f'<text x="712" y="{y + 36}" font-family="{MONO}" font-size="18" fill="#ffffff" fill-opacity="0.45">{name}</text>')
        parts.append(f'<rect x="770" y="{y}" width="726" height="62" rx="10" fill="#3dd6f5" fill-opacity="0.14"/>')
        for x in range(780, 1488, 9):
            h = 6 + 44 * abs(math.sin(x * 0.043 + y) * math.cos(x * 0.011))
            parts.append(f'<rect x="{x}" y="{y + 31 - h / 2:.1f}" width="4" height="{h:.1f}" rx="2" fill="#3dd6f5" fill-opacity="{0.75 if strong else 0.45}"/>')
    # Between two timecodes, so it hides neither.
    playhead = 1287
    parts.append(f'<path d="M{playhead} 238V600" stroke="{LIME}" stroke-width="3"/>')
    parts.append(f'<polygon points="{pts((playhead - 14, 236), (playhead + 14, 236), (playhead + 14, 252), (playhead, 266), (playhead - 14, 252))}" fill="{LIME}"/>')
    cover("editing-premiere", "02", "Монтаж", "Premiere Pro", "Монтаж", "#7c5cff", "\n  ".join(parts))


def camera():
    cx, cy = 1180, 486
    parts = [
        f'<circle cx="{cx}" cy="{cy}" r="266" fill="none" stroke="#ffffff" stroke-opacity="0.07" stroke-width="2"/>',
        f'<circle cx="{cx}" cy="{cy}" r="230" fill="#101013" stroke="#ffffff" stroke-opacity="0.18" stroke-width="2"/>',
    ]
    for i in range(90):
        xa, ya = polar(cx, cy, 228, i * 4)
        xb, yb = polar(cx, cy, 206 if i % 5 == 0 else 217, i * 4)
        parts.append(f'<line x1="{xa:.1f}" y1="{ya:.1f}" x2="{xb:.1f}" y2="{yb:.1f}" stroke="#ffffff" stroke-opacity="{0.4 if i % 5 == 0 else 0.18}" stroke-width="2"/>')
    # f-stops along the upper-left arc only, clear of the tool name at the top right.
    for stop, deg in zip(["1.4", "2", "2.8", "4", "5.6"], range(160, 281, 30)):
        x, y = polar(cx, cy, 296, deg)
        on = stop == "2.8"
        parts.append(f'<text x="{x:.1f}" y="{y + 7:.1f}" text-anchor="middle" font-family="{MONO}" font-size="22" fill="{LIME if on else "#ffffff"}" fill-opacity="{1 if on else 0.4}">{stop}</text>')
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="88" fill="{LIME}" fill-opacity="0.35" filter="url(#soft)"/>')
    blades = 7
    step = 360 / blades
    for k in range(blades):
        a = k * step
        quad = [polar(cx, cy, 76, a), polar(cx, cy, 76, a + step), polar(cx, cy, 196, a + step + 38), polar(cx, cy, 196, a + 14)]
        parts.append(f'<polygon points="{pts(*quad)}" fill="{"#1d1d22" if k % 2 else "#24242a"}" stroke="#ffffff" stroke-opacity="0.22" stroke-width="2" stroke-linejoin="round"/>')
    opening = [polar(cx, cy, 76, k * step) for k in range(blades)]
    parts.append(f'<polygon points="{pts(*opening)}" fill="{LIME}" fill-opacity="0.16" stroke="{LIME}" stroke-width="3"/>')
    cover("camera-basics", "03", "Съёмка", "Камера и смартфон", "Съёмка", "#3dd6f5", "\n  ".join(parts))


def lighting():
    art = f'''<defs>
    <linearGradient id="beam" x1="0.9" y1="0.1" x2="0.2" y2="0.9">
      <stop offset="0" stop-color="#fff6d6" stop-opacity="0.32"/>
      <stop offset="1" stop-color="#fff6d6" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <polygon points="{pts((1250, 400), (1410, 440), (1170, 770), (860, 660))}" fill="url(#beam)"/>
  <g transform="rotate(24 1320 336)">
    <rect x="1180" y="246" width="280" height="180" rx="16" fill="#ffc83d" fill-opacity="0.55" filter="url(#soft)"/>
    <rect x="1180" y="246" width="280" height="180" rx="16" fill="#fffaf0"/>
    <rect x="1192" y="258" width="256" height="156" rx="10" fill="none" stroke="#e8dcc0" stroke-width="3"/>
  </g>
  {label(1496, 520, "KEY")}
  <circle cx="760" cy="320" r="60" fill="#ffffff" fill-opacity="0.2" filter="url(#soft)"/>
  <circle cx="760" cy="320" r="30" fill="#ffffff" fill-opacity="0.55"/>
  {label(730, 392, "FILL")}
  <circle cx="1040" cy="500" r="78" fill="#17171b"/>
  <path d="M870 760 Q1040 580 1210 760 Z" fill="#17171b"/>
  <path d="M1086 430 A78 78 0 0 1 1100 560" fill="none" stroke="{LIME}" stroke-width="6" stroke-linecap="round"/>
  <path d="M1150 660 Q1185 700 1206 756" fill="none" stroke="{LIME}" stroke-width="6" stroke-linecap="round"/>
  {label(1130, 620, "RIM", fill=LIME, opacity=1)}'''
    cover("lighting-video", "04", "Свет", "Трёхточечная схема", "Свет", "#ffc83d", art)


def directing():
    bx, by, bw, bh = 930, 360, 560, 300

    def stripes(top, bottom):
        return "".join(
            f'<polygon points="{pts((bx - 40 + i * 84, bottom), (bx + i * 84, bottom), (bx + 44 + i * 84, top), (bx + 4 + i * 84, top))}" fill="#f5f5f6"/>'
            for i in range(8)
        )

    art = f'''<defs>
    <clipPath id="arm"><rect x="{bx}" y="{by - 70}" width="{bw}" height="70" rx="10"/></clipPath>
    <clipPath id="bar"><rect x="{bx}" y="{by}" width="{bw}" height="56"/></clipPath>
  </defs>
  <rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="20" fill="#141417" stroke="#ffffff" stroke-opacity="0.18" stroke-width="2"/>
  <rect x="{bx}" y="{by}" width="{bw}" height="56" fill="#1d1d22"/>
  <g clip-path="url(#bar)">{stripes(by, by + 56)}</g>
  <g transform="rotate(-13 {bx} {by})">
    <rect x="{bx}" y="{by - 70}" width="{bw}" height="70" rx="10" fill="#1d1d22"/>
    <g clip-path="url(#arm)">{stripes(by - 70, by)}</g>
  </g>
  <circle cx="{bx}" cy="{by}" r="12" fill="#2a2a30" stroke="#ffffff" stroke-opacity="0.3"/>
  <path d="M{bx + 187} {by + 80}V{by + bh - 24}M{bx + 374} {by + 80}V{by + bh - 24}" stroke="#ffffff" stroke-opacity="0.1"/>
  {label(bx + 32, by + 118, "СЦЕНА")}
  {label(bx + 219, by + 118, "ДУБЛЬ")}
  {label(bx + 406, by + 118, "КАМЕРА")}
  <text x="{bx + 30}" y="{by + 222}" font-family="{SANS}" font-size="88" font-weight="700" fill="#ffffff">04</text>
  <text x="{bx + 217}" y="{by + 222}" font-family="{SANS}" font-size="88" font-weight="700" fill="#ffffff">2</text>
  <text x="{bx + 404}" y="{by + 222}" font-family="{SANS}" font-size="88" font-weight="700" fill="{LIME}">A</text>
  <circle cx="{bx + 40}" cy="{by + 262}" r="9" fill="#ff4d4d"/>
  {label(bx + 60, by + 269, "REC", opacity=0.6)}'''
    cover("directing-short", "05", "Режиссура", "Сценарий и площадка", "Режиссура", "#ff4d4d", art, size=196)


def reels():
    # Starts below the header row so the tool name stays readable.
    px, py, pw, ph = 1090, 178, 320, 590
    segments = []
    for i in range(4):
        x = px + 28 + i * 68
        segments.append(f'<rect x="{x}" y="{py + 58}" width="60" height="6" rx="3" fill="#ffffff" fill-opacity="0.25"/>')
        if i < 3:
            segments.append(f'<rect x="{x}" y="{py + 58}" width="{60 if i < 2 else 30}" height="6" rx="3" fill="{LIME}"/>')
    mid = px + pw / 2
    art = f'''<defs>
    <linearGradient id="screen" x1="0" y1="0" x2="0.6" y2="1">
      <stop offset="0" stop-color="#ff3d9a" stop-opacity="0.55"/>
      <stop offset="0.55" stop-color="#7c5cff" stop-opacity="0.35"/>
      <stop offset="1" stop-color="#0a0a0b" stop-opacity="0.9"/>
    </linearGradient>
  </defs>
  <g transform="rotate(-11 910 480)" opacity="0.35">
    <rect x="770" y="220" width="270" height="510" rx="42" fill="#111114" stroke="#ffffff" stroke-opacity="0.35" stroke-width="3"/>
  </g>
  <rect x="{px}" y="{py}" width="{pw}" height="{ph}" rx="48" fill="#111114" stroke="#ffffff" stroke-opacity="0.35" stroke-width="3"/>
  <rect x="{px + 14}" y="{py + 14}" width="{pw - 28}" height="{ph - 28}" rx="36" fill="url(#screen)"/>
  <rect x="{mid - 45}" y="{py + 24}" width="90" height="22" rx="11" fill="#0a0a0b"/>
  {"".join(segments)}
  <circle cx="{mid}" cy="{py + 290}" r="64" fill="#ffffff" fill-opacity="0.14"/>
  <polygon points="{pts((mid - 20, py + 256), (mid - 20, py + 324), (mid + 36, py + 290))}" fill="{LIME}"/>
  <path d="M{px + 272} {py + 396} c-10 -14 -30 -8 -30 8 c0 14 18 24 30 34 c12 -10 30 -20 30 -34 c0 -16 -20 -22 -30 -8z" fill="#ffffff" fill-opacity="0.9"/>
  <text x="{px + 272}" y="{py + 460}" text-anchor="middle" font-family="{MONO}" font-size="16" fill="#ffffff" fill-opacity="0.7">24K</text>
  <circle cx="{px + 272}" cy="{py + 498}" r="16" fill="none" stroke="#ffffff" stroke-opacity="0.9" stroke-width="4"/>
  <rect x="{px + 34}" y="{py + 500}" width="168" height="12" rx="6" fill="#ffffff" fill-opacity="0.6"/>
  <rect x="{px + 34}" y="{py + 526}" width="116" height="12" rx="6" fill="#ffffff" fill-opacity="0.35"/>
  <rect x="830" y="560" width="150" height="54" rx="27" fill="#0a0a0b" stroke="{LIME}" stroke-width="2"/>
  <text x="905" y="595" text-anchor="middle" font-family="{MONO}" font-size="22" fill="{LIME}">+1.2K</text>'''
    cover("instagram-reels", "06", "Контент", "Instagram · CapCut", "Reels", "#ff3d9a", art)


def motion():
    grid = "".join(f'<path d="M780 {y}H1500" stroke="#ffffff" stroke-opacity="0.06" stroke-dasharray="6 10"/>' for y in range(240, 600, 60))
    keys = "".join(
        f'<rect x="{x - 16}" y="{y - 16}" width="32" height="32" transform="rotate(45 {x} {y})" fill="#0a0a0b" stroke="{LIME}" stroke-width="4"/>'
        for x, y in [(800, 580), (1180, 250), (1480, 230)]
    )
    art = f'''<path d="M780 600H1500M780 200V600" stroke="#ffffff" stroke-opacity="0.18" stroke-width="2"/>
  {grid}
  <path d="M800 580 C 980 580, 1010 250, 1180 250 S 1390 560, 1480 230" fill="none" stroke="{LIME}" stroke-width="6" stroke-linecap="round"/>
  <path d="M800 580H960M1180 250H1060M1180 250H1300" stroke="#ffffff" stroke-opacity="0.45" stroke-width="2"/>
  <circle cx="960" cy="580" r="9" fill="#ffffff"/><circle cx="1060" cy="250" r="9" fill="#ffffff"/><circle cx="1300" cy="250" r="9" fill="#ffffff"/>
  {keys}'''
    cover("motion-after-effects", "07", "Моушн", "After Effects", "Моушн", LIME, art)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for draw in (color_grading, editing, camera, lighting, directing, reels, motion):
        draw()
    print("wrote", ", ".join(sorted(p.name for p in OUT.glob("*.svg"))))
