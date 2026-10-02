"""Render the O.D.I.N.T. org art and README media from the odint.io source.

Source of truth: D:/03 Website Library/ODINT.io (the live site's repo) and its signed design system
(ODINT_Claude_Handoff/DESIGN_SYSTEM.md, SOCIAL_SYSTEM.md, DESIGN.md):
  - master seal = ring + eight points + grey facets; positive black/grey on white, inverse white/grey on black
  - avatars keep a 12% safe margin; never red, metallic, shadowed, gradient or rotating on the logo
  - six colours only; carmine #A1121A marks map markers and nothing else; #CC0000 is retired
Everything renders offline in headless Chromium: requests for https://odint.io/ are answered from the local
public/ folder and every other host is refused. Nothing is fetched from the live site.

    py -3.13 scripts/make_art.py
"""
import base64, hashlib, io, json, mimetypes, pathlib, re, shutil, urllib.parse
from PIL import Image
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parents[1]
OUT = HERE / 'brand'
ASSETS = HERE / 'profile' / 'assets'
README = HERE / 'profile' / 'README.md'
SITE = pathlib.Path(r'D:\03 Website Library\ODINT.io')
PUB = SITE / 'public'

WHITE, BLACK, PALE, CARMINE = '#ffffff', '#000000', '#eeeae2', '#a1121a'
EDITORIAL = "Georgia, 'Times New Roman', serif"
RECORD = "ui-monospace, 'Courier New', monospace"
NAME = 'Observatory for Digital Infrastructure and Network Transparency'
LINE = 'Follow the evidence.'
GL = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']
mimetypes.add_type('text/javascript', '.mjs')
mimetypes.add_type('image/webp', '.webp')


def clean(svg):
    svg = re.sub(r'<title[^>]*>.*?</title>', '', svg, flags=re.S)
    return re.sub(r'\s(role|aria-labelledby)="[^"]*"', '', svg)


def inverse(svg):
    """Positive (black/grey on white) -> inverse (white/grey on black). Grey facets stay grey."""
    return svg.replace('"#000"', '"@K"').replace('"#fff"', '"#000"').replace('"@K"', '"#fff"')


MARK = clean((PUB / 'assets' / 'logo' / 'odint-mark.svg').read_text(encoding='utf-8'))
LOCKUP = clean((PUB / 'assets' / 'logo' / 'odint-lockup.svg').read_text(encoding='utf-8'))
ATLAS = re.search(r'<svg[^>]*class="atlas"[^>]*>.*?</svg>',
                  (PUB / 'index.html').read_text(encoding='utf-8'), re.S).group(0)
ATLAS = re.sub(r'<title>.*?</title>', '', ATLAS).replace('viewbox=', 'viewBox=')   # 84N..60S, the site's own crop


def sized(svg, css):
    return svg.replace('<svg ', f'<svg style="{css}" ', 1)


def img(svg, css):
    """Logo as <img>, the way the site's header loads it (inline SVG text resolves fonts differently)."""
    return f'<img style="{css}" src="data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}">'


def doc(body, w, h, bg='transparent'):
    return ('<!doctype html><html><head><meta charset="utf-8"><style>'
            f'*{{box-sizing:border-box;margin:0;padding:0}} html,body{{width:{w}px;height:{h}px;background:{bg};overflow:hidden}}'
            f'</style></head><body>{body}</body></html>')


def shot(page, html, w, h, out, transparent=False):
    page.set_viewport_size({'width': w, 'height': h})
    page.set_content(html, wait_until='load')
    out.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(out), omit_background=transparent, clip={'x': 0, 'y': 0, 'width': w, 'height': h})
    return out


def avatar(ground, size=1024):
    ink = inverse(MARK) if ground == 'black' else MARK
    pad = round(size * 0.12)
    bg = BLACK if ground == 'black' else WHITE
    body = (f'<div style="width:{size}px;height:{size}px;background:{bg};padding:{pad}px">'
            f'{img(ink, "width:100%;height:100%;display:block")}</div>')
    return doc(body, size, size)


def atlas(ground):
    """The site's own atlas: Natural Earth land, one carmine marker per country with a published investigation."""
    stroke = 'stroke:#000;stroke-width:.45;vector-effect:non-scaling-stroke' if ground == 'white' else 'stroke:none'
    ring = WHITE if ground == 'black' else BLACK
    css = (f'<style>.atlas__land path{{fill:{PALE};{stroke}}}'
           f'.atlas__marker circle{{fill:{CARMINE};stroke:{ring};stroke-width:1.6;r:5.5}}</style>')
    return css + sized(ATLAS, 'width:100%;height:auto;display:block')


def plate(ground, w, h, scale=1.0, captions=True):
    """Two fields with a hard edge: text field (lockup, editorial line, record lines) | evidence field (atlas)."""
    fg, bg = (WHITE, BLACK) if ground == 'black' else (BLACK, WHITE)
    lock = inverse(LOCKUP) if ground == 'black' else LOCKUP
    s = scale
    rule = max(1, round(2 * s))
    meta = f'font:400 {round(21 * s)}px/1.35 {RECORD};letter-spacing:.04em;text-transform:uppercase'
    top = f'<div style="{meta};margin-bottom:{round(22 * s)}px">ODINT / Interactive world atlas</div>' if captions else ''
    foot = (f'<div style="{meta};margin-top:{round(22 * s)}px">One marker per country with a published investigation</div>'
            if captions else '')
    body = f'''
<div style="display:grid;grid-template-columns:47% 53%;width:{w}px;height:{h}px;background:{bg};color:{fg}">
  <div style="display:flex;flex-direction:column;justify-content:center;padding:0 {round(64 * s)}px 0 {round(110 * s)}px">
    {img(lock, f"width:{round(660 * s)}px;height:auto;display:block")}
    <div style="height:{rule}px;background:{fg};width:{round(660 * s)}px;margin:{round(34 * s)}px 0"></div>
    <div style="font:400 {round(88 * s)}px/1.01 {EDITORIAL};letter-spacing:-.035em">{LINE}</div>
    <div style="{meta};margin-top:{round(34 * s)}px;max-width:{round(700 * s)}px">{NAME}</div>
    <div style="{meta};margin-top:{round(16 * s)}px;font-weight:700">odint.io</div>
  </div>
  <div style="border-left:{rule}px solid {fg};display:flex;flex-direction:column;justify-content:center;padding:0 {round(150 * s)}px">
    {top}{atlas(ground)}{foot}
  </div>
</div>'''
    return doc(body, w, h, bg)


def route_offline(page):
    def handle(route):
        u = urllib.parse.urlsplit(route.request.url)
        if u.netloc != 'odint.io':
            return route.abort()
        p = urllib.parse.unquote(u.path)
        f = PUB / p.lstrip('/')
        if p.endswith('/') or f.is_dir():
            f = f / 'index.html'
        if not f.exists():
            return route.fulfill(status=404, body='')
        ctype = mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
        route.fulfill(status=200, path=str(f), headers={'content-type': ctype})
    page.route('**/*', handle)


def screenshots(browser, made):
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    route_offline(page)
    for name, path in (('home', '/'), ('atlas', '/atlas/')):
        page.goto('https://odint.io' + path, wait_until='domcontentloaded')
        page.wait_for_timeout(3000)
        out = OUT / '05-screenshots' / f'odint-{name}-1440.png'
        out.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out))
        made.append(out)
    page.close()


def globe_loop(browser, made, frames=60, size=540):
    page = browser.new_page(viewport={'width': 1600, 'height': 1100})
    route_offline(page)
    page.goto('https://odint.io/', wait_until='domcontentloaded')
    page.wait_for_function('window.odintAtlas && window.odintAtlas.ready && window.odintAtlas.map', timeout=90000)
    page.add_style_tag(content='.globe-controls,.globe-coordinate,#globe-status,.globe-route-panel,.maplibregl-ctrl,'
                               '.maplibregl-ctrl-attrib,.globe-hint{display:none!important}')
    globe = page.locator('#odint-globe')
    globe.scroll_into_view_if_needed()
    tiles = []
    for i in range(frames):
        page.evaluate('''lng => new Promise(done => {
            const m = window.odintAtlas.map; m.stop();
            m.jumpTo({center:[lng, 14], bearing:0, pitch:0});
            m.once('idle', () => done()); m.triggerRepaint(); setTimeout(done, 4000); })''', -100 + i * 360 / frames)
        im = Image.open(io.BytesIO(globe.screenshot())).convert('RGB')
        side = min(im.size)
        im = im.crop(((im.width - side) // 2, (im.height - side) // 2, (im.width + side) // 2, (im.height + side) // 2))
        tiles.append(im.resize((size, size), Image.LANCZOS))
    page.close()
    out = OUT / '06-globe' / 'odint-atlas-globe.gif'
    still = OUT / '06-globe' / 'odint-atlas-globe-still.png'
    out.parent.mkdir(parents=True, exist_ok=True)
    pal = [t.quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE) for t in tiles]
    pal[0].save(out, save_all=True, append_images=pal[1:], duration=90, loop=0, optimize=True, disposal=1)
    tiles[0].save(still, optimize=True)
    made += [out, still]


def featured(made, count=4):
    """The investigations the live homepage features, in its order, with their editorial photographs."""
    html = (PUB / 'index.html').read_text(encoding='utf-8')
    records = json.loads((PUB / 'archive.json').read_text(encoding='utf-8'))['records']
    by_thumb = {r['editorialThumb']: r for r in records if r.get('editorialThumb')}
    picks, seen = [], set()
    for thumb in re.findall(r'<img src="(/media/editorial/thumbs/[^"]+)"', html):
        r = by_thumb.get(thumb)
        if r and r['publicationStatus'] == 'published' and r['route'] not in seen:
            seen.add(r['route'])
            picks.append(r)
        if len(picks) == count:
            break
    rows = []
    for r in picks:
        out = ASSETS / f"inv-{r['slug']}.jpg"
        out.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(PUB / r['editorialThumb'].lstrip('/')).convert('RGB')
        im.resize((480, round(im.height * 480 / im.width)), Image.LANCZOS).save(out, quality=86, optimize=True, progressive=True)
        made.append(out)
        rows.append({'route': r['route'], 'title': r['title'], 'date': r['publishedAt'], 'id': r['id'],
                     'country': r['country'], 'file': out.name})
    (OUT / 'featured.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')
    return rows


def publish_readme_media():
    """Copy README media into profile/assets under content-hashed names and relink profile/README.md
    (GitHub's image proxy caches by URL, so a changed image needs a new name)."""
    pairs = {'banner-dark': OUT / '03-banner' / 'odint-banner-black.png',
             'banner-light': OUT / '03-banner' / 'odint-banner-white.png',
             'globe': OUT / '06-globe' / 'odint-atlas-globe.gif',
             'home': OUT / '05-screenshots' / 'odint-home-1440.png',
             'atlas': OUT / '05-screenshots' / 'odint-atlas-1440.png',
             'lockup-dark': OUT / '02-logo' / 'odint-lockup-inverse-512.png',
             'lockup-light': OUT / '02-logo' / 'odint-lockup-positive-512.png'}
    text = README.read_text(encoding='utf-8') if README.exists() else ''
    for tag, src in pairs.items():
        sha = hashlib.sha1(src.read_bytes()).hexdigest()[:8]
        dst = ASSETS / f'{tag}-{sha}{src.suffix}'
        for old in ASSETS.glob(f'{tag}-*{src.suffix}'):
            if old != dst and re.fullmatch(rf'{tag}-[0-9a-f]{{8}}{re.escape(src.suffix)}', old.name):
                old.unlink()
        shutil.copyfile(src, dst)
        text = re.sub(rf'{tag}-[0-9a-f]{{8}}{re.escape(src.suffix)}', dst.name, text)
    if README.exists():
        README.write_text(text, encoding='utf-8', newline='\n')


def featured_block(rows):
    """README strip: the homepage's featured investigations, photo + record line + title, linked to odint.io."""
    raw = 'https://github.com/O-D-I-N-T/.github/raw/main/profile/assets/'
    months = 'JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC'.split()
    cells = []
    for r in rows:
        y, m, d = r['date'].split('-')
        url = 'https://odint.io' + r['route']
        cells.append(f'<td width="{100 // len(rows)}%" valign="top"><a href="{url}"><img src="{raw}{r["file"]}" width="100%" '
                     f'alt="Editorial photograph for {r["title"]}"></a><br><sub><code>{r["id"]} · {d} {months[int(m) - 1]} {y}'
                     f'</code></sub><br><a href="{url}"><b>{r["title"]}</b></a></td>')
    return '<table>\n<tr>\n' + '\n'.join(cells) + '\n</tr>\n</table>'


def splice_featured(rows):
    if not README.exists():
        return
    text = README.read_text(encoding='utf-8')
    text = re.sub(r'(<!-- featured:start -->).*?(<!-- featured:end -->)',
                  lambda m: m.group(1) + '\n' + featured_block(rows) + '\n' + m.group(2), text, flags=re.S)
    README.write_text(text, encoding='utf-8', newline='\n')


def main():
    made = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=GL)
        page = browser.new_page()
        for g in ('black', 'white'):
            big = shot(page, avatar(g), 1024, 1024, OUT / '01-profile-icon' / f'odint-avatar-{g}-1024.png')
            made.append(big)
            for s in (512, 460, 256, 128, 64):
                out = OUT / '01-profile-icon' / f'odint-avatar-{g}-{s}.png'
                Image.open(big).resize((s, s), Image.LANCZOS).save(out, optimize=True)
                made.append(out)
            ink = 'inverse' if g == 'black' else 'positive'
            mark = inverse(MARK) if g == 'black' else MARK
            lock = inverse(LOCKUP) if g == 'black' else LOCKUP
            for wd in (2048, 1024, 512):
                lh = round(wd * 100 / 360)
                made.append(shot(page, doc(img(lock, f'width:{wd}px;height:auto;display:block'), wd, lh),
                                 wd, lh, OUT / '02-logo' / f'odint-lockup-{ink}-{wd}.png', transparent=True))
                made.append(shot(page, doc(img(mark, f'width:{wd}px;height:{wd}px;display:block'), wd, wd),
                                 wd, wd, OUT / '02-logo' / f'odint-seal-{ink}-{wd}.png', transparent=True))
            made.append(shot(page, plate(g, 2560, 720), 2560, 720, OUT / '03-banner' / f'odint-banner-{g}.png'))
            made.append(shot(page, plate(g, 1280, 640, scale=0.62), 1280, 640,
                             OUT / '04-social-preview' / f'odint-social-{g}-1280x640.png'))
        page.close()
        screenshots(browser, made)
        globe_loop(browser, made)
        browser.close()
    for name, svg in (('odint-seal-positive.svg', MARK), ('odint-seal-inverse.svg', inverse(MARK)),
                      ('odint-lockup-positive.svg', LOCKUP), ('odint-lockup-inverse.svg', inverse(LOCKUP))):
        (OUT / '02-logo' / name).write_text(svg, encoding='utf-8', newline='\n')
    splice_featured(featured(made))
    publish_readme_media()
    print(f'{len(made)} files under {OUT} and {ASSETS}')


if __name__ == '__main__':
    main()
