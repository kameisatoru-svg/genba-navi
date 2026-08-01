# -*- coding: utf-8 -*-
"""
make_map_svg.py  —  集合場所案内図プレビュー（annaizu_preview.html）用の地図SVGを作る

OpenStreetMap（Overpass API）から建物・道路・駐車場を取得し、
annaizu_preview.html の地図キャンバス（viewBox 0 0 1000 638）にぴったり収まる
SVG を1枚出力する。出力SVGはそのままアプリの「画像を読込」にドロップすればよい。

使い方:
    python make_map_svg.py 33.194743 131.657121 --range 240 --out map.svg
    python make_map_svg.py "33.194743, 131.657121"            # 貼り付けそのままでも可
    python make_map_svg.py "https://www.google.com/maps/...@33.19,131.65,17z"

    --range  中心から上下の距離(m)＝図の高さの半分。既定240。
             敷地1つなら200〜260、街区ごと入れるなら400〜600
    --label  ラベルを出す最大件数（既定22）。0でラベル無し
    --plain  建物と道路だけの素っ気ない図（ラベル無し・淡色）

座標の拾い方:
    Googleマップで集合場所を右クリック →「35.123456, 139.123456」をコピーして渡す。

Overpass が混んでいる時は数十秒かかる。失敗したらしばらく置いて再実行するか、
--endpoint で別ミラーを指定する。
"""
import argparse, json, math, re, sys, time, urllib.error, urllib.parse, urllib.request

VB_W, VB_H = 1000.0, 638.0          # annaizu_preview.html の地図キャンバス（188mm×120mm）
ENDPOINTS = [
    'https://overpass-api.de/api/interpreter',
    'https://overpass.kumi.systems/api/interpreter',
    'https://overpass.private.coffee/api/interpreter',
]

ROAD_STYLE = [   # (highway値, 線幅, 塗り, 縁)
    (('motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary'), 11.0, '#f2cb98', '#c98b32'),
    (('secondary', 'tertiary', 'secondary_link', 'tertiary_link'),     8.0, '#f6ead3', '#bfa878'),
    (('residential', 'unclassified', 'living_street'),                5.5, '#ffffff', '#cfcfcf'),
    (('service', 'footway', 'path', 'pedestrian'),                    2.6, '#ffffff', '#dcdcdc'),
]


def parse_point(text):
    """Googleマップの座標貼り付け／URL／数値ペアから (lat, lon) を取る"""
    for pat in (r'!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)',
                r'@(-?\d+\.\d+),(-?\d+\.\d+)',
                r'(-?\d{1,3}\.\d{3,})[,\s]+(-?\d{1,3}\.\d{3,})'):
        m = re.search(pat, text)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None


def fetch(lat, lon, rng, endpoints):
    d_lat = rng / 110574.0
    d_lon = rng / (111320.0 * math.cos(math.radians(lat)))
    # 横に広い図なので経度側を広めに取る
    d_lon *= VB_W / VB_H
    bb = '%.6f,%.6f,%.6f,%.6f' % (lat - d_lat, lon - d_lon, lat + d_lat, lon + d_lon)
    q = ('[out:json][timeout:60];('
         'way["building"](%s);'
         'way["highway"](%s);'
         'way["amenity"="parking"](%s);'
         'way["landuse"~"retail|commercial|industrial"](%s);'
         'node["name"]["amenity"](%s);'
         'node["name"]["shop"](%s);'
         ');out body geom;' % (bb, bb, bb, bb, bb, bb))
    # Overpass は時間帯によって混む。ミラーを順に、間隔を空けて2巡試す。
    last = None
    for attempt in range(2):
        for url in endpoints:
            try:
                req = urllib.request.Request(
                    url, data=('data=' + urllib.parse.quote(q)).encode('utf-8'),
                    headers={'Content-Type': 'application/x-www-form-urlencoded',
                             'User-Agent': 'artrays-annaizu/1.0 (construction site guide map)'})
                with urllib.request.urlopen(req, timeout=90) as r:
                    return json.loads(r.read().decode('utf-8'))
            except Exception as e:                              # noqa: BLE001
                last = '%s: %s' % (url, e)
                print('  ... %s で失敗、次を試します' % url, file=sys.stderr)
        if attempt == 0:
            print('  ... 15秒待って再試行します', file=sys.stderr)
            time.sleep(15)
    raise SystemExit('Overpass からデータを取得できませんでした（混雑時は数分後に再実行）。\n'
                     '  最後のエラー: %s\n'
                     '  取得済みJSONがあるなら --from-json で再利用できます。' % last)


def build_svg(els, lat0, lon0, rng, max_labels=22, plain=False):
    m_lon = 111320.0 * math.cos(math.radians(lat0))
    half_h = float(rng)
    half_w = rng * (VB_W / VB_H)

    def P(la, lo):
        x = (lo - lon0) * m_lon
        y = (la - lat0) * 110574.0
        return ((x + half_w) / (2 * half_w) * VB_W, (half_h - y) / (2 * half_h) * VB_H)

    def d(geom, close=False):
        pts = [P(p['lat'], p['lon']) for p in geom]
        return 'M ' + ' L '.join('%.1f,%.1f' % p for p in pts) + (' Z' if close else '')

    def esc(s):
        return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

    o = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d">' % (VB_W, VB_H),
         '<rect width="%d" height="%d" fill="#fcfcfa"/>' % (VB_W, VB_H)]

    for e in els:                                       # 敷地
        t, g = e.get('tags', {}), e.get('geometry')
        if g and re.match(r'retail|commercial|industrial', t.get('landuse', '')):
            o.append('<path d="%s" fill="#f6f3ec" stroke="#d8cfb8" stroke-width="1.2"/>' % d(g, True))
    for e in els:                                       # 駐車場
        t, g = e.get('tags', {}), e.get('geometry')
        if g and t.get('amenity') == 'parking':
            o.append('<path d="%s" fill="#dcead6" stroke="#6f9169" stroke-width="1.2"/>' % d(g, True))
    for cls, w, col, ec in ROAD_STYLE:                  # 道路（縁→塗りの2度描き）
        for e in els:
            t, g = e.get('tags', {}), e.get('geometry')
            if not g or t.get('highway') not in cls:
                continue
            p = d(g)
            o.append('<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round" stroke-linejoin="round"/>' % (p, ec, w + 1.8))
            o.append('<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round" stroke-linejoin="round"/>' % (p, col, w))
    for e in els:                                       # 建物
        t, g = e.get('tags', {}), e.get('geometry')
        if g and 'building' in t:
            o.append('<path d="%s" fill="%s" stroke="%s" stroke-width="1.1"/>'
                     % (d(g, True), '#dfe3e8' if plain else '#ccd2da', '#9aa3ae' if plain else '#8a939f'))

    if not plain and max_labels:
        MAJOR = ('motorway', 'trunk', 'primary', 'secondary')

        def labelable(e):
            t = e.get('tags') or {}
            if not t.get('name'):
                return False
            if t.get('place') or t.get('boundary'):       # 町名・字名は案内図に不要
                return False
            if t.get('public_transport') or t.get('highway') == 'bus_stop':
                return False
            if 'highway' in t:                            # 道路は幹線だけ
                return t['highway'] in MAJOR
            return True

        def weight(e):                                    # 大きい建物・施設を優先
            t = e.get('tags', {})
            return (0 if 'highway' in t else 1, len(e.get('geometry') or []))

        placed, used, n = [], set(), 0
        for e in sorted([x for x in els if labelable(x)], key=weight, reverse=True):
            if n >= max_labels:
                break
            t = e['tags']
            name = t['name']
            if name in used:                              # 同名は1回だけ
                continue
            g = e.get('geometry')
            if g:
                x = sum(P(p['lat'], p['lon'])[0] for p in g) / len(g)
                y = sum(P(p['lat'], p['lon'])[1] for p in g) / len(g)
            elif 'lat' in e:
                x, y = P(e['lat'], e['lon'])
            else:
                continue
            if x < 14 or x > VB_W - 14 or y < 18 or y > VB_H - 10:
                continue
            road = 'highway' in t
            fs = 15 if road else 17
            half = len(name) * fs * 0.55                  # 文字幅ぶんの衝突半径
            if any(abs(px - x) < (half + pw) and abs(py - y) < 22 for px, py, pw in placed):
                continue
            placed.append((x, y, half)); used.add(name); n += 1
            wt = '400' if road else '700'
            for st in ('stroke="#fff" stroke-width="4.6" stroke-linejoin="round" fill="none"', 'fill="#000"'):
                o.append('<text x="%.1f" y="%.1f" font-size="%d" font-weight="%s" text-anchor="middle" '
                         'font-family="Meiryo,\'Yu Gothic\',sans-serif" %s>%s</text>'
                         % (x, y, fs, wt, st, esc(name)))

    # 縮尺バーと方位は SVG 自身に焼き込む（実距離を知っているのは生成側だけなので）
    width_m = 2 * half_w
    step = 10
    for cand in (10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000):
        if cand <= width_m / 4:
            step = cand
    bar = step / width_m * VB_W
    bx, by = VB_W - 26 - bar, VB_H - 26
    o.append('<g font-family="Meiryo,\'Yu Gothic\',sans-serif">')
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="30" fill="#fff" fill-opacity="0.82"/>'
             % (bx - 18, by - 17, bar + 44))
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="6" fill="#000"/>' % (bx, by, bar / 2))
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="6" fill="#fff" stroke="#000" stroke-width="1"/>'
             % (bx + bar / 2, by, bar / 2))
    o.append('<text x="%.1f" y="%.1f" font-size="14" text-anchor="middle" fill="#000">0</text>' % (bx, by - 5))
    o.append('<text x="%.1f" y="%.1f" font-size="14" text-anchor="middle" fill="#000">%dm</text>'
             % (bx + bar, by - 5, step))
    nx, ny = VB_W - 30, 32                      # 方位（この図は常に北が上）
    o.append('<path d="M %.0f,%.0f L %.0f,%.0f L %.0f,%.0f L %.0f,%.0f Z" fill="#000"/>'
             % (nx, ny - 16, nx - 8, ny + 10, nx, ny + 4, nx + 8, ny + 10))
    o.append('<text x="%.0f" y="%.0f" font-size="15" font-weight="700" text-anchor="middle" fill="#000">N</text>'
             % (nx, ny + 27))
    o.append('</g>')
    o.append('</svg>')
    return '\n'.join(o)


# =============================================================================
# 航空写真（国土地理院 空中写真タイル）
#   Googleマップの衛星画像は配布・印刷に制約があるため使わない。
#   地理院タイルは出典を明示すれば自由に利用できる（本関数が出典を焼き込む）。
# =============================================================================
GSI_TILE = 'https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/%d/%d/%d.jpg'
GSI_MAX_Z = 18


def _tile_xy(lat, lon, z):
    n = 2 ** z
    r = math.radians(lat)
    return ((lon + 180.0) / 360.0 * n,
            (1.0 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2.0 * n)


def build_aerial_svg(lat0, lon0, rng, aspect=1.30, zoom=None):
    """中心と範囲から空中写真を切り出し、data URI で埋めたSVGを返す"""
    from io import BytesIO
    import base64
    from PIL import Image

    vb_w = 1000.0
    vb_h = round(vb_w / aspect)
    half_h, half_w = float(rng), rng * aspect

    # 目標 1600px 相当の解像度になるズームを選ぶ（地理院は z18 が上限）
    if zoom is None:
        res_want = (2 * half_w) / 1600.0                       # m/px
        zoom = GSI_MAX_Z
        for z in range(14, GSI_MAX_Z + 1):
            if 156543.03392 * math.cos(math.radians(lat0)) / (2 ** z) <= res_want:
                zoom = z
                break
    m_per_px = 156543.03392 * math.cos(math.radians(lat0)) / (2 ** zoom)

    cx, cy = _tile_xy(lat0, lon0, zoom)                          # タイル座標(小数)
    px_w, px_h = (2 * half_w) / m_per_px, (2 * half_h) / m_per_px
    left, top = cx * 256 - px_w / 2, cy * 256 - px_h / 2
    tx0, ty0 = int(left // 256), int(top // 256)
    tx1, ty1 = int((left + px_w) // 256), int((top + px_h) // 256)

    canvas = Image.new('RGB', ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256), (230, 230, 230))
    got = miss = 0
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            try:
                req = urllib.request.Request(GSI_TILE % (zoom, tx, ty),
                                             headers={'User-Agent': 'artrays-annaizu/1.0'})
                with urllib.request.urlopen(req, timeout=25) as r:
                    canvas.paste(Image.open(BytesIO(r.read())), ((tx - tx0) * 256, (ty - ty0) * 256))
                got += 1
            except Exception:                                    # noqa: BLE001
                miss += 1
    if not got:
        raise SystemExit('空中写真タイルを取得できませんでした（通信 or 範囲外）。')
    print('空中写真 z=%d ／ タイル %d枚取得' % (zoom, got) + ('（%d枚欠測）' % miss if miss else ''))

    img = canvas.crop((int(left - tx0 * 256), int(top - ty0 * 256),
                       int(left - tx0 * 256 + px_w), int(top - ty0 * 256 + px_h)))
    buf = BytesIO(); img.save(buf, 'JPEG', quality=86)
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')

    o = ['<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
         'viewBox="0 0 %d %d">' % (vb_w, vb_h),
         '<image x="0" y="0" width="%d" height="%d" preserveAspectRatio="none" '
         'xlink:href="data:image/jpeg;base64,%s"/>' % (vb_w, vb_h, b64)]

    width_m = 2 * half_w                                          # 縮尺バー
    step = 10
    for cand in (10, 20, 25, 50, 100, 200, 250, 500):
        if cand <= width_m / 4:
            step = cand
    bar = step / width_m * vb_w
    bx, by = vb_w - 26 - bar, vb_h - 26
    o.append('<g font-family="Meiryo,\'Yu Gothic\',sans-serif">')
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="30" fill="#fff" fill-opacity="0.85"/>'
             % (bx - 18, by - 17, bar + 44))
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="6" fill="#000"/>' % (bx, by, bar / 2))
    o.append('<rect x="%.1f" y="%.1f" width="%.1f" height="6" fill="#fff" stroke="#000" stroke-width="1"/>'
             % (bx + bar / 2, by, bar / 2))
    o.append('<text x="%.1f" y="%.1f" font-size="14" text-anchor="middle" fill="#000">0</text>' % (bx, by - 5))
    o.append('<text x="%.1f" y="%.1f" font-size="14" text-anchor="middle" fill="#000">%dm</text>'
             % (bx + bar, by - 5, step))
    nx, ny = vb_w - 30, 34                                        # 方位（北が上）
    o.append('<circle cx="%.0f" cy="%.0f" r="22" fill="#fff" fill-opacity="0.85"/>' % (nx, ny + 4))
    o.append('<path d="M %.0f,%.0f L %.0f,%.0f L %.0f,%.0f L %.0f,%.0f Z" fill="#000"/>'
             % (nx, ny - 14, nx - 8, ny + 10, nx, ny + 4, nx + 8, ny + 10))
    o.append('<text x="%.0f" y="%.0f" font-size="14" font-weight="700" text-anchor="middle" fill="#000">N</text>'
             % (nx, ny + 24))
    # 出典表示（地理院タイル利用規約により必須）
    o.append('<rect x="0" y="%.1f" width="196" height="20" fill="#fff" fill-opacity="0.8"/>' % (vb_h - 20))
    o.append('<text x="5" y="%.1f" font-size="13" fill="#000">出典：国土地理院 空中写真</text>' % (vb_h - 6))
    o.append('</g></svg>')
    return '\n'.join(o)


def main():
    ap = argparse.ArgumentParser(description='集合場所案内図用の地図SVGを作る')
    ap.add_argument('point', nargs='+', help='緯度 経度 / "33.19,131.65" / GoogleマップURL')
    ap.add_argument('--range', type=float, default=240.0, help='中心から上下の距離(m)。既定240')
    ap.add_argument('--out', default='map.svg', help='出力SVGパス')
    ap.add_argument('--label', type=int, default=22, help='ラベル最大件数（0で無し）')
    ap.add_argument('--plain', action='store_true', help='ラベル無し・淡色の素図')
    ap.add_argument('--aerial', action='store_true',
                    help='国土地理院の空中写真で作る（拡大図向け。Overpass不要）')
    ap.add_argument('--aspect', type=float, default=None,
                    help='横÷縦。既定は本図1.567／--aerial時は拡大図枠の1.30')
    ap.add_argument('--endpoint', action='append', help='Overpassのミラーを指定（複数可）')
    ap.add_argument('--from-json', dest='from_json', action='append',
                    help='取得済みのOverpass JSONを使う（複数指定でマージ）。混雑時の再利用に')
    ap.add_argument('--save-json', dest='save_json', help='取得したJSONを保存しておく')
    a = ap.parse_args()

    pt = parse_point(' '.join(a.point))
    if not pt:
        raise SystemExit('緯度経度を読み取れませんでした。例: 33.194743 131.657121')
    lat, lon = pt
    print('中心 %.6f, %.6f ／ 範囲 ±%.0fm' % (lat, lon, a.range))

    if a.aerial:
        svg = build_aerial_svg(lat, lon, a.range, a.aspect or 1.30)
        with open(a.out, 'w', encoding='utf-8') as f:
            f.write(svg)
        print('出力 %s（%.0f KB）' % (a.out, len(svg) / 1024))
        print('→ annaizu_preview.html の「拡大図に別の地図を使う」に読み込んでください。')
        return

    if a.from_json:
        seen, els = set(), []
        for path in a.from_json:
            with open(path, encoding='utf-8') as f:
                for e in json.load(f).get('elements', []):
                    if e.get('id') in seen:
                        continue
                    seen.add(e.get('id')); els.append(e)
        print('既存JSONから %d 要素' % len(els))
    else:
        data = fetch(lat, lon, a.range, a.endpoint or ENDPOINTS)
        els = data.get('elements', [])
        print('取得 %d 要素' % len(els))
        if a.save_json:
            with open(a.save_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            print('JSONを保存 %s' % a.save_json)
    svg = build_svg(els, lat, lon, a.range, 0 if a.plain else a.label, a.plain)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(svg)
    print('出力 %s（%.0f KB）' % (a.out, len(svg) / 1024))
    print('→ annaizu_preview.html の「画像を読込」にこのSVGをドロップしてください。')


if __name__ == '__main__':
    main()
