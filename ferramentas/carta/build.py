"""Monta a carta náutica de 1778 (SVG em metros) a partir da geografia do Atlas de Gemini."""
from geo import *
from scipy import ndimage as ndi
from skimage import measure
import base64, io, math, json
from PIL import Image

land0 = np.load('land.npy') > 0
isl = np.load('isl.npy') > 0
LAND = land0 | isl
H = np.load('H.npy')
dsea = ndi.distance_transform_edt(~LAND) * RES
dland = ndi.distance_transform_edt(LAND) * RES

def on(x, y):
    r, c = int((y - Y0) / RES), int((x - X0) / RES)
    if r < 0 or c < 0 or r >= NY or c >= NX: return False
    return bool(LAND[r, c])

def f(v): return str(int(round(v)))
def pd(pts, close=False):
    s = 'M' + ' L'.join(f(x) + ' ' + f(y) for x, y in pts)
    return s + ('Z' if close else '')
def px2w(c):  # (row,col) array -> world (x,y)
    return np.c_[X0 + c[:, 1] * RES, Y0 + c[:, 0] * RES]

def contours_world(field, level, eps=1.2, minlen=8, sigma=None):
    A = ndi.gaussian_filter(field, sigma) if sigma else field
    out = []
    for c in measure.find_contours(A, level):
        if len(c) < minlen: continue
        a = np.round(c[:, ::-1] * 4).astype(np.int32).reshape(-1, 1, 2)
        a = cv2.approxPolyDP(a, eps * 4, False).reshape(-1, 2) / 4.0
        out.append(px2w(a[:, ::-1]))
    return out

def chaikin(pts, n=3):
    p = np.array(pts, float)
    for _ in range(n):
        q = 0.75 * p[:-1] + 0.25 * p[1:]; r = 0.25 * p[:-1] + 0.75 * p[1:]
        p = np.vstack([p[:1], np.column_stack([q, r]).reshape(-1, 2), p[-1:]])
    return p

G = json.load(open('geo_raw.json'))
out = []  # svg chunks
rng = np.random.default_rng(1778)

# ---------------- extents
FX0, FY0, FX1, FY1 = X0, Y0, X0 + W, Y0 + H.shape[0] * 0 + 40500.0
BAND = 700.0  # graduated border band
VB = (FX0 - 2700, FY0 - 2700, (FX1 - FX0) + 5400, (FY1 - FY0) + 5900)

# ---------------- paper texture (jpeg pattern)
def paper_png():
    n = 640
    a = np.zeros((n, n), np.float32)
    for s, w in [(1, .25), (3, .35), (9, .5), (30, .8)]:
        z = ndi.gaussian_filter(rng.standard_normal((n, n)).astype(np.float32), s, mode='wrap')
        a += w * z / z.std()
    a = (a - a.min()) / (a.max() - a.min())
    base = np.array([236, 222, 188], np.float32); dark = np.array([214, 192, 148], np.float32)
    img = base[None, None, :] * (1 - a[..., None] * 0.55) + dark[None, None, :] * (a[..., None] * 0.55)
    fib = ndi.gaussian_filter(rng.standard_normal((n, n)).astype(np.float32), (0.6, 6), mode='wrap')
    img += (fib / fib.std() * 2.2)[..., None]
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    b = io.BytesIO(); im.save(b, 'JPEG', quality=72)
    return base64.b64encode(b.getvalue()).decode()
PAPER = paper_png()

# ---------------- defs
TREE = '<g id="tree"><path d="M0 -38 C28 -38 34 -6 18 4 C32 18 6 28 0 22 C-8 30 -32 18 -20 4 C-34 -6 -24 -38 0 -38Z" class="tr"/><path d="M0 18 L0 44" class="trk"/></g>'
ANCHOR = '<g id="anchor"><circle cy="-120" r="28" class="ank"/><path d="M0 -92 V120 M-70 -50 H70 M-120 40 C-110 120 -40 140 0 120 C40 140 110 120 120 40 M-120 40 l-30 30 M120 40 l30 30" class="ank"/></g>'
CROSS = '<path id="grave" d="M0 -26 V26 M-14 -10 H14" class="grv"/>'
out.append(f'''<defs>
<pattern id="paper" patternUnits="userSpaceOnUse" width="5200" height="5200"><image href="data:image/jpeg;base64,{PAPER}" width="5200" height="5200" preserveAspectRatio="none"/></pattern>
<radialGradient id="vign" cx="50%" cy="48%" r="72%"><stop offset="60%" stop-color="#7a5a2c" stop-opacity="0"/><stop offset="100%" stop-color="#6b4a1e" stop-opacity=".28"/></radialGradient>
{TREE}{ANCHOR}{CROSS}
<clipPath id="cFrame"><rect x="{f(FX0)}" y="{f(FY0)}" width="{f(FX1-FX0)}" height="{f(FY1-FY0)}"/></clipPath>
''')

# land path (vector, from Atlas) — without the modern container-terminal fill
LAND_D = G['land'][0]
ISL_D = G['island'][0]
out.append(f'<clipPath id="cSea"><path clip-rule="evenodd" d="M{f(FX0)} {f(FY0)}H{f(FX1)}V{f(FY1)}H{f(FX0)}Z {LAND_D} {ISL_D}"/></clipPath>')
out.append(f'<clipPath id="cLand"><path d="{LAND_D} {ISL_D}"/></clipPath>')
out.append('</defs>')

# ---------------- paper
out.append(f'<rect x="{f(VB[0])}" y="{f(VB[1])}" width="{f(VB[2])}" height="{f(VB[3])}" fill="url(#paper)"/>')

body = []  # inside frame clip
# coastal sea ribbon (hand-coloured tint)
for w, o in [(900, .07), (560, .08), (300, .10), (130, .12)]:
    body.append(f'<path d="{LAND_D} {ISL_D}" class="ribbon" style="stroke-width:{w};stroke-opacity:{o}"/>')

# ---------------- depth model & soundings
yy, xx = np.mgrid[0:NY, 0:NX].astype(np.float32)
WX = X0 + xx * RES; WY = Y0 + yy * RES
bay = ((WX > 6500) & (WX < 16200) & (WY > 13200) & (WY < 26600)).astype(np.float32)
bay = ndi.gaussian_filter(bay, 90)
outer = 2 + 26 * (1 - np.exp(-dsea / 2200)) + dsea / 240
inner = 1.5 + 8.5 * (1 - np.exp(-dsea / 650))
depth = inner * bay + outer * (1 - bay)
depth += 6 * np.exp(-(((WX - 16900) ** 2) / (2 * 900 ** 2) + ((WY - 19700) ** 2) / (2 * 700 ** 2)))  # Narrows channel
depth += ndi.gaussian_filter(rng.standard_normal((NY, NX)).astype(np.float32), 60) * 40
depth[LAND] = 0
del yy, xx

def dget(x, y):
    r, c = int((y - Y0) / RES), int((x - X0) / RES)
    return float(depth[r, c]), float(dsea[r, c])

# exclusion boxes in sea (labels, ornaments) x0,y0,x1,y1
EXCL = [(22900, -1300, 36300, 8100),  # cartouche
        (26600, 30300, 34600, 38700),  # rose
        (21000, 34300, 25700, 37200),  # remarks
        (10000, 37300, 22600, 39000),   # scale
        (22600, 15300, 35600, 16900),  # ocean label
        (7600, 20300, 15200, 21800),   # bay label
        (13900, 19100, 17800, 20450),  # narrows label + ferry
        (27100, 11400, 30700, 13900),  # gull island
        (22600, 9300, 25400, 11800),   # small rose
        (31500, 18500, 36800, 20400),  # no ground note
        (11900, -200, 13700, 350), (11700, 900, 14300, 1450), (14000, 400, 16200, 1300)]
def excluded(x, y, pad=0):
    return any(a - pad <= x <= c + pad and b - pad <= y <= d + pad for a, b, c, d in EXCL)

sound = []
for gx in np.arange(FX0 + 300, FX1 - 300, 820):
    for gy in np.arange(FY0 + 300, FY1 - 300, 820):
        x = gx + rng.uniform(-260, 260); y = gy + rng.uniform(-260, 260)
        if on(x, y) or excluded(x, y, 120): continue
        dp, ds = dget(x, y)
        if ds < 160: continue
        if ds > 9500: continue
        sound.append((x, y, dp))
# extra soundings near coast in bay / narrows
for gx in np.arange(6500, 21000, 520):
    for gy in np.arange(13000, 26500, 520):
        x = gx + rng.uniform(-200, 200); y = gy + rng.uniform(-200, 200)
        if on(x, y) or excluded(x, y, 120): continue
        dp, ds = dget(x, y)
        if ds < 140 or ds > 1600: continue
        if any((x - a) ** 2 + (y - b) ** 2 < 430 ** 2 for a, b, _ in sound): continue
        sound.append((x, y, dp))
def fmt_f(d):
    if d < 6:
        h = round(d * 2) / 2
        return (str(int(h)) + ('½' if h % 1 else '')) if h >= 1 else '½'
    return str(int(round(d)))
snd = ''.join(f'<text x="{f(x)}" y="{f(y)}">{fmt_f(d)}</text>' for x, y, d in sound)

# shoal line (3 fathoms) & water lines
shoal = contours_world(np.where(LAND, 0, depth), 3.0, eps=1.5, minlen=20, sigma=2)
shoal = [c for c in shoal if np.hypot(*(c[0] - c[-1])) > 0 or len(c) > 30]
wl = []
for dist in (45, 110, 200, 320):
    wl += contours_world(dsea, dist, eps=1.3, minlen=12, sigma=1.5)

# ---------------- rhumb lines (two roses)
ROSES = [(30600, 34500, 3000), (24000, 10550, 1050)]
rh_major, rh_minor = [], []
for cx, cy, R in ROSES:
    for k in range(32):
        a = math.radians(k * 11.25)
        x1, y1 = cx + math.sin(a) * 62000, cy - math.cos(a) * 62000
        x0, y0 = cx + math.sin(a) * R * 1.02, cy - math.cos(a) * R * 1.02
        (rh_major if k % 4 == 0 else rh_minor).append(f'M{f(x0)} {f(y0)}L{f(x1)} {f(y1)}')
body.append('<g id="lyr-rhumb" class="lyr" clip-path="url(#cSea)">'
            f'<path d="{"".join(rh_minor)}" class="rh"/><path d="{"".join(rh_major)}" class="rh rhM"/></g>')
body.append('<g class="lyr" id="lyr-water" clip-path="url(#cSea)">' + ''.join(f'<path d="{pd(c)}" class="wl"/>' for c in wl) + '</g>')
body.append('<g class="lyr" id="lyr-snd">' + ''.join(f'<path d="{pd(c)}" class="shoal"/>' for c in shoal)
            + f'<g class="snd">{snd}</g>'
            + '<text x="34200" y="19300" class="note-i" text-anchor="middle">Sem fundo</text><text x="34200" y="19780" class="note-i" text-anchor="middle">a 90 braças</text></g>')

# ---------------- land
body.append(f'<path d="{LAND_D} {ISL_D}" class="land"/>')
# inland wash (ochre-green ribbon inside land)
body.append(f'<g clip-path="url(#cLand)">' + ''.join(
    f'<path d="{LAND_D} {ISL_D}" class="lwash" style="stroke-width:{w};stroke-opacity:{o}"/>' for w, o in [(1300, .10), (700, .12), (300, .14)]) + '</g>')

# beaches stipple (Atlas sand band)
SAND = G['sandband'][0]
body.append(f'<g clip-path="url(#cLand)" class="lyr" id="lyr-sand"><path d="{SAND}" class="sd1"/><path d="{SAND}" class="sd2"/></g>')

# ---------------- hachures
hz = np.load('hach.npz')
st, m1, m2, en, sl = hz['start'], hz['mid1'], hz['mid2'], hz['end'], hz['slope']
W_ = np.clip(4 + sl * 24, 4, 22)
classes = [4, 6, 8.5, 11.5, 15, 19, 22]
buckets = {c: [] for c in classes}
for i in range(len(st)):
    pts = [st[i], m1[i], m2[i], en[i]]
    pts = [p for j, p in enumerate(pts) if j == 0 or np.hypot(*(p - pts[j - 1])) > 0.3]
    if len(pts) < 2: continue
    w = px2w(np.array(pts))
    # shorten a little so strokes read as separate ticks
    cls = min(classes, key=lambda c: abs(c - W_[i]))
    buckets[cls].append(pd(w))
body.append('<g class="lyr" id="lyr-relief">' + ''.join(
    f'<path d="{"".join(v)}" class="hc" style="stroke-width:{c}"/>' for c, v in buckets.items() if v) + '</g>')

# ---------------- woods
def poisson(cx, cy, rx, ry, spacing, keep, n_try=6000, rot=0):
    pts = []
    for _ in range(n_try):
        u, v = rng.uniform(-1, 1, 2)
        if u * u + v * v > 1: continue
        x = cx + u * rx; y = cy + v * ry
        if not on(x, y) or not keep(x, y): continue
        if any((x - a) ** 2 + (y - b) ** 2 < spacing ** 2 for a, b in pts): continue
        pts.append((x, y))
    return pts
def dl(x, y): return dland[int((y - Y0) / RES), int((x - X0) / RES)]
def far_from(px_, py_, r): return lambda x, y: (x - px_) ** 2 + (y - py_) ** 2 > r * r and dl(x, y) > 120
trees = []
trees += poisson(600, 34950, 3600, 3300, 150, far_from(-1800, 21450, 0), 9000)  # Younger Brother covered in woods
trees += poisson(13200, 8500, 2600, 4200, 260, lambda x, y: dl(x, y) > 600 and rng.random() < .8, 4000)
trees += poisson(28400, 24000, 2600, 1500, 240, lambda x, y: dl(x, y) > 300, 2500)
trees += poisson(5200, 29500, 2200, 1600, 260, lambda x, y: dl(x, y) > 300, 1800)
trees += poisson(3500, 9000, 4500, 5000, 330, lambda x, y: (x + 1800) ** 2 + (y - 21450) ** 2 > 3200 ** 2 and rng.random() < .55, 3500)
trees = [t for t in trees if not excluded(*t)]
body.append('<g class="lyr" id="lyr-woods">' + ''.join(
    f'<use href="#tree" x="{f(x)}" y="{f(y)}" transform="scale(1)"/>' for x, y in trees) + '</g>')

# ---------------- rivers & brook
for d in G['river']:
    body.append(f'<path d="{d}" class="river"/>')
body.append(f'<path d="{G["creek"][0]}" class="brook"/>')

# ---------------- coastline
body.append(f'<path d="{LAND_D} {ISL_D}" class="coast"/>')

# ---------------- roads, ferry, paths
road = chaikin([(16900, 18820), (16900, 18300), (17300, 17000), (17600, 16000), (18300, 15000), (18900, 14000), (18800, 13000),
                (18650, 12000), (18100, 11000), (17850, 10000), (17450, 9000), (17000, 8000), (16350, 7000), (16200, 6000),
                (15550, 5000), (15400, 4000), (15350, 3000), (14700, 2200), (13950, 1880)], 3)
roadlen = float(np.sum(np.hypot(*np.diff(road, axis=0).T)))
vpath = chaikin([(17000, 21300), (14500, 22400), (13300, 23300), (12500, 24700), (11900, 25600), (10500, 26300), (8000, 26600), (5500, 26600),
                 (3200, 26700), (1300, 27000), (-200, 25800), (-900, 24000), (-1500, 22300), (-1800, 21600)], 3)
for x, y in vpath[::6]:
    assert on(x, y), ('vale path off land', x, y)
ferry = [(17560, 20470), (17250, 19650), (16900, 18820)]
body.append('<g class="lyr" id="lyr-roads">'
            f'<path d="{pd(road)}" class="rd1"/><path d="{pd(road)}" class="rd2"/>'
            f'<path d="{pd(vpath)}" class="trail"/>'
            f'<path d="{pd(chaikin(ferry,3))}" class="ferry"/>'
            '</g>')

# ---------------- settlements & features
feat = []
# Kembleton: pier, streets, blocks, church, gallows, fields
feat.append('<path d="M17560 20690 L17560 20470" class="pier"/>')
feat.append('<path d="M17560 20700 L17600 21500 M17200 20960 L18250 20980 M17320 21250 L18150 21280 M18200 20980 L18350 21550" class="street"/>')
blocks = [(17260, 20760, 230, 150), (17640, 20740, 380, 170), (18050, 20760, 150, 160), (17330, 21030, 220, 170), (17640, 21030, 260, 190),
          (17940, 21040, 220, 180), (17400, 21320, 170, 170), (17650, 21330, 240, 150), (17920, 21330, 200, 130)]
for x, y, w, h in blocks:
    assert on(x, y) and on(x + w, y + h), ('block off land', x, y)
    feat.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" class="blk"/>')
# Chapter House on the bluff: walled square around a courtyard
feat.append('<g id="chapter"><rect x="16880" y="20800" width="260" height="240" class="chap"/><rect x="16945" y="20865" width="130" height="110" class="court"/>'
            '<path d="M17010 20700 V20790 M16985 20730 H17035" class="crs"/></g>')
# church cross in the square
feat.append('<path d="M17760 20900 V20990 M17735 20925 H17785" class="crs"/>')
# gallows on the square
feat.append('<path d="M17520 21180 V21110 H17590 V21180" class="gal"/>')
# fields (ploughed lots)
for x, y, w, h, a in [(15700, 21700, 640, 480, 8), (18450, 21650, 700, 450, -5), (16900, 21700, 650, 500, 3), (18450, 21150, 500, 380, 0)]:
    if not (on(x, y) and on(x + w, y + h)): continue
    lines = ''.join(f'M{x} {y + k}H{x + w}' for k in range(30, h, 55))
    feat.append(f'<g transform="rotate({a} {x} {y})"><rect x="{x}" y="{y}" width="{w}" height="{h}" class="fld"/><path d="{lines}" class="fldl"/></g>')
# North Harbour: huts along the cove, fish flakes on the beach, small quay
huts = []
for x in np.arange(12850, 14700, 95):
    sx = shore_y = None
    # find shore y below cove
    for t in range(0, 1500, 10):
        if on(x, 1200 + t): shore_y = 1200 + t; break
    if shore_y is None: continue
    for row in (1, 2):
        if rng.random() < .55:
            yy_ = shore_y + 160 * row + rng.uniform(-40, 60)
            if on(x, yy_): huts.append((x + rng.uniform(-20, 20), yy_))
for x, y in huts:
    feat.append(f'<rect x="{f(x-24)}" y="{f(y-18)}" width="48" height="36" class="hut"/>')
fl = []
for x in np.arange(13050, 14400, 110):
    for t in range(0, 1500, 10):
        if on(x, 1200 + t): sy = 1200 + t; break
    fl.append(f'M{f(x)} {f(sy+40)}v70M{f(x+30)} {f(sy+40)}v70')
feat.append(f'<path d="{"".join(fl)}" class="flake"/>')
# Burying Ground: fenced plot with crosses
feat.append('<rect x="20760" y="17750" width="480" height="330" class="yard"/>' + ''.join(
    f'<use href="#grave" x="{20830 + i * 85}" y="{17830 + j * 95}"/>' for i in range(5) for j in range(3)))
# Antient Stones on the summit of Elder Brother
stones = ''.join(f'<ellipse cx="{f(-1800 + math.cos(a) * 150)}" cy="{f(21450 + math.sin(a) * 150)}" rx="22" ry="30" class="stone"/>'
                 for a in np.linspace(0, 2 * math.pi, 12, endpoint=False))
feat.append(stones)
# Tide Cave mark
feat.append('<path d="M11905 180 a70 70 0 0 1 0 -140" class="cave"/>')
# anchors
feat.append('<use href="#anchor" x="16300" y="20250" transform="rotate(0)"/>')
feat.append('<use href="#anchor" x="14900" y="900"/>')
body.append('<g class="lyr" id="lyr-feat">' + ''.join(feat) + '</g>')

# ---------------- labels (English, as a British surveyor)
def T(x, y, s, cls, rot=0, anchor='middle', ls=None):
    tr = f' transform="rotate({rot} {f(x)} {f(y)})"' if rot else ''
    lsp = f' letter-spacing="{ls}"' if ls else ''
    return f'<text x="{f(x)}" y="{f(y)}" class="{cls}" text-anchor="{anchor}"{tr}{lsp}>{s}</text>'
def along(pts, s, cls, ls=None, off=0, pid=None):
    return (f'<path id="{pid}" d="{pd(pts)}" fill="none" stroke="none"/>'
            f'<text class="{cls}"{" letter-spacing=%s" % repr(str(ls)) if ls else ""}><textPath href="#{pid}" startOffset="50%" text-anchor="middle">{s}</textPath></text>')
L = []
L.append(T(29000, 16400, 'OCEANO ATLÂNTICO', 'l-ocean', 0, ls=300))
L.append(T(11400, 21150, 'BAÍA DOS IRMÃOS', 'l-bay', -4, ls=130))
L.append(T(15600, 19850, 'O Estreito', 'l-water', -10))
L.append(T(17300, 19300, 'Travessia', 'l-small', 0, 'start'))
L.append(T(28900, 13300, 'Ilha das Gaivotas', 'l-isle'))
L.append(T(18050, 22250, 'KEMBLETON', 'l-town', 0, ls=90))
L.append(T(16820, 21230, 'Casa Capitular', 'l-small', 0, 'end'))
L.append(T(13750, 2950, 'PORTO NORTE', 'l-town', -3, ls=70))
L.append(T(13000, 1330, 'Estrados de bacalhau', 'l-small', -4))
L.append(T(12020, 170, 'Gruta da Maré', 'l-small', 0, 'start'))
L.append(T(-1800, 22200, 'Círculo de Pedras', 'l-small'))
L.append(T(-1800, 20550, 'IRMÃO MAIS VELHO', 'l-mount', 0, ls=110))
L.append(T(600, 36550, 'IRMÃO MAIS NOVO', 'l-mount', 0, ls=110))
L.append(T(-500, 29100, 'Vale do Gólgota', 'l-vale', -8, ls=160))
L.append(T(-3300, 12600, 'SERRA DOS GÊMEOS', 'l-range', -74, ls=520))
L.append(T(3000, 2400, 'ILHA DOS DOIS IRMÃOS', 'l-island', -6, ls=150))
L.append(T(21300, 17550, 'Ponta do Cemitério', 'l-point', -38))
L.append(T(21000, 18300, 'Cemitério', 'l-small'))
L.append(along(chaikin([(1200, 15600), (3500, 15100), (5600, 14300)], 2), 'Rio Castor', 'l-river', pid='pBeaver'))
L.append(along([(18050, 13200), (18350, 10200)], 'Estrada da Falésia', 'l-road', pid='pRoad'))
L.append(T(-150, 30600, 'Riacho', 'l-small', -60))
body.append('<g class="lyr" id="lyr-names">' + ''.join(L) + '</g>')

# soundings legend note & small rose
def rose(cx, cy, R, big=True):
    g = [f'<g transform="translate({f(cx)} {f(cy)})" class="rose">']
    g.append(f'<circle r="{f(R)}" class="r-ring"/><circle r="{f(R*0.93)}" class="r-ring2"/><circle r="{f(R*0.18)}" class="r-hub"/>')
    # ticks
    tk = ''.join(f'M{f(math.sin(math.radians(a))*R*0.93)} {f(-math.cos(math.radians(a))*R*0.93)}L{f(math.sin(math.radians(a))*R*(0.88 if a%10 else 0.84))} {f(-math.cos(math.radians(a))*R*(0.88 if a%10 else 0.84))}' for a in range(0, 360, 5))
    g.append(f'<path d="{tk}" class="r-tick"/>')
    for k in range(32):
        a = math.radians(k * 11.25)
        L_ = R * (0.86 if k % 8 == 0 else 0.66 if k % 4 == 0 else 0.5 if k % 2 == 0 else 0.38)
        w = R * (0.11 if k % 8 == 0 else 0.085 if k % 4 == 0 else 0.06 if k % 2 == 0 else 0.045)
        tip = (math.sin(a) * L_, -math.cos(a) * L_)
        l = (math.sin(a - math.pi / 2) * w, -math.cos(a - math.pi / 2) * w)
        r = (math.sin(a + math.pi / 2) * w, -math.cos(a + math.pi / 2) * w)
        if k % 2 == 1: continue
        g.append(f'<path d="M0 0L{f(l[0])} {f(l[1])}L{f(tip[0])} {f(tip[1])}Z" class="r-d"/><path d="M0 0L{f(r[0])} {f(r[1])}L{f(tip[0])} {f(tip[1])}Z" class="r-l"/>')
    if big:
        # fleur-de-lis at north and cross at east (English convention)
        s = R / 1000
        g.append(f'<g transform="translate(0 {f(-R*0.97)}) scale({s:.3f})"><path d="M0 -260 C60 -180 70 -90 0 -10 C-70 -90 -60 -180 0 -260Z M0 -40 C90 -120 200 -90 170 0 C150 -60 80 -60 30 -20Z M0 -40 C-90 -120 -200 -90 -170 0 C-150 -60 -80 -60 -30 -20Z M-90 0 H90 V40 H-90Z" class="r-fl"/></g>')
        for k, lab in [(0, 'N'), (8, 'L'), (16, 'S'), (24, 'O')]:
            if lab == 'N': continue
            a = math.radians(k * 11.25)
            g.append(f'<text x="{f(math.sin(a)*R*1.13)}" y="{f(-math.cos(a)*R*1.13+R*0.05)}" class="r-lab" text-anchor="middle">{lab}</text>')
    g.append('</g>')
    return ''.join(g)
orn = []
orn.append(rose(*ROSES[0], True))
orn.append(rose(*ROSES[1], False))

# scale of leagues
LEAGUE = 5556.0; MILE = 1852.0
sx0, sy0 = 12400, 38020
sc = [f'<g class="scale">']
sc.append(f'<text x="{f(sx0 + LEAGUE)}" y="{f(sy0 - 330)}" class="sc-t" text-anchor="middle">Escala de duas léguas, de vinte ao grau</text>')
sc.append(f'<rect x="{f(sx0)}" y="{f(sy0)}" width="{f(2*LEAGUE)}" height="150" class="sc-o"/>')
for i in range(6):
    if i % 2 == 0: sc.append(f'<rect x="{f(sx0 + i*MILE)}" y="{f(sy0)}" width="{f(MILE)}" height="75" class="sc-b"/>')
    else: sc.append(f'<rect x="{f(sx0 + i*MILE)}" y="{f(sy0+75)}" width="{f(MILE)}" height="75" class="sc-b"/>')
for i in range(10):
    x = sx0 - MILE + i * MILE / 10
sc.append(f'<path d="{"".join(f"M{f(sx0 - MILE + i*MILE/10)} {sy0}v150" for i in range(11))}" class="sc-tick"/><rect x="{f(sx0-MILE)}" y="{sy0}" width="{f(MILE)}" height="150" class="sc-o"/>')
for lab, x in [('1 milha', sx0 - MILE / 2), ('0', sx0), ('1 légua', sx0 + LEAGUE), ('2 léguas', sx0 + 2 * LEAGUE)]:
    sc.append(f'<text x="{f(x)}" y="{f(sy0 + 430)}" class="sc-l" text-anchor="middle">{lab}</text>')
sc.append('</g>')
orn.append(''.join(sc))

# remarks
rem = ['<g class="remarks">', '<text x="23350" y="34800" class="rm-h" text-anchor="middle">OBSERVAÇÕES</text>',
       '<path d="M21750 34940 H24950" class="rm-rule"/>']
for i, t in enumerate(['Preamar nas luas nova e cheia às VIII h.', 'As águas-vivas sobem sete pés.', 'As sondagens estão em braças.',
                       'A Gruta da Maré só seca na baixa-mar.', 'Declinação da agulha: 6° Oeste.']):
    rem.append(f'<text x="23350" y="{35380 + i*400}" class="rm" text-anchor="middle">{t}</text>')
rem.append('</g>')
orn.append(''.join(rem))

# cartouche (top-right sea)
cx0, cy0, cx1, cy1 = 23300, -650, 35700, 7700
ct = [f'<g class="cart"><rect x="{cx0}" y="{cy0}" width="{cx1-cx0}" height="{cy1-cy0}" class="ct-bg"/>',
      f'<rect x="{cx0}" y="{cy0}" width="{cx1-cx0}" height="{cy1-cy0}" class="ct-o"/>',
      f'<rect x="{cx0+160}" y="{cy0+160}" width="{cx1-cx0-320}" height="{cy1-cy0-320}" class="ct-i"/>']
# corner flourishes
for (x, y, sxs, sys_) in [(cx0, cy0, 1, 1), (cx1, cy0, -1, 1), (cx0, cy1, 1, -1), (cx1, cy1, -1, -1)]:
    ct.append(f'<path transform="translate({x} {y}) scale({sxs} {sys_})" d="M160 600 C160 300 300 160 600 160 M260 560 C300 380 380 300 560 260 M330 330 m-55 0 a55 55 0 1 0 110 0 a55 55 0 1 0 -110 0" class="ct-fl"/>')
mx = (cx0 + cx1) / 2
ct += [T(mx, 900, 'CARTA', 'ct-1', ls=200), T(mx, 1500, 'da', 'ct-2'),
       T(mx, 2650, 'ILHA DOS DOIS IRMÃOS', 'ct-3', ls=120),
       T(mx, 3500, 'com a vila e o porto de Kembleton,', 'ct-2'),
       T(mx, 4100, 'Porto Norte e as costas adjacentes.', 'ct-2'),
       f'<path d="M{mx-2600} 4600 H{mx-300} M{mx+300} 4600 H{mx+2600}" class="ct-rule"/><path d="M{mx} 4450 l150 150 -150 150 -150 -150Z" class="ct-dia"/>',
       T(mx, 5500, 'Levantada nos anos de 1776 e 1777.', 'ct-4'),
       T(mx, 6400, 'Lat. 38° Norte · Long. 60° Oeste de Londres', 'ct-5')]
ct.append('</g>')
orn.append(''.join(ct))
body.append('<g id="lyr-orn">' + ''.join(orn) + '</g>')

out.append(f'<g clip-path="url(#cFrame)">{"".join(body)}</g>')

# ---------------- frame with graduated border (minutes of lat / long)
fr = [f'<rect x="{f(FX0)}" y="{f(FY0)}" width="{f(FX1-FX0)}" height="{f(FY1-FY0)}" class="nl"/>',
      f'<rect x="{f(FX0-BAND)}" y="{f(FY0-BAND)}" width="{f(FX1-FX0+2*BAND)}" height="{f(FY1-FY0+2*BAND)}" class="nl2"/>',
      f'<rect x="{f(FX0-BAND-160)}" y="{f(FY0-BAND-160)}" width="{f(FX1-FX0+2*BAND+320)}" height="{f(FY1-FY0+2*BAND+320)}" class="nl3"/>']
CX, CY = 15525.0, 18750.0
MLAT = 1852.0; MLON = 1852.0 * math.cos(math.radians(38))
def latmin(y): return 38 * 60 - (y - CY) / MLAT
def lonmin(x): return 60 * 60 - (x - CX) / MLON
# lat bands
lo, hi = latmin(FY1), latmin(FY0)
m = math.ceil(lo)
segs = []
while m < hi:
    y = CY - (m - 38 * 60) * MLAT
    y2 = CY - (m + 1 - 38 * 60) * MLAT
    if m % 2 == 0:
        for xa in (FX0 - BAND, FX1):
            segs.append(f'<rect x="{f(xa)}" y="{f(max(y2, FY0))}" width="{f(BAND)}" height="{f(min(y, FY1)-max(y2, FY0))}" class="gb"/>')
    if m % 5 == 0:
        d, mm = divmod(m, 60)
        lab = f'{d}°{mm:02d}′' if mm else f'{d}°'
        for xa, an in ((FX0 - BAND - 260, 'end'), (FX1 + BAND + 260, 'start')):
            segs.append(f'<text x="{f(xa)}" y="{f(y+140)}" class="grad" text-anchor="{an}">{lab}</text>')
    m += 1
lo, hi = lonmin(FX1), lonmin(FX0)
m = math.ceil(lo)
while m < hi:
    x = CX - (m - 60 * 60) * MLON
    x2 = CX - (m + 1 - 60 * 60) * MLON
    if m % 2 == 0:
        for ya in (FY0 - BAND, FY1):
            segs.append(f'<rect x="{f(max(x2, FX0))}" y="{f(ya)}" width="{f(min(x, FX1)-max(x2, FX0))}" height="{f(BAND)}" class="gb"/>')
    if m % 5 == 0:
        d, mm = divmod(m, 60)
        lab = f'{d}°{mm:02d}′' if mm else f'{d}°'
        for ya in (FY0 - BAND - 280, FY1 + BAND + 620):
            segs.append(f'<text x="{f(x)}" y="{f(ya)}" class="grad" text-anchor="middle">{lab}</text>')
    m += 1
fr += segs
fr.append(T(CX, FY1 + BAND + 1450, 'Publicada conforme Ato do Parlamento, 1º de maio de 1778.', 'imprint'))
fr.append(T(FX0 - BAND - 160, FY0 - BAND - 700, 'Longitude oeste de Londres', 'grad-t', 0, 'start'))
out.append('<g id="frame">' + ''.join(fr) + '</g>')

# ---------------- reference markers (interactive) & GM annotations
REFS = json.load(open('refs.json'))
mk = []
for r in REFS:
    x, y = r['at']; cls = 'ref gm-only' if r.get('gm') else 'ref'
    mk.append(f'<g class="{cls}" data-ref="{r["id"]}" tabindex="0" role="button" aria-label="{r["name"]}" transform="translate({x} {y})">'
              f'<circle r="330" class="ref-hit"/><circle r="190" class="ref-c"/><text y="78" class="ref-t" text-anchor="middle">{r["letter"]}</text></g>')
gmn = []
for r in REFS:
    if 'gmnote' in r:
        x, y, s = r['gmnote']
        gmn.append(f'<text x="{x}" y="{y}" class="gm-note">{s}</text>')
out.append('<g id="lyr-gm">' + ''.join(gmn) + '</g>')
out.append('<g id="lyr-refs" class="lyr">' + ''.join(mk) + '</g>')

svg = ''.join(out)
open('chart_inner.svg', 'w').write(svg)
json.dump({'vb': VB, 'road_km': roadlen / 1000, 'ferry_km': float(np.sum(np.hypot(*np.diff(np.array(ferry), axis=0).T))) / 1000,
           'n_sound': len(sound), 'n_trees': len(trees), 'n_hach': int(len(st))}, open('chart_meta.json', 'w'))
print('svg bytes', len(svg), json.load(open('chart_meta.json')))
