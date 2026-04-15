# -*- coding: utf-8 -*-
"""
sekozu_parts.py
施工図フレームワーク用 断面部材ライブラリ（v1.0）

株式会社アート・レイズ / 現場ナビPRO
置き場所: C:\\Users\\user\\artrays\\claude ai\\genba-navi\\

■ 設計方針
- 各関数は SVG 文字列（str）を返す。呼び出し側で連結して <svg>…</svg> に埋める。
- 座標は「呼び出し側が決めた描画座標系（px）」で受け取る。
- 部材寸法は「実mm」を scale(px/mm) で px に換算する。
  scale=1.0 なら 1mm=1px（実寸）／scale=0.5 なら 1/2 縮尺相当。
- sekozu-framework スキルの描画ルールに準拠（I形H鋼・コの字LGSランナー・縦2本線LGSスタッド・
  PBハッチ・右引出しラベル・アンカーボルト）。

■ 使い方
    from sekozu_parts import (draw_hko, draw_lgs_runner, draw_lgs_stud,
                              draw_pb, draw_label_right, draw_anchor,
                              draw_defs, draw_wood_stud, draw_screw_coarse,
                              draw_plywood, draw_keical, draw_c_channel)

    svg_body = []
    svg_body.append(draw_defs())                       # <defs> マーカー等（必須1回）
    svg_body.append(draw_hko(cx=200, y=400, spec='H-150x150'))
    svg_body.append(draw_lgs_runner(cx=200, y=460, spec='LGS65', direction='down'))
    svg_body.append(draw_lgs_stud(x=165, y1=470, y2=700, spec='LGS65'))
    svg_body.append(draw_pb(x=169, y1=470, y2=700, w=12.5))
    svg_body.append(draw_label_right(x=280, cy=580, text='化粧PB t12.5'))
    svg_body.append(draw_anchor(cx=200, y=430))

    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="760" height="1074">' \\
          + ''.join(svg_body) + '</svg>'

■ 色・線の定数
- 既存H鋼: #999 opacity 0.65
- LGS（新設）: #333 opacity 0.75
- PB: fill=#f8f8f8 stroke=#1a1a1a sw=1.2  斜めハッチ=#bbb sw=0.4
- 木材: fill=#efe3c8 stroke=#8a6a3a sw=1.0
- 寸法線・引出し: #888 / #aaa sw=0.6〜0.8
- ラベル文字: #555 font-size=10
"""

# =========================================================
# 規格表（断面寸法 mm）
# =========================================================

HKO_SPECS = {
    # JIS H形鋼（幅×せい×ウェブ×フランジ）例 — 必要に応じ追加
    'H-100x100':  (100, 100,  6,  8),
    'H-125x125':  (125, 125,  6.5, 9),
    'H-150x150':  (150, 150,  7, 10),
    'H-175x175':  (175, 175,  7.5, 11),
    'H-200x200':  (200, 200,  8, 12),
    'H-250x250':  (250, 250,  9, 14),
    'H-300x300':  (300, 300, 10, 15),
    # 細幅系（梁用）
    'H-200x100':  (100, 200,  5.5, 8),
    'H-250x125':  (125, 250,  6,   9),
    'H-300x150':  (150, 300,  6.5, 9),
    'H-350x175':  (175, 350,  7,  11),
    'H-400x200':  (200, 400,  8,  13),
}

# LGS規格（B=せい、H=フランジ幅、t=板厚） JIS G 3302 / JIS A 6517 相当
LGS_SPECS = {
    # 間仕切り用
    'LGS45':  {'B': 45,  'H_stud': 45,  'H_runner': 40, 't': 0.8},
    'LGS50':  {'B': 50,  'H_stud': 45,  'H_runner': 40, 't': 0.8},
    'LGS65':  {'B': 65,  'H_stud': 45,  'H_runner': 40, 't': 0.8},
    'LGS75':  {'B': 75,  'H_stud': 45,  'H_runner': 40, 't': 0.8},
    'LGS90':  {'B': 90,  'H_stud': 45,  'H_runner': 40, 't': 0.8},
    'LGS100': {'B': 100, 'H_stud': 45,  'H_runner': 40, 't': 0.8},
}

# C形鋼（JIS G 3350相当、軽溝形鋼）せい×幅×リップ×板厚
C_SPECS = {
    'C-60x30':   (60, 30, 10, 1.6),
    'C-75x45':   (75, 45, 15, 2.3),
    'C-100x50':  (100, 50, 20, 2.3),
    'C-125x50':  (125, 50, 20, 2.3),
    'C-150x65':  (150, 65, 20, 2.3),
}

# 木材規格（幅×せい mm）
WOOD_SPECS = {
    '30x40':   (30, 40),
    '45x45':   (45, 45),    # 間柱（基本）
    '30x105':  (30, 105),   # 間柱（壁厚大）
    '45x105':  (45, 105),   # 間柱（真壁）
    '105x105': (105, 105),  # 柱
    '45x60':   (45, 60),    # 胴縁・垂木小
    '45x90':   (45, 90),    # 垂木・根太
    '60x90':   (60, 90),
    '90x90':   (90, 90),
}

# ボード板厚（mm）
BOARD_THK = {
    'PB9.5':   9.5,
    'PB12.5':  12.5,
    'PB15':    15.0,
    'PLY9':    9.0,
    'PLY12':   12.0,
    'PLY24':   24.0,
    'KEIKAL6': 6.0,
    'KEIKAL8': 8.0,
}


# =========================================================
# <defs> — マーカー定義（ファイル先頭に1回だけ出力）
# =========================================================

def draw_defs():
    """SVGマーカー・共通パターン定義。<svg>直下に1回だけ入れる。"""
    return '''
<defs>
  <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5"
    markerWidth="5" markerHeight="5" orient="auto-start-reverse">
    <path d="M2 2L8 5L2 8" fill="none" stroke="context-stroke" stroke-width="1.2"/>
  </marker>
  <marker id="dot" viewBox="0 0 6 6" refX="3" refY="3"
    markerWidth="4" markerHeight="4">
    <circle cx="3" cy="3" r="1.6" fill="context-stroke"/>
  </marker>
  <pattern id="hatchPB" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
    <line x1="0" y1="0" x2="0" y2="6" stroke="#bbb" stroke-width="0.6"/>
  </pattern>
  <pattern id="hatchWood" width="4" height="4" patternUnits="userSpaceOnUse">
    <path d="M0 4 Q1 2 2 4 T4 4" stroke="#8a6a3a" stroke-width="0.4" fill="none" opacity="0.5"/>
  </pattern>
  <pattern id="hatchPly" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(30)">
    <line x1="0" y1="0" x2="0" y2="8" stroke="#a88658" stroke-width="0.5"/>
  </pattern>
</defs>'''


# =========================================================
# H鋼（I形断面）
# =========================================================

def draw_hko(cx, y, spec='H-150x150', scale=1.0, existing=True, label=None):
    """
    H鋼断面（I形）。cx=中心x、y=上フランジ上端y。
    existing=True で既存扱い（グレー薄）／False で新設扱い（濃色）。
    """
    B, H, tw, tf = HKO_SPECS[spec]
    s = scale
    w_b = B * s              # フランジ幅(px)
    h_all = H * s            # 全せい
    h_tf = tf * s            # フランジ厚
    w_tw = tw * s            # ウェブ厚
    h_web = h_all - 2 * h_tf # ウェブ高

    x_left = cx - w_b / 2
    x_web  = cx - w_tw / 2
    y_top  = y
    y_web  = y + h_tf
    y_btm  = y + h_all - h_tf

    color = '#999' if existing else '#444'
    opa   = '0.65' if existing else '0.85'
    stroke = '#1a1a1a'

    svg = f'''
<!-- H鋼 {spec} -->
<g class="part-hko">
  <rect x="{x_left:.2f}" y="{y_top:.2f}"  width="{w_b:.2f}" height="{h_tf:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.8"/>
  <rect x="{x_web:.2f}"  y="{y_web:.2f}"  width="{w_tw:.2f}" height="{h_web:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.8"/>
  <rect x="{x_left:.2f}" y="{y_btm:.2f}"  width="{w_b:.2f}" height="{h_tf:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.8"/>
</g>'''
    if label:
        svg += draw_label_right(x_left + w_b, y_top + h_all / 2, label)
    return svg


# =========================================================
# LGS ランナー（コの字断面）
# =========================================================

def draw_lgs_runner(cx, y, spec='LGS65', scale=1.0, direction='down'):
    """
    LGSランナー断面。コの字。direction='down'=口が下向き（天井付け）、'up'=口が上向き（床付け）。
    cx=中心x、y=ランナー外形の基準辺（directionが'down'なら上端、'up'なら下端）。
    """
    sp = LGS_SPECS[spec]
    B = sp['B']; H = sp['H_runner']; t = sp['t']
    s = scale
    w = B * s          # 底板幅
    h = H * s          # 立上り高
    th = max(t * s, 1.5)  # 見やすさのため最小1.5px

    x_left = cx - w / 2
    color = '#333'
    opa = '0.75'
    stroke = '#1a1a1a'

    if direction == 'down':
        # 口が下 → 底板が上端、立上りが下に伸びる
        y_base = y
        svg = f'''
<!-- LGSランナー {spec}（口↓） -->
<g class="part-lgs-runner">
  <rect x="{x_left:.2f}" y="{y_base:.2f}" width="{w:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>
  <rect x="{x_left:.2f}" y="{y_base + th:.2f}" width="{th:.2f}" height="{h - th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>
  <rect x="{cx + w / 2 - th:.2f}" y="{y_base + th:.2f}" width="{th:.2f}" height="{h - th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>
</g>'''
    else:
        # 口が上 → 底板が下端、立上りが上に伸びる
        y_base = y - h  # 底板上端
        svg = f'''
<!-- LGSランナー {spec}（口↑） -->
<g class="part-lgs-runner">
  <rect x="{x_left:.2f}" y="{y - th:.2f}" width="{w:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>
  <rect x="{x_left:.2f}" y="{y_base:.2f}" width="{th:.2f}" height="{h - th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>
  <rect x="{cx + w / 2 - th:.2f}" y="{y_base:.2f}" width="{th:.2f}" height="{h - th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>
</g>'''
    return svg


# =========================================================
# LGS スタッド（縦2本線）
# =========================================================

def draw_lgs_stud(x, y1, y2, spec='LGS65', scale=1.0):
    """
    LGSスタッドを正面から見た姿（縦材）。
    C形断面ではなく「フランジ幅に相当する間隔の縦2本線」で表現する。
    x=左フランジ位置、y1=上端、y2=下端。
    """
    sp = LGS_SPECS[spec]
    B = sp['B']
    s = scale
    w = B * s
    return f'''
<!-- LGSスタッド {spec} -->
<g class="part-lgs-stud" stroke="#333" stroke-width="2.2" opacity="0.85">
  <line x1="{x:.2f}" y1="{y1:.2f}" x2="{x:.2f}" y2="{y2:.2f}"/>
  <line x1="{x + w:.2f}" y1="{y1:.2f}" x2="{x + w:.2f}" y2="{y2:.2f}"/>
</g>'''


# =========================================================
# PB（プラスターボード）— rect + 斜めハッチ
# =========================================================

def draw_pb(x, y1, y2, w=12.5, scale=1.0, hatch=True):
    """
    PB（石膏ボード）断面。
    x=ボード左端x（LGSフランジ外面）、y1=上端、y2=下端、w=板厚mm（既定 t12.5）。
    """
    tw = w * scale
    h = y2 - y1
    fill = 'url(#hatchPB)' if hatch else '#f8f8f8'
    svg = f'''
<!-- PB t{w} -->
<g class="part-pb">
  <rect x="{x:.2f}" y="{y1:.2f}" width="{tw:.2f}" height="{h:.2f}"
        fill="#f8f8f8" stroke="#1a1a1a" stroke-width="1.2"/>'''
    if hatch:
        svg += f'''
  <rect x="{x:.2f}" y="{y1:.2f}" width="{tw:.2f}" height="{h:.2f}" fill="url(#hatchPB)" stroke="none"/>'''
    svg += '\n</g>'
    return svg


# =========================================================
# ボード（合板・ケイカル板）
# =========================================================

def draw_plywood(x, y1, y2, w=12.0, scale=1.0):
    """構造用合板。木目風ハッチ。"""
    tw = w * scale
    h = y2 - y1
    return f'''
<!-- 合板 t{w} -->
<g class="part-ply">
  <rect x="{x:.2f}" y="{y1:.2f}" width="{tw:.2f}" height="{h:.2f}"
        fill="#f3e6cc" stroke="#6a4a20" stroke-width="1.0"/>
  <rect x="{x:.2f}" y="{y1:.2f}" width="{tw:.2f}" height="{h:.2f}"
        fill="url(#hatchPly)" stroke="none"/>
</g>'''


def draw_keical(x, y1, y2, w=6.0, scale=1.0):
    """ケイカル板（ケイ酸カルシウム板）。淡いグレー。"""
    tw = w * scale
    h = y2 - y1
    return f'''
<!-- ケイカル板 t{w} -->
<g class="part-keical">
  <rect x="{x:.2f}" y="{y1:.2f}" width="{tw:.2f}" height="{h:.2f}"
        fill="#e8e8e6" stroke="#555" stroke-width="1.0"/>
  <rect x="{x + tw*0.35:.2f}" y="{y1 + 2:.2f}"
        width="{tw*0.3:.2f}" height="{h - 4:.2f}"
        fill="#d0d0ce" stroke="none" opacity="0.6"/>
</g>'''


# =========================================================
# C形鋼（リップ溝形鋼）
# =========================================================

def draw_c_channel(cx, y, spec='C-75x45', scale=1.0, direction='right'):
    """C形鋼断面。direction='right'=口が右、'left'=口が左。cx=ウェブ中心x、y=上端y。"""
    H, B, lip, t = C_SPECS[spec]
    s = scale
    hpx = H * s; bpx = B * s; lpx = lip * s
    th = max(t * s, 1.2)
    stroke = '#1a1a1a'
    color = '#444'; opa = '0.85'

    if direction == 'right':
        x_web = cx - th / 2
        # ウェブ
        web = f'<rect x="{x_web:.2f}" y="{y:.2f}" width="{th:.2f}" height="{hpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>'
        # 上下フランジ
        top = f'<rect x="{cx - th/2:.2f}" y="{y:.2f}" width="{bpx:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>'
        btm = f'<rect x="{cx - th/2:.2f}" y="{y + hpx - th:.2f}" width="{bpx:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>'
        # 上下リップ
        l_top = f'<rect x="{cx - th/2 + bpx - th:.2f}" y="{y:.2f}" width="{th:.2f}" height="{lpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>'
        l_btm = f'<rect x="{cx - th/2 + bpx - th:.2f}" y="{y + hpx - lpx:.2f}" width="{th:.2f}" height="{lpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>'
    else:
        x_web = cx - th / 2
        web = f'<rect x="{x_web:.2f}" y="{y:.2f}" width="{th:.2f}" height="{hpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>'
        top = f'<rect x="{cx + th/2 - bpx:.2f}" y="{y:.2f}" width="{bpx:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>'
        btm = f'<rect x="{cx + th/2 - bpx:.2f}" y="{y + hpx - th:.2f}" width="{bpx:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>'
        l_top = f'<rect x="{cx + th/2 - bpx:.2f}" y="{y:.2f}" width="{th:.2f}" height="{lpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>'
        l_btm = f'<rect x="{cx + th/2 - bpx:.2f}" y="{y + hpx - lpx:.2f}" width="{th:.2f}" height="{lpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="{stroke}" stroke-width="0.6"/>'
    return f'<!-- C形鋼 {spec} --><g class="part-c">{web}{top}{btm}{l_top}{l_btm}</g>'


# =========================================================
# 木材（間柱・胴縁・垂木・根太）
# =========================================================

def draw_wood_stud(cx, y, spec='45x105', scale=1.0, orientation='vertical', label=None):
    """
    木材断面。cx=中心x、y=上端y。orientation='vertical'は実寸で正立。
    spec='45x105'は幅45×せい105mm。回転木目は簡易表現。
    """
    W, H = WOOD_SPECS[spec]
    s = scale
    wpx = W * s; hpx = H * s
    x_left = cx - wpx / 2
    svg = f'''
<!-- 木材 {spec} -->
<g class="part-wood">
  <rect x="{x_left:.2f}" y="{y:.2f}" width="{wpx:.2f}" height="{hpx:.2f}"
        fill="#efe3c8" stroke="#8a6a3a" stroke-width="1.0"/>
  <rect x="{x_left:.2f}" y="{y:.2f}" width="{wpx:.2f}" height="{hpx:.2f}"
        fill="url(#hatchWood)" stroke="none"/>
  <line x1="{x_left + wpx*0.3:.2f}" y1="{y + hpx*0.15:.2f}"
        x2="{x_left + wpx*0.3:.2f}" y2="{y + hpx*0.85:.2f}"
        stroke="#8a6a3a" stroke-width="0.3" opacity="0.6"/>
  <line x1="{x_left + wpx*0.7:.2f}" y1="{y + hpx*0.15:.2f}"
        x2="{x_left + wpx*0.7:.2f}" y2="{y + hpx*0.85:.2f}"
        stroke="#8a6a3a" stroke-width="0.3" opacity="0.6"/>
</g>'''
    if label:
        svg += draw_label_right(cx + wpx / 2, y + hpx / 2, label)
    return svg


# =========================================================
# ビス・アンカー・ボルト
# =========================================================

def draw_screw_coarse(x, y, length=25, scale=1.0, orientation='horizontal'):
    """
    コーススレッド／ドリルビス（簡易）。x,y=頭の中心。
    orientation='horizontal'=右向き、'vertical'=下向き。
    """
    s = scale
    L = length * s
    head_r = 2.0
    shaft_w = 1.2

    if orientation == 'horizontal':
        return f'''
<!-- ビス L{length} -->
<g class="part-screw" stroke="#222" stroke-width="0.6">
  <circle cx="{x:.2f}" cy="{y:.2f}" r="{head_r}" fill="#666"/>
  <line x1="{x:.2f}" y1="{y - head_r:.2f}" x2="{x:.2f}" y2="{y + head_r:.2f}"/>
  <rect x="{x:.2f}" y="{y - shaft_w/2:.2f}" width="{L:.2f}" height="{shaft_w:.2f}" fill="#888"/>
  <polygon points="{x + L:.2f},{y - shaft_w/2:.2f} {x + L + 2:.2f},{y:.2f} {x + L:.2f},{y + shaft_w/2:.2f}" fill="#888"/>
</g>'''
    else:
        return f'''
<!-- ビス L{length} -->
<g class="part-screw" stroke="#222" stroke-width="0.6">
  <circle cx="{x:.2f}" cy="{y:.2f}" r="{head_r}" fill="#666"/>
  <line x1="{x - head_r:.2f}" y1="{y:.2f}" x2="{x + head_r:.2f}" y2="{y:.2f}"/>
  <rect x="{x - shaft_w/2:.2f}" y="{y:.2f}" width="{shaft_w:.2f}" height="{L:.2f}" fill="#888"/>
  <polygon points="{x - shaft_w/2:.2f},{y + L:.2f} {x:.2f},{y + L + 2:.2f} {x + shaft_w/2:.2f},{y + L:.2f}" fill="#888"/>
</g>'''


def draw_anchor(cx, y, label='アンカーボルト'):
    """
    アンカーボルト（上引出し表記）。cx=ボルト中心、y=ボルト頭の基準y。
    sekozu-framework準拠の二重円＋上引出し。
    """
    return f'''
<!-- アンカーボルト -->
<g class="part-anchor">
  <circle cx="{cx:.2f}" cy="{y:.2f}" r="5" fill="none" stroke="#1a1a1a" stroke-width="1.2"/>
  <circle cx="{cx:.2f}" cy="{y:.2f}" r="2" fill="#1a1a1a"/>
  <line x1="{cx:.2f}" y1="{y - 6:.2f}" x2="{cx:.2f}" y2="{y - 22:.2f}" stroke="#aaa" stroke-width="0.6"/>
  <line x1="{cx:.2f}" y1="{y - 22:.2f}" x2="{cx - 28:.2f}" y2="{y - 22:.2f}" stroke="#aaa" stroke-width="0.6"/>
  <text x="{cx - 30:.2f}" y="{y - 25:.2f}" text-anchor="end" font-size="10" fill="#555" font-family="Meiryo, 'Yu Gothic', sans-serif">{label}</text>
</g>'''


def draw_bolt_hex(cx, cy, d=12, scale=1.0):
    """六角ボルト頭（平面）。cx,cy=中心、d=対辺距離mm。"""
    s = scale
    r = (d / 2) * s * 1.15  # 対角寸法
    import math
    pts = []
    for i in range(6):
        ang = math.radians(30 + 60 * i)
        pts.append(f'{cx + r * math.cos(ang):.2f},{cy + r * math.sin(ang):.2f}')
    return f'''
<!-- 六角ボルト M{d} -->
<polygon points="{' '.join(pts)}" fill="#888" stroke="#1a1a1a" stroke-width="0.6"/>
<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r*0.35:.2f}" fill="none" stroke="#1a1a1a" stroke-width="0.5"/>'''


# =========================================================
# ラベル引出し
# =========================================================

def draw_label_right(x, cy, text, length=14):
    """
    右引出しラベル。x=部材右端x、cy=引出し線の高さ。
    """
    x2 = x + length
    return f'''<g class="label-right">
  <line x1="{x:.2f}" y1="{cy:.2f}" x2="{x2:.2f}" y2="{cy:.2f}" stroke="#aaa" stroke-width="0.6"/>
  <text x="{x2 + 2:.2f}" y="{cy + 4:.2f}" font-size="10" fill="#555" font-family="Meiryo, 'Yu Gothic', sans-serif">{text}</text>
</g>'''


def draw_label_left(x, cy, text, length=14):
    """左引出しラベル。x=部材左端x、cy=引出し線の高さ。"""
    x2 = x - length
    return f'''<g class="label-left">
  <line x1="{x:.2f}" y1="{cy:.2f}" x2="{x2:.2f}" y2="{cy:.2f}" stroke="#aaa" stroke-width="0.6"/>
  <text x="{x2 - 2:.2f}" y="{cy + 4:.2f}" text-anchor="end" font-size="10" fill="#555" font-family="Meiryo, 'Yu Gothic', sans-serif">{text}</text>
</g>'''


def draw_label_top(cx, y, text, length=16):
    """上引出しラベル。cx=部材中心x、y=部材上端y。"""
    y2 = y - length
    return f'''<g class="label-top">
  <line x1="{cx:.2f}" y1="{y:.2f}" x2="{cx:.2f}" y2="{y2:.2f}" stroke="#aaa" stroke-width="0.6"/>
  <text x="{cx:.2f}" y="{y2 - 3:.2f}" text-anchor="middle" font-size="10" fill="#555" font-family="Meiryo, 'Yu Gothic', sans-serif">{text}</text>
</g>'''


# =========================================================
# 寸法線
# =========================================================

def dim_horizontal(x1, x2, y, text, ext_from_y=None):
    """水平寸法線。x1〜x2、y=寸法線y、text=寸法値。ext_from_y=引出し元y（任意）。"""
    mid = (x1 + x2) / 2
    ext = ''
    if ext_from_y is not None:
        ext = f'''
  <line x1="{x1:.2f}" y1="{ext_from_y:.2f}" x2="{x1:.2f}" y2="{y + 4:.2f}" stroke="#888" stroke-width="0.5" opacity="0.5"/>
  <line x1="{x2:.2f}" y1="{ext_from_y:.2f}" x2="{x2:.2f}" y2="{y + 4:.2f}" stroke="#888" stroke-width="0.5" opacity="0.5"/>'''
    return f'''<g class="dim-h">
  <line x1="{x1:.2f}" y1="{y:.2f}" x2="{x2:.2f}" y2="{y:.2f}"
        stroke="#888" stroke-width="0.8" marker-start="url(#arr)" marker-end="url(#arr)"/>
  <text x="{mid:.2f}" y="{y - 3:.2f}" text-anchor="middle" font-size="10" fill="#333" font-family="Meiryo, 'Yu Gothic', sans-serif">{text}</text>{ext}
</g>'''


def dim_vertical(x, y1, y2, text, ext_from_x=None):
    """垂直寸法線。"""
    mid = (y1 + y2) / 2
    ext = ''
    if ext_from_x is not None:
        ext = f'''
  <line x1="{ext_from_x:.2f}" y1="{y1:.2f}" x2="{x + 4:.2f}" y2="{y1:.2f}" stroke="#888" stroke-width="0.5" opacity="0.5"/>
  <line x1="{ext_from_x:.2f}" y1="{y2:.2f}" x2="{x + 4:.2f}" y2="{y2:.2f}" stroke="#888" stroke-width="0.5" opacity="0.5"/>'''
    return f'''<g class="dim-v">
  <line x1="{x:.2f}" y1="{y1:.2f}" x2="{x:.2f}" y2="{y2:.2f}"
        stroke="#888" stroke-width="0.8" marker-start="url(#arr)" marker-end="url(#arr)"/>
  <text x="{x - 4:.2f}" y="{mid:.2f}" text-anchor="end" font-size="10" fill="#333" font-family="Meiryo, 'Yu Gothic', sans-serif" transform="rotate(-90 {x - 4:.2f} {mid:.2f})">{text}</text>{ext}
</g>'''


# =========================================================
# デモ／テスト用（直接実行すると部品カタログSVGを出力）
# =========================================================

def _demo_catalog():
    """全部品を並べたカタログSVGを生成。"""
    parts = [draw_defs()]

    # タイトル
    parts.append('<text x="20" y="28" font-size="18" font-family="Meiryo" fill="#1e2d40" font-weight="bold">施工図部品ライブラリ v1.0</text>')
    parts.append('<text x="20" y="46" font-size="11" font-family="Meiryo" fill="#555">株式会社アート・レイズ / sekozu_parts.py</text>')

    # H鋼
    parts.append('<text x="20" y="90" font-size="12" font-family="Meiryo" fill="#333" font-weight="bold">■ H鋼（実寸 scale=1.0）</text>')
    parts.append(draw_hko(cx=90,  y=110, spec='H-100x100', label='H-100×100'))
    parts.append(draw_hko(cx=260, y=110, spec='H-150x150', label='H-150×150'))
    parts.append(draw_hko(cx=460, y=110, spec='H-200x200', label='H-200×200'))

    # LGS
    parts.append('<text x="20" y="360" font-size="12" font-family="Meiryo" fill="#333" font-weight="bold">■ LGSランナー（口↓＝天井付）／スタッド（縦2本線）</text>')
    parts.append(draw_lgs_runner(cx=100, y=380, spec='LGS65', direction='down'))
    parts.append(draw_label_right(140, 400, 'LGS65ランナー（口↓）'))
    parts.append(draw_lgs_runner(cx=100, y=520, spec='LGS65', direction='up'))
    parts.append(draw_label_right(140, 500, 'LGS65ランナー（口↑）'))
    parts.append(draw_lgs_stud(x=330, y1=380, y2=520, spec='LGS65'))
    parts.append(draw_label_right(395, 450, 'LGS65スタッド（正面）'))

    # C形鋼
    parts.append('<text x="20" y="580" font-size="12" font-family="Meiryo" fill="#333" font-weight="bold">■ C形鋼</text>')
    parts.append(draw_c_channel(cx=80,  y=600, spec='C-75x45',  direction='right'))
    parts.append(draw_label_right(130, 640, 'C-75×45'))
    parts.append(draw_c_channel(cx=300, y=600, spec='C-100x50', direction='right'))
    parts.append(draw_label_right(360, 650, 'C-100×50'))

    # 木材
    parts.append('<text x="20" y="770" font-size="12" font-family="Meiryo" fill="#333" font-weight="bold">■ 木材</text>')
    parts.append(draw_wood_stud(cx=60,  y=790, spec='45x45',   label='45×45'))
    parts.append(draw_wood_stud(cx=160, y=790, spec='45x105',  label='45×105'))
    parts.append(draw_wood_stud(cx=280, y=790, spec='105x105', label='105×105 柱'))
    parts.append(draw_wood_stud(cx=430, y=790, spec='45x90',   label='45×90 垂木'))

    # ボード
    parts.append('<text x="20" y="920" font-size="12" font-family="Meiryo" fill="#333" font-weight="bold">■ ボード類（t=実寸mm×10で拡大表示）</text>')
    parts.append(draw_pb(x=60, y1=940, y2=1040, w=12.5, scale=4))
    parts.append(draw_label_right(60 + 12.5*4, 990, 'PB t12.5'))
    parts.append(draw_plywood(x=200, y1=940, y2=1040, w=12, scale=4))
    parts.append(draw_label_right(200 + 12*4, 990, '合板 t12'))
    parts.append(draw_keical(x=340, y1=940, y2=1040, w=8, scale=4))
    parts.append(draw_label_right(340 + 8*4, 990, 'ケイカル板 t8'))

    # ビス・アンカー
    parts.append('<text x="520" y="580" font-size="12" font-family="Meiryo" fill="#333" font-weight="bold">■ 留め付け</text>')
    parts.append(draw_screw_coarse(x=540, y=610, length=32, orientation='horizontal'))
    parts.append(draw_label_right(540 + 32 + 4, 610, 'コーススレッド L32'))
    parts.append(draw_screw_coarse(x=540, y=640, length=25, orientation='horizontal'))
    parts.append(draw_label_right(540 + 25 + 4, 640, 'ドリルビス L25'))
    parts.append(draw_anchor(cx=600, y=720))
    parts.append(draw_bolt_hex(cx=680, cy=720, d=12))
    parts.append(draw_label_right(695, 720, '六角ボルト M12'))

    body = '\n'.join(parts)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 1074" width="760" height="1074"
     style="background:#fff; font-family:Meiryo,'Yu Gothic',sans-serif;">
{body}
</svg>'''


if __name__ == '__main__':
    import os
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sekozu_parts_catalog.svg')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(_demo_catalog())
    print(f'カタログSVGを出力しました: {out}')
