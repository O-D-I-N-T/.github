"""Animated ODINT logo GIFs: the master seal and the lockup, built up by a short reveal.

The logo files are odint.io's own (public/assets/logo/odint-mark.svg and odint-lockup.svg, read by
make_art.py), rendered as <img> the way the site loads them. The motion follows DESIGN.md
("short reveals ... no continuous logo spin") and DESIGN_SYSTEM.md (never red, metallic, shadows,
gradients or ongoing rotation): the rings are drawn clockwise from twelve o'clock, the eight points
stamp in, cardinals first, then the centre; on the lockup the wordmark is uncovered left to right.
Every change is a hard edge, never a fade. Frame 0 is the complete logo, identical to the static
artwork, so anything that shows only the first frame shows the real mark.

    py -3.13 scripts/make_logo_gif.py [--out DIR]
"""
import argparse, io, math, re
from pathlib import Path
from PIL import Image, ImageChops, ImageSequence
from playwright.sync_api import sync_playwright
from make_art import BLACK, GL, HERE, LOCKUP, MARK, WHITE, img, inverse

ORDER = [0, 2, 4, 6, 1, 3, 5, 7]       # star tips clockwise from north: N E S W, then NE SE SW NW
HOLD, BLANK, STEP, STAMP = 2800, 400, 40, 100   # ms
SEAL, LOCK_W, LOCK_PAD = 1024, 1200, 96         # px
WORD = [110.0, 360.0]   # wordmark extent in lockup units; measured from the rendered lockup in make()


def wedge(theta, r=60):
    """Clockwise from twelve o'clock through theta degrees, around the seal centre (50, 50)."""
    n = max(2, math.ceil(theta / 3))
    arc = ' '.join(f'L{50 + r * math.sin(math.radians(theta * i / n)):.2f} '
                   f'{50 - r * math.cos(math.radians(theta * i / n)):.2f}' for i in range(n + 1))
    return f'M50 50 {arc} Z'


def kites(star_d, tips):
    """The star outline split at its inner vertices: one kite (centre, inner, tip, inner) per tip."""
    v = list(zip(*[iter(map(float, re.findall(r'-?[\d.]+', star_d)))] * 2))   # tip, inner, tip, inner ...
    out = []
    for k in tips:
        a, t, b = v[(2 * k - 1) % 16], v[2 * k], v[2 * k + 1]
        out.append(f'M50 50 L{a[0]:g} {a[1]:g} L{t[0]:g} {t[1]:g} L{b[0]:g} {b[1]:g} Z')
    return ' '.join(out)


def seal_state(rings, points, centre):
    """odint-mark.svg part-built: rings swept to `rings` degrees, the first `points` of its eight points."""
    if rings >= 360 and points == 8 and centre:
        return MARK
    ring_g, point_g, facet_g = re.findall(r'<g\b[^>]*>.*?</g>', MARK, re.S)
    head = MARK[:MARK.index(ring_g)]
    dot = re.search(r'<circle cx="50" cy="50" r="4\.6"[^>]*/>', MARK).group(0)

    def first(group, n):        # the file lists points and facets N E S W NE SE SW NW
        return re.match(r'<g\b[^>]*>', group).group(0) + ''.join(re.findall(r'<path\b[^>]*/>', group)[:n]) + '</g>'

    defs = ''
    if rings <= 0:
        ring_g = ''
    elif rings < 360:
        defs = f'<defs><clipPath id="sweep"><path d="{wedge(rings)}"/></clipPath></defs>'
        ring_g = ring_g.replace('<g ', '<g clip-path="url(#sweep)" ', 1)
    return head + defs + ring_g + first(point_g, points) + first(facet_g, points) + (dot if centre else '') + '</svg>'


def lockup_state(rings, points, centre, word):
    """odint-lockup.svg part-built; its star is one path, so points are uncovered by kite clips."""
    if rings >= 360 and points == 8 and centre and word >= 1:
        return LOCKUP
    ring_g = re.search(r'<g fill="none"[^>]*>.*?</g>', LOCKUP, re.S).group(0)
    star = re.search(r'<path fill="#000" d="([^"]*)"/>', LOCKUP)
    facets = re.search(r'<path fill="#777"[^>]*/>', LOCKUP).group(0)
    dot = re.search(r'<circle cx="50" cy="50" r="4\.6"[^>]*/>', LOCKUP).group(0)
    text = re.search(r'<text\b.*?</text>', LOCKUP, re.S).group(0)
    head = LOCKUP[:LOCKUP.index('<g')]
    defs = []
    if rings <= 0:
        ring_g = ''
    elif rings < 360:
        defs.append(f'<clipPath id="sweep"><path d="{wedge(rings)}"/></clipPath>')
        ring_g = ring_g.replace('<g ', '<g clip-path="url(#sweep)" ', 1)
    if points <= 0:
        mark = ''
    elif points < 8:
        defs.append(f'<clipPath id="points"><path d="{kites(star.group(1), ORDER[:points])}"/></clipPath>')
        mark = f'<g clip-path="url(#points)">{star.group(0)}{facets}</g>'
    else:
        mark = star.group(0) + facets
    if word <= 0:
        text = ''
    elif word < 1:
        left, right = WORD
        defs.append(f'<clipPath id="wipe"><rect x="{left:.2f}" y="0" width="{(right - left) * word:.2f}" height="100"/></clipPath>')
        text = f'<g clip-path="url(#wipe)">{text}</g>'
    seal = f'<g>{ring_g}{mark}{dot if centre else ""}</g>'
    return head + (f'<defs>{"".join(defs)}</defs>' if defs else '') + seal + text + '</svg>'


def timeline(lockup):
    """(state, ms) pairs. Frame 0 is the finished logo; the reveal ends one step before it, so the loop closes."""
    done = dict(rings=360, points=8, centre=True, word=1.0)
    t = [(done, HOLD), (dict(done, rings=0, points=0, centre=False, word=0.0), BLANK)]
    t += [(dict(done, rings=360 * i / 12, points=0, centre=False, word=0.0), STEP) for i in range(1, 13)]
    t += [(dict(done, points=n, centre=False, word=0.0), STAMP) for n in range(1, 9)]
    if lockup:
        t.append((dict(done, word=0.0), STAMP))
        t += [(dict(done, word=i / 12), STEP) for i in range(1, 12)]
    return t


def page_html(svg, ground, w, h, pad, fit):
    """The same box make_art.avatar() draws: ground colour, padding, the logo as <img>."""
    bg = BLACK if ground == 'black' else WHITE
    return ('<!doctype html><html><head><meta charset="utf-8"><style>'
            f'*{{box-sizing:border-box;margin:0;padding:0}} html,body{{width:{w}px;height:{h}px;background:transparent;overflow:hidden}}'
            f'</style></head><body><div style="width:{w}px;height:{h}px;background:{bg};padding:{pad}px">'
            f'{img(svg, fit)}</div></body></html>')


def render(page, svg, ground, w, h, pad, fit):
    page.set_viewport_size({'width': w, 'height': h})
    page.set_content(page_html(inverse(svg) if ground == 'black' else svg, ground, w, h, pad, fit), wait_until='load')
    page.evaluate('Promise.all([...document.images].map(i => i.decode()))')
    return Image.open(io.BytesIO(page.screenshot(clip={'x': 0, 'y': 0, 'width': w, 'height': h}))).convert('L')


def make(page, kind, ground, out):
    lockup = kind == 'lockup'
    if lockup:
        w = LOCK_W
        h = round((LOCK_W - 2 * LOCK_PAD) * 100 / 360) + 2 * LOCK_PAD
        pad, fit = LOCK_PAD, 'width:100%;height:auto;display:block'
    else:
        w = h = SEAL
        pad, fit = round(SEAL * 0.12), 'width:100%;height:100%;display:block'     # 12% avatar margin
    steps = timeline(lockup)
    still = render(page, LOCKUP if lockup else MARK, ground, w, h, pad, fit)   # warm-up: a first paint at a new size differs slightly
    if lockup:      # the wipe runs exactly across the word as the site's font draws it
        scale = (w - 2 * pad) / 360
        ink = still.point(lambda v: 255 if abs(v - (0 if ground == 'black' else 255)) > 24 else 0)
        box = ink.crop((round(pad + 105 * scale), 0, w, h)).getbbox()
        WORD[:] = [(box[0] + round(105 * scale)) / scale - 1, (box[2] + round(105 * scale)) / scale + 1]
    frames = [render(page, (lockup_state if lockup else seal_state)(**{k: v for k, v in s.items()
              if lockup or k != 'word'}), ground, w, h, pad, fit) for s, _ in steps]
    part = out.with_name(out.stem + '.partial.gif')
    # optimize=False: Pillow's palette optimisation let the logo show through the blank frame on decode.
    frames[0].save(part, save_all=True, append_images=frames[1:], duration=[ms for _, ms in steps], loop=0,
                   optimize=False)
    # The saved GIF must decode to exactly what was drawn before it replaces anything.
    shown = [f.convert('L') for f in ImageSequence.Iterator(Image.open(part))]
    assert len(shown) == len(frames) and all(not ImageChops.difference(a, b).getbbox() for a, b in zip(shown, frames)), \
        f'{out.name}: decoded frames differ'
    part.replace(out)
    report = {'file': out.name, 'size': [w, h], 'frames': len(frames), 'seconds': sum(ms for _, ms in steps) / 1000,
              'bytes': out.stat().st_size}
    if not lockup:      # frame 0 against the published avatar make_art.py drew from the same file
        avatar = HERE / 'brand' / '01-profile-icon' / f'odint-avatar-{ground}-{SEAL}.png'
        if avatar.exists():
            diff = ImageChops.difference(frames[0], Image.open(avatar).convert('L'))
            report['frame0_vs_published_avatar_maxdiff'] = diff.getextrema()[1]
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=Path(r'D:\32 Logo Library\ODINT Logos'))
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=GL)
        page = browser.new_page()
        for kind in ('seal', 'lockup'):
            for ground in ('black', 'white'):
                print(make(page, kind, ground, a.out / f'odint-{kind}-reveal-{ground}.gif'))
        browser.close()


if __name__ == '__main__':
    main()
