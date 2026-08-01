# -*- coding: utf-8 -*-
"""
make_map_svg.py  —  集合場所案内図プレビュー（annaizu_preview.html）用の地図SVGを作る

OpenStreetMap（Overpass API）から建物・道路・駐車場を取得し、
annaizu_preview.html の地図キャンバス（viewBox 0 0 1000 681）にぴったり収まる
SVG を1枚出力する。出力SVGはそのままアプリの「画像を読込」にドロップすればよい。

使い方:
    python make_map_svg.py 33.194743 131.657121 --range 420 --out map.svg
    python make_map_svg.py "33.194743, 131.657121"            # 貼り付けそのままでも可
    python make_map_svg.py "https://www.google.com/maps/...@33.19,131.65,17z"

    --range  中心から上下方向の距離(m)。既定420。広域なら700〜1000
    --label  ラベルを出す最大件数（既定22）。0でラベル無し
    --plain  建物と道路だけの素っ気ない図（ラベル無し・淡色）

座標の拾い方:
    Googleマップで集合場所を右クリック →「35.123456, 139.123456」をコピーして渡す。

Overpass が混んでいる時は数十秒かかる。失敗したらしばらく置いて再実行するか、
--endpoint で別ミラーを指定する。
"""
import argparse, json, math, re, sys, urllib.error, urllib.parse, urllib.request

VB_W, VB_H = 1000.0, 681.0          # annaizu_preview.html の地図キャンバス
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
        placed, n = [], 0
        # 面積の大きい建物・名前付き施設を優先
        def weight(e):
            t = e.get('tags', {})
            g = e.get('geometry') or []
            return (0 if 'highway' in t else 1, len(g))
        cands = [e for e in els if (e.get('tags') or {}).get('name')]
        for e in sorted(cands, key=weight, reverse=True):
            if n >= max_labels:
                break
            t = e['tags']
            g = e.get('geometry')
            if g:
                x = sum(P(p['lat'], p['lon'])[0] for p in g) / len(g)
                y = sum(P(p['lat'], p['lon'])[1] for p in g) / len(g)
            elif 'lat' in e:
                x, y = P(e['lat'], e['lon'])
            else:
                continue
            if x < 14 or x > VB_W - 14 or y < 16 or y > VB_H - 8:
                continue
            if any(abs(px - x) < 78 and abs(py - y) < 24 for px, py in placed):
                continue
            placed.append((x, y)); n += 1
            road = 'highway' in t
            fs, wt = (15, '400') if road else (17, '700')
            for st in ('stroke="#fff" stroke-width="4.6" stroke-linejoin="round" fill="none"', 'fill="#000"'):
                o.append('<text x="%.1f" y="%.1f" font-size="%d" font-weight="%s" text-anchor="middle" '
                         'font-family="Meiryo,\'Yu Gothic\',sans-serif" %s>%s</text>'
                         % (x, y, fs, wt, st, esc(t['name'])))

    o.append('</svg>')
    return '\n'.join(o)


def main():
    ap = argparse.ArgumentParser(description='集合場所案内図用の地図SVGを作る')
    ap.add_argument('point', nargs='+', help='緯度 経度 / "33.19,131.65" / GoogleマップURL')
    ap.add_argument('--range', type=float, default=420.0, help='中心から上下の距離(m)。既定420')
    ap.add_argument('--out', default='map.svg', help='出力SVGパス')
    ap.add_argument('--label', type=int, default=22, help='ラベル最大件数（0で無し）')
    ap.add_argument('--plain', action='store_true', help='ラベル無し・淡色の素図')
    ap.add_argument('--endpoint', action='append', help='Overpassのミラーを指定（複数可）')
    a = ap.parse_args()

    pt = parse_point(' '.join(a.point))
    if not pt:
        raise SystemExit('緯度経度を読み取れませんでした。例: 33.194743 131.657121')
    lat, lon = pt
    print('中心 %.6f, %.6f ／ 範囲 ±%.0fm' % (lat, lon, a.range))
    data = fetch(lat, lon, a.range, a.endpoint or ENDPOINTS)
    els = data.get('elements', [])
    print('取得 %d 要素' % len(els))
    svg = build_svg(els, lat, lon, a.range, 0 if a.plain else a.label, a.plain)
    with open(a.out, 'w', encoding='utf-8') as f:
        f.write(svg)
    print('出力 %s（%.0f KB）' % (a.out, len(svg) / 1024))
    print('→ annaizu_preview.html の「画像を読込」にこのSVGをドロップしてください。')


if __name__ == '__main__':
    main()
