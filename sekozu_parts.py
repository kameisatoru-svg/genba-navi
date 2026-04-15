# -*- coding: utf-8 -*-
"""
sekozu_parts.py
施工図フレームワーク 断面部材ライブラリ v2.0（縦断面・横断面対応版）

株式会社アート・レイズ / 現場ナビPRO
置き場所: C:\\Users\\user\\artrays\\claude ai\\genba-navi\\

■ 設計方針（v2.0で再設計）
施工図の「縦断面（鉛直断面）」と「横断面（水平断面＝平面詳細）」では
同じ部材でも見え方が全く違う。関数名の接尾辞で明確に分ける。

  _section : 縦断面（壁を横から切った図）用
  _plan    : 横断面（壁を上から見下ろした平面詳細図）用

各断面での部材の見え方：

┌────────────┬───────────────────────┬───────────────────────────┐
│ 部材       │ 縦断面 _section        │ 横断面 _plan               │
├────────────┼───────────────────────┼───────────────────────────┤
│ H鋼        │ I形断面                │ I形断面（水平向き）        │
│ C形鋼      │ リップ付コの字         │ リップ付コの字（水平）     │
│ LGSランナー│ コの字（口↑↓）        │ 見えない（切断位置外）     │
│ LGSスタッド│ 縦2本線（フランジ側面）│ C形断面×複数（@303/@455） │
│ 木材       │ 縦長長方形＋木目       │ 正方形/長方形×複数         │
│ PB         │ 縦帯＋斜めハッチ       │ 横帯＋斜めハッチ           │
│ 合板       │ 縦帯＋木目ハッチ       │ 横帯＋木目ハッチ           │
│ ケイカル板 │ 縦帯＋淡グレー         │ 横帯＋淡グレー             │
│ ビス       │ 横向き矢印             │ 横向き矢印                 │
│ アンカー   │ 二重円＋上引出し       │ 二重円＋引出し             │
└────────────┴───────────────────────┴───────────────────────────┘

■ 引数の約束
- scale : mm→px 変換比（既定1.0＝実寸、0.5＝1/2縮尺）
- cx, cy : 中心座標（px）
- x, y   : 左上基準座標（px）
- y1, y2 / x1, x2 : 範囲指定
- spec   : 規格名（辞書キー）

■ 使い方（縦断面例）
    from sekozu_parts import *
    svg_parts = [draw_defs()]
    svg_parts.append(draw_hko_section(cx=200, y=400, spec='H-150x150'))
    svg_parts.append(draw_lgs_runner_section(cx=200, y=460, spec='LGS65', direction='down'))
    svg_parts.append(draw_lgs_stud_section(x=170, y1=480, y2=700, spec='LGS65'))
    svg_parts.append(draw_pb_section(x=174, y1=480, y2=700, w=12.5))
    svg_parts.append(draw_label_right(x=230, cy=600, text='化粧PB t12.5'))

■ 使い方（横断面例）
    svg_parts.append(draw_lgs_array_plan(x0=100, cy=500, spec='LGS65',
                                         count=6, pitch=455, scale=0.5))
    svg_parts.append(draw_pb_plan(x1=80, x2=400, y=480, w=12.5, scale=0.5))
    svg_parts.append(draw_pb_plan(x1=80, x2=400, y=535, w=12.5, scale=0.5))
"""

import math


# =========================================================
# 規格表（断面寸法 mm）
# =========================================================

HKO_SPECS = {
    'H-100x100':  (100, 100,  6,  8),
    'H-125x125':  (125, 125,  6.5, 9),
    'H-150x150':  (150, 150,  7, 10),
    'H-175x175':  (175, 175,  7.5, 11),
    'H-200x200':  (200, 200,  8, 12),
    'H-250x250':  (250, 250,  9, 14),
    'H-300x300':  (300, 300, 10, 15),
    'H-200x100':  (100, 200,  5.5, 8),
    'H-250x125':  (125, 250,  6,   9),
    'H-300x150':  (150, 300,  6.5, 9),
    'H-350x175':  (175, 350,  7,  11),
    'H-400x200':  (200, 400,  8,  13),
}

# LGS規格 JIS A 6517
# B=せい（フランジ幅方向）、flange=フランジ幅、t=板厚
# スタッドとランナーはフランジ幅が異なるのが普通
LGS_SPECS = {
    'LGS45':  {'B': 45,  'stud_f': 45, 'runner_f': 40, 't': 0.8, 'lip': 10},
    'LGS50':  {'B': 50,  'stud_f': 45, 'runner_f': 40, 't': 0.8, 'lip': 10},
    'LGS65':  {'B': 65,  'stud_f': 45, 'runner_f': 40, 't': 0.8, 'lip': 10},
    'LGS75':  {'B': 75,  'stud_f': 45, 'runner_f': 40, 't': 0.8, 'lip': 10},
    'LGS90':  {'B': 90,  'stud_f': 45, 'runner_f': 40, 't': 0.8, 'lip': 10},
    'LGS100': {'B': 100, 'stud_f': 50, 'runner_f': 45, 't': 0.8, 'lip': 10},
}

# C形鋼 JIS G 3350
C_SPECS = {
    'C-60x30':   (60, 30, 10, 1.6),
    'C-75x45':   (75, 45, 15, 2.3),
    'C-100x50':  (100, 50, 20, 2.3),
    'C-125x50':  (125, 50, 20, 2.3),
    'C-150x65':  (150, 65, 20, 2.3),
}

# 木材規格（幅 mm × せい mm）
WOOD_SPECS = {
    '30x40':   (30, 40),
    '45x45':   (45, 45),
    '30x105':  (30, 105),
    '45x105':  (45, 105),
    '105x105': (105, 105),
    '45x60':   (45, 60),
    '45x90':   (45, 90),
    '60x90':   (60, 90),
    '90x90':   (90, 90),
}

# 標準ピッチ（mm）
STANDARD_PITCH = {
    'LGS@303':   303,
    'LGS@455':   455,
    'wood@303':  303,  # 木造間柱 一尺
    'wood@455':  455,  # 木造間柱 一尺五寸
    'wood@910':  910,
}

# 色・線幅の定数
C = {
    'hko_fill':       '#999',
    'hko_fill_new':   '#444',
    'hko_opa':        '0.65',
    'hko_opa_new':    '0.85',
    'lgs_fill':       '#333',
    'lgs_opa':        '0.75',
    'wood_fill':      '#efe3c8',
    'wood_stroke':    '#8a6a3a',
    'pb_fill':        '#f8f8f8',
    'pb_stroke':      '#1a1a1a',
    'ply_fill':       '#f3e6cc',
    'ply_stroke':     '#6a4a20',
    'keical_fill':    '#e8e8e6',
    'keical_stroke':  '#555',
    'dim':            '#888',
    'ext':            '#aaa',
    'label':          '#555',
    'screw':          '#666',
}


# =========================================================
# <defs> — マーカー＆パターン定義（<svg>直下に1回）
# =========================================================

def draw_defs():
    return '''
<defs>
  <marker id="arr" viewBox="0 0 10 10" refX="8" refY="5"
    markerWidth="5" markerHeight="5" orient="auto-start-reverse">
    <path d="M2 2L8 5L2 8" fill="none" stroke="context-stroke" stroke-width="1.2"/>
  </marker>
  <marker id="tick" viewBox="0 0 10 10" refX="5" refY="5"
    markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <line x1="5" y1="1" x2="5" y2="9" stroke="context-stroke" stroke-width="1.2"/>
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
  <pattern id="hatchConc" width="8" height="8" patternUnits="userSpaceOnUse">
    <circle cx="2" cy="2" r="0.5" fill="#888"/>
    <circle cx="6" cy="5" r="0.4" fill="#888"/>
    <circle cx="3" cy="6" r="0.3" fill="#888"/>
  </pattern>
</defs>'''


# =========================================================
# H鋼
# =========================================================

def draw_hko_section(cx, y, spec='H-150x150', scale=1.0, existing=True, label=None):
    """
    縦断面用 H鋼 I形断面（梁を長手と直交方向に切った姿）。
    cx=中心x、y=上フランジ上端y。
    """
    B, H, tw, tf = HKO_SPECS[spec]
    s = scale
    w_b = B * s; h_all = H * s; h_tf = tf * s; w_tw = tw * s
    h_web = h_all - 2 * h_tf
    x_left = cx - w_b / 2
    x_web  = cx - w_tw / 2
    color = C['hko_fill']     if existing else C['hko_fill_new']
    opa   = C['hko_opa']      if existing else C['hko_opa_new']
    svg = f'''
<!-- H鋼 {spec}（縦断面） -->
<g class="part-hko-s">
  <rect x="{x_left:.2f}" y="{y:.2f}" width="{w_b:.2f}" height="{h_tf:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.8"/>
  <rect x="{x_web:.2f}"  y="{y + h_tf:.2f}" width="{w_tw:.2f}" height="{h_web:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.8"/>
  <rect x="{x_left:.2f}" y="{y + h_all - h_tf:.2f}" width="{w_b:.2f}" height="{h_tf:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.8"/>
</g>'''
    if label:
        svg += draw_label_right(x_left + w_b, y + h_all / 2, label)
    return svg


def draw_hko_plan(cx, cy, spec='H-150x150', scale=1.0, existing=True, rotate=0, label=None):
    """
    横断面用 H鋼。平面詳細では「梁を上から見下ろした」水平向きのI形が現れる。
    cx, cy = 中心。rotate=90 で縦向きに回転。
    """
    B, H, tw, tf = HKO_SPECS[spec]
    s = scale
    w_b = B * s; h_all = H * s; h_tf = tf * s; w_tw = tw * s
    color = C['hko_fill']  if existing else C['hko_fill_new']
    opa   = C['hko_opa']   if existing else C['hko_opa_new']
    # I形を水平向きに描く（長手方向が水平）
    # 左右フランジ（短辺）＋中央ウェブ（長辺）
    x_left = cx - h_all / 2   # 水平向き：長手=水平軸
    y_top  = cy - w_b / 2
    # 左フランジ
    lf = f'<rect x="{x_left:.2f}" y="{y_top:.2f}" width="{h_tf:.2f}" height="{w_b:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.8"/>'
    # ウェブ
    wb = f'<rect x="{x_left + h_tf:.2f}" y="{cy - w_tw/2:.2f}" width="{h_all - 2*h_tf:.2f}" height="{w_tw:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.8"/>'
    # 右フランジ
    rf = f'<rect x="{x_left + h_all - h_tf:.2f}" y="{y_top:.2f}" width="{h_tf:.2f}" height="{w_b:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.8"/>'
    inner = f'{lf}{wb}{rf}'
    transform = f' transform="rotate({rotate} {cx} {cy})"' if rotate else ''
    svg = f'<!-- H鋼 {spec}（横断面） --><g class="part-hko-p"{transform}>{inner}</g>'
    if label:
        svg += draw_label_right(cx + h_all/2, cy, label)
    return svg


# =========================================================
# C形鋼
# =========================================================

def draw_c_channel_section(cx, y, spec='C-75x45', scale=1.0, direction='right'):
    """縦断面用C形鋼。direction='right'/'left' で口の向き。cx=ウェブ中心x、y=上端y。"""
    H, B, lip, t = C_SPECS[spec]
    s = scale
    hpx = H * s; bpx = B * s; lpx = lip * s
    th = max(t * s, 1.2)
    color = C['hko_fill_new']; opa = C['hko_opa_new']
    if direction == 'right':
        wx = cx - th / 2
        fx = cx - th / 2
        flip_x = fx + bpx - th
    else:
        wx = cx - th / 2
        fx = cx + th / 2 - bpx
        flip_x = fx
    return f'''
<!-- C形鋼 {spec}（縦断面 口{direction}） -->
<g class="part-c-s">
  <rect x="{wx:.2f}" y="{y:.2f}" width="{th:.2f}" height="{hpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.6"/>
  <rect x="{fx:.2f}" y="{y:.2f}" width="{bpx:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.6"/>
  <rect x="{fx:.2f}" y="{y + hpx - th:.2f}" width="{bpx:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.6"/>
  <rect x="{flip_x:.2f}" y="{y:.2f}" width="{th:.2f}" height="{lpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.6"/>
  <rect x="{flip_x:.2f}" y="{y + hpx - lpx:.2f}" width="{th:.2f}" height="{lpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.6"/>
</g>'''


def draw_c_channel_plan(cx, cy, spec='C-75x45', scale=1.0, direction='right'):
    """横断面用C形鋼（母屋・胴縁の平面詳細など）。水平向きに配置。"""
    H, B, lip, t = C_SPECS[spec]
    s = scale
    hpx = H * s; bpx = B * s; lpx = lip * s
    th = max(t * s, 1.2)
    color = C['hko_fill_new']; opa = C['hko_opa_new']
    # 水平向き：せいHが水平方向、フランジBが垂直方向
    x_left = cx - hpx / 2
    y_top = cy - bpx / 2
    if direction == 'right':  # 口が画面上
        web = f'<rect x="{x_left:.2f}" y="{cy - th/2:.2f}" width="{hpx:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.6"/>'
        ft  = f'<rect x="{x_left:.2f}" y="{y_top:.2f}" width="{th:.2f}" height="{bpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.6"/>'
        fb  = f'<rect x="{x_left + hpx - th:.2f}" y="{y_top:.2f}" width="{th:.2f}" height="{bpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.6"/>'
    return f'<!-- C形鋼 {spec}（横断面） --><g class="part-c-p">{web}{ft}{fb}</g>'


# =========================================================
# LGSランナー — 縦断面のみ（横断面では現れない）
# =========================================================

def draw_lgs_runner_section(cx, y, spec='LGS65', scale=1.0, direction='down'):
    """
    縦断面用 LGSランナー（コの字）。
    direction='down' 口↓（天井付）／'up' 口↑（床付）
    cx=中心x、y=ランナー外形基準辺（down:上端 / up:下端）
    """
    sp = LGS_SPECS[spec]
    B = sp['B']; H = sp['runner_f']; t = sp['t']
    s = scale
    w = B * s; h = H * s
    th = max(t * s, 1.5)
    x_left = cx - w / 2
    color = C['lgs_fill']; opa = C['lgs_opa']
    if direction == 'down':
        base = f'<rect x="{x_left:.2f}" y="{y:.2f}" width="{w:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.6"/>'
        l    = f'<rect x="{x_left:.2f}" y="{y + th:.2f}" width="{th:.2f}" height="{h - th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.6"/>'
        r    = f'<rect x="{cx + w/2 - th:.2f}" y="{y + th:.2f}" width="{th:.2f}" height="{h - th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.6"/>'
    else:
        y_base = y - h
        base = f'<rect x="{x_left:.2f}" y="{y - th:.2f}" width="{w:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.6"/>'
        l    = f'<rect x="{x_left:.2f}" y="{y_base:.2f}" width="{th:.2f}" height="{h - th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.6"/>'
        r    = f'<rect x="{cx + w/2 - th:.2f}" y="{y_base:.2f}" width="{th:.2f}" height="{h - th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.6"/>'
    return f'<!-- LGSランナー {spec}（縦断面 口{direction}） --><g class="part-lgs-runner-s">{base}{l}{r}</g>'


# =========================================================
# LGSスタッド
# =========================================================

def draw_lgs_stud_section(x, y1, y2, spec='LGS65', scale=1.0):
    """
    縦断面用 LGSスタッド（側面姿＝縦2本線）。
    x=左フランジx、y1=上端、y2=下端。
    フランジ幅に相当する間隔で2本の縦線を引く。
    """
    sp = LGS_SPECS[spec]
    B = sp['B']
    s = scale
    w = B * s
    return f'''
<!-- LGSスタッド {spec}（縦断面 側面姿） -->
<g class="part-lgs-stud-s" stroke="{C['lgs_fill']}" stroke-width="2.2" opacity="{C['lgs_opa']}">
  <line x1="{x:.2f}" y1="{y1:.2f}" x2="{x:.2f}" y2="{y2:.2f}"/>
  <line x1="{x + w:.2f}" y1="{y1:.2f}" x2="{x + w:.2f}" y2="{y2:.2f}"/>
</g>'''


def draw_lgs_stud_plan(cx, cy, spec='LGS65', scale=1.0, direction='right'):
    """
    横断面用 LGSスタッド（C形断面×1本）。
    cx, cy = スタッド中心。direction='right'/'left'=リップ向き。
    B（せい）は水平方向、flange_f（フランジ）は垂直方向に配置される想定
    （実際の壁では壁厚方向にB、壁長手方向にflange_fが来る）。
    """
    sp = LGS_SPECS[spec]
    # 壁の厚み方向＝Bがy方向に、flange_f=x方向になるよう回転
    B = sp['B']; fl = sp['stud_f']; t = sp['t']; lip = sp['lip']
    s = scale
    hpx = B * s       # 水平方向（壁厚方向）
    bpx = fl * s      # 垂直方向（壁長手方向）
    lpx = lip * s
    th = max(t * s, 1.0)
    color = C['lgs_fill']; opa = C['lgs_opa']
    x_left = cx - hpx / 2
    y_top  = cy - bpx / 2
    if direction == 'right':
        web  = f'<rect x="{x_left + hpx - th:.2f}" y="{y_top:.2f}" width="{th:.2f}" height="{bpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.5"/>'
        ft   = f'<rect x="{x_left:.2f}" y="{y_top:.2f}" width="{hpx:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.5"/>'
        fb   = f'<rect x="{x_left:.2f}" y="{y_top + bpx - th:.2f}" width="{hpx:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.5"/>'
        lipT = f'<rect x="{x_left:.2f}" y="{y_top:.2f}" width="{th:.2f}" height="{lpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.5"/>'
        lipB = f'<rect x="{x_left:.2f}" y="{y_top + bpx - lpx:.2f}" width="{th:.2f}" height="{lpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.5"/>'
    else:
        web  = f'<rect x="{x_left:.2f}" y="{y_top:.2f}" width="{th:.2f}" height="{bpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.5"/>'
        ft   = f'<rect x="{x_left:.2f}" y="{y_top:.2f}" width="{hpx:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.5"/>'
        fb   = f'<rect x="{x_left:.2f}" y="{y_top + bpx - th:.2f}" width="{hpx:.2f}" height="{th:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.5"/>'
        lipT = f'<rect x="{x_left + hpx - th:.2f}" y="{y_top:.2f}" width="{th:.2f}" height="{lpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.5"/>'
        lipB = f'<rect x="{x_left + hpx - th:.2f}" y="{y_top + bpx - lpx:.2f}" width="{th:.2f}" height="{lpx:.2f}" fill="{color}" fill-opacity="{opa}" stroke="#1a1a1a" stroke-width="0.5"/>'
    return f'<!-- LGSスタッド {spec}（横断面 C形 口{direction}） --><g class="part-lgs-stud-p">{web}{ft}{fb}{lipT}{lipB}</g>'


def draw_lgs_array_plan(x0, cy, spec='LGS65', count=5, pitch=455, scale=1.0, direction='right'):
    """
    横断面用 LGSスタッドを @pitch で count 本並べる（平面詳細の骨格）。
    x0=先頭スタッド中心x、cy=全スタッド共通中心y。
    """
    parts = []
    step = pitch * scale
    for i in range(count):
        parts.append(draw_lgs_stud_plan(x0 + i * step, cy, spec, scale, direction))
    return f'<!-- LGSスタッド列 @{pitch} ×{count} -->\n' + '\n'.join(parts)


# =========================================================
# 木材
# =========================================================

def draw_wood_section(cx, y, spec='45x105', scale=1.0, label=None):
    """
    縦断面用 木材（間柱・胴縁を側面から見た縦長長方形）。
    cx=中心x、y=上端y。spec='45x105'は幅45×せい105mm。
    """
    W, H = WOOD_SPECS[spec]
    s = scale
    wpx = W * s; hpx = H * s
    x_left = cx - wpx / 2
    svg = f'''
<!-- 木材 {spec}（縦断面） -->
<g class="part-wood-s">
  <rect x="{x_left:.2f}" y="{y:.2f}" width="{wpx:.2f}" height="{hpx:.2f}"
        fill="{C['wood_fill']}" stroke="{C['wood_stroke']}" stroke-width="1.0"/>
  <rect x="{x_left:.2f}" y="{y:.2f}" width="{wpx:.2f}" height="{hpx:.2f}"
        fill="url(#hatchWood)" stroke="none"/>
  <line x1="{x_left + wpx*0.3:.2f}" y1="{y + hpx*0.15:.2f}" x2="{x_left + wpx*0.3:.2f}" y2="{y + hpx*0.85:.2f}" stroke="{C['wood_stroke']}" stroke-width="0.3" opacity="0.6"/>
  <line x1="{x_left + wpx*0.7:.2f}" y1="{y + hpx*0.15:.2f}" x2="{x_left + wpx*0.7:.2f}" y2="{y + hpx*0.85:.2f}" stroke="{C['wood_stroke']}" stroke-width="0.3" opacity="0.6"/>
</g>'''
    if label:
        svg += draw_label_right(cx + wpx / 2, y + hpx / 2, label)
    return svg


def draw_wood_plan(cx, cy, spec='45x105', scale=1.0, orientation='vertical', label=None):
    """
    横断面用 木材（平面詳細で見る間柱の断面）。
    orientation='vertical' なら spec='45x105' の 105 が壁厚方向。
    orientation='horizontal' なら 45 が壁厚方向。
    """
    W, H = WOOD_SPECS[spec]
    s = scale
    if orientation == 'vertical':
        wall_thk_px = H * s   # 壁厚方向＝せい
        long_px = W * s       # 壁長手方向＝幅
    else:
        wall_thk_px = W * s
        long_px = H * s
    x_left = cx - wall_thk_px / 2
    y_top  = cy - long_px / 2
    svg = f'''
<!-- 木材 {spec}（横断面） -->
<g class="part-wood-p">
  <rect x="{x_left:.2f}" y="{y_top:.2f}" width="{wall_thk_px:.2f}" height="{long_px:.2f}"
        fill="{C['wood_fill']}" stroke="{C['wood_stroke']}" stroke-width="1.0"/>
  <rect x="{x_left:.2f}" y="{y_top:.2f}" width="{wall_thk_px:.2f}" height="{long_px:.2f}"
        fill="url(#hatchWood)" stroke="none"/>
  <circle cx="{cx:.2f}" cy="{cy:.2f}" r="{min(wall_thk_px, long_px)*0.15:.2f}" fill="none" stroke="{C['wood_stroke']}" stroke-width="0.4" opacity="0.6"/>
  <circle cx="{cx:.2f}" cy="{cy:.2f}" r="{min(wall_thk_px, long_px)*0.3:.2f}" fill="none" stroke="{C['wood_stroke']}" stroke-width="0.3" opacity="0.5"/>
</g>'''
    if label:
        svg += draw_label_right(cx + wall_thk_px/2, cy, label)
    return svg


def draw_wood_array_plan(x0, cy, spec='45x105', count=5, pitch=455, scale=1.0, orientation='vertical'):
    """横断面用 間柱を@pitchで並べる。"""
    parts = []
    step = pitch * scale
    for i in range(count):
        parts.append(draw_wood_plan(x0 + i * step, cy, spec, scale, orientation))
    return f'<!-- 間柱列 @{pitch} ×{count} -->\n' + '\n'.join(parts)


# =========================================================
# PB（石膏ボード）
# =========================================================

def draw_pb_section(x, y1, y2, w=12.5, scale=1.0, hatch=True):
    """縦断面用 PB（縦帯＋斜めハッチ）。x=ボード左端、y1=上端、y2=下端、w=板厚mm。"""
    tw = w * scale
    h = y2 - y1
    svg = f'''
<!-- PB t{w}（縦断面） -->
<g class="part-pb-s">
  <rect x="{x:.2f}" y="{y1:.2f}" width="{tw:.2f}" height="{h:.2f}"
        fill="{C['pb_fill']}" stroke="{C['pb_stroke']}" stroke-width="1.2"/>'''
    if hatch:
        svg += f'\n  <rect x="{x:.2f}" y="{y1:.2f}" width="{tw:.2f}" height="{h:.2f}" fill="url(#hatchPB)" stroke="none"/>'
    return svg + '\n</g>'


def draw_pb_plan(x1, x2, y, w=12.5, scale=1.0, side='top', hatch=True):
    """
    横断面用 PB（平面詳細で壁の両面に現れる横帯）。
    x1, x2 = 壁長手方向のPB左右端、y = PB外面ライン、w=板厚mm。
    side='top' なら y から下へw、'bottom' なら y から上へw。
    """
    tw = w * scale
    wd = x2 - x1
    if side == 'top':
        y_top = y
    else:
        y_top = y - tw
    svg = f'''
<!-- PB t{w}（横断面 {side}面） -->
<g class="part-pb-p">
  <rect x="{x1:.2f}" y="{y_top:.2f}" width="{wd:.2f}" height="{tw:.2f}"
        fill="{C['pb_fill']}" stroke="{C['pb_stroke']}" stroke-width="1.2"/>'''
    if hatch:
        svg += f'\n  <rect x="{x1:.2f}" y="{y_top:.2f}" width="{wd:.2f}" height="{tw:.2f}" fill="url(#hatchPB)" stroke="none"/>'
    return svg + '\n</g>'


# =========================================================
# 合板
# =========================================================

def draw_plywood_section(x, y1, y2, w=12.0, scale=1.0):
    tw = w * scale; h = y2 - y1
    return f'''
<!-- 合板 t{w}（縦断面） -->
<g class="part-ply-s">
  <rect x="{x:.2f}" y="{y1:.2f}" width="{tw:.2f}" height="{h:.2f}" fill="{C['ply_fill']}" stroke="{C['ply_stroke']}" stroke-width="1.0"/>
  <rect x="{x:.2f}" y="{y1:.2f}" width="{tw:.2f}" height="{h:.2f}" fill="url(#hatchPly)" stroke="none"/>
</g>'''


def draw_plywood_plan(x1, x2, y, w=12.0, scale=1.0, side='top'):
    tw = w * scale; wd = x2 - x1
    y_top = y if side == 'top' else y - tw
    return f'''
<!-- 合板 t{w}（横断面 {side}） -->
<g class="part-ply-p">
  <rect x="{x1:.2f}" y="{y_top:.2f}" width="{wd:.2f}" height="{tw:.2f}" fill="{C['ply_fill']}" stroke="{C['ply_stroke']}" stroke-width="1.0"/>
  <rect x="{x1:.2f}" y="{y_top:.2f}" width="{wd:.2f}" height="{tw:.2f}" fill="url(#hatchPly)" stroke="none"/>
</g>'''


# =========================================================
# ケイカル板
# =========================================================

def draw_keical_section(x, y1, y2, w=6.0, scale=1.0):
    tw = w * scale; h = y2 - y1
    return f'''
<!-- ケイカル板 t{w}（縦断面） -->
<g class="part-keical-s">
  <rect x="{x:.2f}" y="{y1:.2f}" width="{tw:.2f}" height="{h:.2f}" fill="{C['keical_fill']}" stroke="{C['keical_stroke']}" stroke-width="1.0"/>
</g>'''


def draw_keical_plan(x1, x2, y, w=6.0, scale=1.0, side='top'):
    tw = w * scale; wd = x2 - x1
    y_top = y if side == 'top' else y - tw
    return f'''
<!-- ケイカル板 t{w}（横断面 {side}） -->
<g class="part-keical-p">
  <rect x="{x1:.2f}" y="{y_top:.2f}" width="{wd:.2f}" height="{tw:.2f}" fill="{C['keical_fill']}" stroke="{C['keical_stroke']}" stroke-width="1.0"/>
</g>'''


# =========================================================
# ビス・アンカー・ボルト
# =========================================================

def draw_screw_coarse(x, y, length=25, scale=1.0, orientation='horizontal'):
    """コーススレッド／ドリルビス。x,y=頭中心。"""
    s = scale; L = length * s
    hr = 2.0; sw = 1.2
    if orientation == 'horizontal':
        return f'''
<!-- ビス L{length} -->
<g class="part-screw" stroke="#222" stroke-width="0.6">
  <circle cx="{x:.2f}" cy="{y:.2f}" r="{hr}" fill="{C['screw']}"/>
  <line x1="{x:.2f}" y1="{y - hr:.2f}" x2="{x:.2f}" y2="{y + hr:.2f}"/>
  <rect x="{x:.2f}" y="{y - sw/2:.2f}" width="{L:.2f}" height="{sw:.2f}" fill="#888"/>
  <polygon points="{x + L:.2f},{y - sw/2:.2f} {x + L + 2:.2f},{y:.2f} {x + L:.2f},{y + sw/2:.2f}" fill="#888"/>
</g>'''
    else:
        return f'''
<!-- ビス L{length} -->
<g class="part-screw" stroke="#222" stroke-width="0.6">
  <circle cx="{x:.2f}" cy="{y:.2f}" r="{hr}" fill="{C['screw']}"/>
  <line x1="{x - hr:.2f}" y1="{y:.2f}" x2="{x + hr:.2f}" y2="{y:.2f}"/>
  <rect x="{x - sw/2:.2f}" y="{y:.2f}" width="{sw:.2f}" height="{L:.2f}" fill="#888"/>
  <polygon points="{x - sw/2:.2f},{y + L:.2f} {x:.2f},{y + L + 2:.2f} {x + sw/2:.2f},{y + L:.2f}" fill="#888"/>
</g>'''


def draw_anchor(cx, y, label='アンカーボルト', callout='top'):
    """
    アンカーボルト（二重円）＋引出し。callout='top'/'right'/'left'で引出し方向。
    """
    base = f'''
<!-- アンカーボルト -->
<g class="part-anchor">
  <circle cx="{cx:.2f}" cy="{y:.2f}" r="5" fill="none" stroke="#1a1a1a" stroke-width="1.2"/>
  <circle cx="{cx:.2f}" cy="{y:.2f}" r="2" fill="#1a1a1a"/>'''
    if callout == 'top':
        base += f'''
  <line x1="{cx:.2f}" y1="{y - 6:.2f}" x2="{cx:.2f}" y2="{y - 22:.2f}" stroke="{C['ext']}" stroke-width="0.6"/>
  <line x1="{cx:.2f}" y1="{y - 22:.2f}" x2="{cx - 28:.2f}" y2="{y - 22:.2f}" stroke="{C['ext']}" stroke-width="0.6"/>
  <text x="{cx - 30:.2f}" y="{y - 25:.2f}" text-anchor="end" font-size="10" fill="{C['label']}" font-family="Meiryo">{label}</text>'''
    elif callout == 'right':
        base += f'''
  <line x1="{cx + 6:.2f}" y1="{y:.2f}" x2="{cx + 26:.2f}" y2="{y:.2f}" stroke="{C['ext']}" stroke-width="0.6"/>
  <text x="{cx + 28:.2f}" y="{y + 4:.2f}" font-size="10" fill="{C['label']}" font-family="Meiryo">{label}</text>'''
    return base + '\n</g>'


def draw_bolt_hex(cx, cy, d=12, scale=1.0):
    """六角ボルト頭（平面）。"""
    s = scale
    r = (d / 2) * s * 1.15
    pts = []
    for i in range(6):
        ang = math.radians(30 + 60 * i)
        pts.append(f'{cx + r * math.cos(ang):.2f},{cy + r * math.sin(ang):.2f}')
    return f'''
<!-- 六角ボルト M{d} -->
<polygon points="{' '.join(pts)}" fill="#888" stroke="#1a1a1a" stroke-width="0.6"/>
<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r*0.35:.2f}" fill="none" stroke="#1a1a1a" stroke-width="0.5"/>'''


# =========================================================
# ラベル引出し・寸法線
# =========================================================

def draw_label_right(x, cy, text, length=14):
    x2 = x + length
    return f'''<g class="label-right">
  <line x1="{x:.2f}" y1="{cy:.2f}" x2="{x2:.2f}" y2="{cy:.2f}" stroke="{C['ext']}" stroke-width="0.6"/>
  <text x="{x2 + 2:.2f}" y="{cy + 4:.2f}" font-size="10" fill="{C['label']}" font-family="Meiryo">{text}</text>
</g>'''


def draw_label_left(x, cy, text, length=14):
    x2 = x - length
    return f'''<g class="label-left">
  <line x1="{x:.2f}" y1="{cy:.2f}" x2="{x2:.2f}" y2="{cy:.2f}" stroke="{C['ext']}" stroke-width="0.6"/>
  <text x="{x2 - 2:.2f}" y="{cy + 4:.2f}" text-anchor="end" font-size="10" fill="{C['label']}" font-family="Meiryo">{text}</text>
</g>'''


def draw_label_top(cx, y, text, length=16):
    y2 = y - length
    return f'''<g class="label-top">
  <line x1="{cx:.2f}" y1="{y:.2f}" x2="{cx:.2f}" y2="{y2:.2f}" stroke="{C['ext']}" stroke-width="0.6"/>
  <text x="{cx:.2f}" y="{y2 - 3:.2f}" text-anchor="middle" font-size="10" fill="{C['label']}" font-family="Meiryo">{text}</text>
</g>'''


def dim_horizontal(x1, x2, y, text, ext_from_y=None):
    mid = (x1 + x2) / 2
    ext = ''
    if ext_from_y is not None:
        ext = f'''
  <line x1="{x1:.2f}" y1="{ext_from_y:.2f}" x2="{x1:.2f}" y2="{y + 4:.2f}" stroke="{C['dim']}" stroke-width="0.5" opacity="0.5"/>
  <line x1="{x2:.2f}" y1="{ext_from_y:.2f}" x2="{x2:.2f}" y2="{y + 4:.2f}" stroke="{C['dim']}" stroke-width="0.5" opacity="0.5"/>'''
    return f'''<g class="dim-h">
  <line x1="{x1:.2f}" y1="{y:.2f}" x2="{x2:.2f}" y2="{y:.2f}" stroke="{C['dim']}" stroke-width="0.8" marker-start="url(#arr)" marker-end="url(#arr)"/>
  <text x="{mid:.2f}" y="{y - 3:.2f}" text-anchor="middle" font-size="10" fill="#333" font-family="Meiryo">{text}</text>{ext}
</g>'''


def dim_vertical(x, y1, y2, text, ext_from_x=None):
    mid = (y1 + y2) / 2
    ext = ''
    if ext_from_x is not None:
        ext = f'''
  <line x1="{ext_from_x:.2f}" y1="{y1:.2f}" x2="{x + 4:.2f}" y2="{y1:.2f}" stroke="{C['dim']}" stroke-width="0.5" opacity="0.5"/>
  <line x1="{ext_from_x:.2f}" y1="{y2:.2f}" x2="{x + 4:.2f}" y2="{y2:.2f}" stroke="{C['dim']}" stroke-width="0.5" opacity="0.5"/>'''
    return f'''<g class="dim-v">
  <line x1="{x:.2f}" y1="{y1:.2f}" x2="{x:.2f}" y2="{y2:.2f}" stroke="{C['dim']}" stroke-width="0.8" marker-start="url(#arr)" marker-end="url(#arr)"/>
  <text x="{x - 4:.2f}" y="{mid:.2f}" text-anchor="end" font-size="10" fill="#333" font-family="Meiryo" transform="rotate(-90 {x - 4:.2f} {mid:.2f})">{text}</text>{ext}
</g>'''


# =========================================================
# 後方互換エイリアス（v1.0呼び出しを壊さない）
# =========================================================

def draw_hko(cx, y, spec='H-150x150', scale=1.0, existing=True, label=None):
    return draw_hko_section(cx, y, spec, scale, existing, label)

def draw_lgs_runner(cx, y, spec='LGS65', scale=1.0, direction='down'):
    return draw_lgs_runner_section(cx, y, spec, scale, direction)

def draw_lgs_stud(x, y1, y2, spec='LGS65', scale=1.0):
    return draw_lgs_stud_section(x, y1, y2, spec, scale)

def draw_pb(x, y1, y2, w=12.5, scale=1.0, hatch=True):
    return draw_pb_section(x, y1, y2, w, scale, hatch)

def draw_wood_stud(cx, y, spec='45x105', scale=1.0, orientation='vertical', label=None):
    return draw_wood_section(cx, y, spec, scale, label)

def draw_plywood(x, y1, y2, w=12.0, scale=1.0):
    return draw_plywood_section(x, y1, y2, w, scale)

def draw_keical(x, y1, y2, w=6.0, scale=1.0):
    return draw_keical_section(x, y1, y2, w, scale)

def draw_c_channel(cx, y, spec='C-75x45', scale=1.0, direction='right'):
    return draw_c_channel_section(cx, y, spec, scale, direction)


# =========================================================
# デモ（python3 sekozu_parts.py で縦断面・横断面の見本SVGを出力）
# =========================================================

def _demo_catalog():
    parts = [draw_defs()]
    parts.append('<rect x="0" y="0" width="1520" height="1074" fill="#fff"/>')

    # ========== 左ページ：縦断面 ==========
    parts.append('<text x="20" y="30" font-size="20" font-family="Meiryo" fill="#1e2d40" font-weight="bold">施工図部品ライブラリ v2.0</text>')
    parts.append('<text x="20" y="52" font-size="11" font-family="Meiryo" fill="#555">株式会社アート・レイズ / sekozu_parts.py — 縦断面（左）・横断面（右）対応</text>')

    parts.append('<rect x="10" y="70" width="740" height="990" fill="none" stroke="#ccc" stroke-dasharray="4,4"/>')
    parts.append('<text x="30" y="95" font-size="16" font-family="Meiryo" fill="#c8a96e" font-weight="bold">■ 縦断面（壁を横から切った図）</text>')

    # H鋼（縦断面） — I形
    parts.append('<text x="30" y="130" font-size="11" font-family="Meiryo" fill="#333">H鋼 I形</text>')
    parts.append(draw_hko_section(cx=100, y=150, spec='H-100x100'))
    parts.append(draw_label_right(150, 200, 'H-100×100'))
    parts.append(draw_hko_section(cx=280, y=150, spec='H-150x150'))
    parts.append(draw_label_right(355, 225, 'H-150×150'))

    # LGS壁（縦断面フル構成） ― 最も重要な使用例
    parts.append('<text x="30" y="360" font-size="11" font-family="Meiryo" fill="#333">LGS65＋PB t12.5 壁（縦断面）</text>')
    # 上部H鋼
    parts.append(draw_hko_section(cx=180, y=380, spec='H-150x150'))
    # 上部ランナー口↓
    parts.append(draw_lgs_runner_section(cx=180, y=530, spec='LGS65', direction='down'))
    # スタッド縦2本線
    parts.append(draw_lgs_stud_section(x=147, y1=540, y2=780, spec='LGS65'))
    # PB左面
    parts.append(draw_pb_section(x=142, y1=540, y2=780, w=12.5, scale=1.2))
    # PB右面
    parts.append(draw_pb_section(x=213, y1=540, y2=780, w=12.5, scale=1.2))
    # 下部ランナー口↑
    parts.append(draw_lgs_runner_section(cx=180, y=780, spec='LGS65', direction='up'))
    # FL表示
    parts.append(f'<line x1="100" y1="782" x2="260" y2="782" stroke="#1a1a1a" stroke-width="1.2"/>')
    parts.append(f'<text x="105" y="798" font-size="10" font-family="Meiryo" fill="#333">FL</text>')
    # ラベル
    parts.append(draw_label_right(223, 560, 'LGS65ランナー（天）'))
    parts.append(draw_label_right(162, 640, 'LGS65スタッド'))
    parts.append(draw_label_right(228, 700, '化粧PB t12.5'))
    parts.append(draw_label_right(223, 770, 'LGS65ランナー（床）'))
    parts.append(draw_anchor(cx=180, y=378 + 5, callout='top', label='M12アンカー'))

    # 木造壁（縦断面）
    parts.append('<text x="430" y="360" font-size="11" font-family="Meiryo" fill="#333">木造間仕切壁（縦断面）</text>')
    parts.append(draw_wood_section(cx=500, y=380, spec='105x105', label='胴差'))   # 上端材
    parts.append(draw_wood_section(cx=500, y=488, spec='45x105'))                  # 間柱（縦に伸びる）
    # 木造では間柱を縦方向に伸ばすので、490〜700まで
    # 上記は短いので別に描き直し：
    parts[-1] = f'''
<g class="part-wood-s">
  <rect x="{500-23:.2f}" y="{488:.2f}" width="{45:.2f}" height="{210:.2f}"
        fill="{C['wood_fill']}" stroke="{C['wood_stroke']}" stroke-width="1.0"/>
  <rect x="{500-23:.2f}" y="{488:.2f}" width="{45:.2f}" height="{210:.2f}"
        fill="url(#hatchWood)" stroke="none"/>
</g>'''
    parts.append(draw_wood_section(cx=500, y=700, spec='105x105', label='土台'))   # 下端材
    parts.append(draw_pb_section(x=467, y1=488, y2=700, w=12.5, scale=1.2))       # 左面PB
    parts.append(draw_pb_section(x=533, y1=488, y2=700, w=12.5, scale=1.2))       # 右面PB
    parts.append(draw_label_right(545, 590, '45×105 間柱'))
    parts.append(draw_label_right(548, 650, 'PB t12.5'))

    # ボード類
    parts.append('<text x="30" y="850" font-size="11" font-family="Meiryo" fill="#333">ボード類（t×4拡大）</text>')
    parts.append(draw_pb_section(x=40, y1=870, y2=1000, w=12.5, scale=4))
    parts.append(draw_label_right(40 + 12.5*4, 935, 'PB t12.5'))
    parts.append(draw_plywood_section(x=180, y1=870, y2=1000, w=12, scale=4))
    parts.append(draw_label_right(180 + 12*4, 935, '合板 t12'))
    parts.append(draw_keical_section(x=320, y1=870, y2=1000, w=8, scale=4))
    parts.append(draw_label_right(320 + 8*4, 935, 'ケイカル板 t8'))

    # ビス
    parts.append('<text x="480" y="850" font-size="11" font-family="Meiryo" fill="#333">ビス・ボルト類</text>')
    parts.append(draw_screw_coarse(x=500, y=880, length=32, orientation='horizontal'))
    parts.append(draw_label_right(500 + 32 + 4, 880, 'コーススレッド L32'))
    parts.append(draw_screw_coarse(x=500, y=910, length=25, orientation='horizontal'))
    parts.append(draw_label_right(500 + 25 + 4, 910, 'ドリルビス L25'))
    parts.append(draw_bolt_hex(cx=520, cy=960, d=12))
    parts.append(draw_label_right(532, 960, '六角ボルト M12'))

    # ========== 右ページ：横断面 ==========
    parts.append('<rect x="770" y="70" width="740" height="990" fill="none" stroke="#ccc" stroke-dasharray="4,4"/>')
    parts.append('<text x="790" y="95" font-size="16" font-family="Meiryo" fill="#c8a96e" font-weight="bold">■ 横断面（壁を上から切った平面詳細）</text>')

    # LGS壁の平面詳細（最重要）
    parts.append('<text x="790" y="140" font-size="11" font-family="Meiryo" fill="#333">LGS65＋両面PB t12.5 壁 @455（平面詳細 scale=0.8）</text>')
    scale_p = 0.8
    wall_cy = 200
    # スタッド@455を5本並べる
    parts.append(draw_lgs_array_plan(x0=830, cy=wall_cy, spec='LGS65', count=5, pitch=455, scale=scale_p, direction='right'))
    # 壁長手方向の範囲（5本@455 = 4スパン + フランジ余裕）
    span = 455 * scale_p
    pb_left = 830 - (LGS_SPECS['LGS65']['stud_f']/2 * scale_p)
    pb_right = 830 + 4 * span + (LGS_SPECS['LGS65']['stud_f']/2 * scale_p)
    # 壁厚方向のスタッド外面
    b_half = LGS_SPECS['LGS65']['B']/2 * scale_p
    # PB両面
    parts.append(draw_pb_plan(x1=pb_left, x2=pb_right, y=wall_cy - b_half - 12.5*scale_p*3, w=12.5, scale=scale_p*3, side='top'))
    parts.append(draw_pb_plan(x1=pb_left, x2=pb_right, y=wall_cy + b_half + 12.5*scale_p*3, w=12.5, scale=scale_p*3, side='bottom'))
    # 寸法
    parts.append(dim_horizontal(x1=830, x2=830+span, y=wall_cy + b_half + 12.5*scale_p*3 + 30, text='@455'))
    parts.append(draw_label_right(830 + 4*span + 30, wall_cy, 'LGS65スタッド @455'))
    parts.append(draw_label_right(830 + 4*span + 30, wall_cy - b_half - 12.5*scale_p*3 + 10, '化粧PB t12.5'))

    # H鋼の平面
    parts.append('<text x="790" y="330" font-size="11" font-family="Meiryo" fill="#333">H鋼（平面）— 梁を上から見下ろした姿</text>')
    parts.append(draw_hko_plan(cx=900,  cy=370, spec='H-150x150', scale=0.8, label='H-150×150'))
    parts.append(draw_hko_plan(cx=1200, cy=370, spec='H-200x100', scale=0.8, label='H-200×100'))

    # 木造間柱@455の平面
    parts.append('<text x="790" y="450" font-size="11" font-family="Meiryo" fill="#333">木造間柱@455（平面詳細 scale=0.8）</text>')
    wood_cy = 510
    parts.append(draw_wood_array_plan(x0=830, cy=wood_cy, spec='45x105', count=5, pitch=455, scale=0.8, orientation='vertical'))
    # 木造もPB両面
    parts.append(draw_pb_plan(x1=800, x2=1250, y=wood_cy - (105/2)*0.8 - 12.5*0.8*3, w=12.5, scale=0.8*3, side='top'))
    parts.append(draw_pb_plan(x1=800, x2=1250, y=wood_cy + (105/2)*0.8 + 12.5*0.8*3, w=12.5, scale=0.8*3, side='bottom'))
    parts.append(dim_horizontal(x1=830, x2=830 + 455*0.8, y=wood_cy + 80, text='@455'))
    parts.append(draw_label_right(830 + 4*455*0.8 + 20, wood_cy, '45×105 間柱'))

    # 単体C形断面
    parts.append('<text x="790" y="650" font-size="11" font-family="Meiryo" fill="#333">LGS C形断面（単体・口の向き）</text>')
    parts.append(draw_lgs_stud_plan(cx=830,  cy=690, spec='LGS65',  scale=2.5, direction='right'))
    parts.append(draw_label_top(cx=830, y=690 - LGS_SPECS['LGS65']['stud_f']*2.5/2, text='LGS65 口→'))
    parts.append(draw_lgs_stud_plan(cx=950,  cy=690, spec='LGS65',  scale=2.5, direction='left'))
    parts.append(draw_label_top(cx=950, y=690 - LGS_SPECS['LGS65']['stud_f']*2.5/2, text='LGS65 口←'))
    parts.append(draw_lgs_stud_plan(cx=1090, cy=690, spec='LGS100', scale=2.5, direction='right'))
    parts.append(draw_label_top(cx=1090, y=690 - LGS_SPECS['LGS100']['stud_f']*2.5/2, text='LGS100 口→'))

    # 木材単体断面
    parts.append('<text x="790" y="820" font-size="11" font-family="Meiryo" fill="#333">木材 単体断面（平面）</text>')
    parts.append(draw_wood_plan(cx=830,  cy=880, spec='45x45',   scale=2.5, label='45×45'))
    parts.append(draw_wood_plan(cx=970,  cy=880, spec='45x105',  scale=2.5, label='45×105'))
    parts.append(draw_wood_plan(cx=1170, cy=880, spec='105x105', scale=2.5, label='105×105 柱'))

    # 凡例
    parts.append('<text x="790" y="1000" font-size="11" font-family="Meiryo" fill="#333">■ 凡例</text>')
    parts.append(f'<rect x="800" y="1020" width="20" height="9" fill="{C["hko_fill"]}" fill-opacity="{C["hko_opa"]}"/><text x="824" y="1029" font-size="10" fill="#555">H鋼（既存）</text>')
    parts.append(f'<rect x="920" y="1020" width="20" height="8" fill="{C["lgs_fill"]}" fill-opacity="{C["lgs_opa"]}"/><text x="944" y="1028" font-size="10" fill="#555">LGS（新設）</text>')
    parts.append(f'<rect x="1040" y="1020" width="20" height="9" fill="{C["pb_fill"]}" stroke="{C["pb_stroke"]}" stroke-width="1.0"/><text x="1064" y="1029" font-size="10" fill="#555">PB＋クロス</text>')
    parts.append(f'<rect x="1160" y="1020" width="20" height="9" fill="{C["wood_fill"]}" stroke="{C["wood_stroke"]}" stroke-width="1.0"/><text x="1184" y="1029" font-size="10" fill="#555">木材</text>')

    body = '\n'.join(parts)
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1520 1074" width="1520" height="1074"
     style="background:#fff; font-family:Meiryo,'Yu Gothic',sans-serif;">
{body}
</svg>'''


if __name__ == '__main__':
    import os
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sekozu_parts_catalog.svg')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(_demo_catalog())
    print(f'カタログSVGを出力しました: {out}')
