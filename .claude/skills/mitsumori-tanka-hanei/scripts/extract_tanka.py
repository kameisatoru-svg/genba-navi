# -*- coding: utf-8 -*-
"""
見積HTML（かめさんが修正してPDF化した分）から明細単価を抽出し、
工種別単価マスター（単価マスター_アートレイズ.html）と突合して反映候補を出す。

出力: teian_tanka.json（反映候補）＋ 標準出力にMarkdown表
書き込みは一切しない（読み取り専用・apply_tanka.py が反映を担当）。

usage:
  python extract_tanka.py                # 未処理の見積HTMLだけ（差分モード）
  python extract_tanka.py --all          # 全件洗い直し
  python extract_tanka.py --files a.html b.html
  python extract_tanka.py --since 2026-07-01
"""
import argparse
import datetime as dt
import difflib
import hashlib
import io
import json
import os
import re
import sys
import unicodedata

def _find_navi():
    """スクリプト位置から genba-navi（単価マスターのある階層）まで遡る。"""
    p = os.path.dirname(os.path.abspath(__file__))
    for _ in range(8):
        if os.path.exists(os.path.join(p, "単価マスター_アートレイズ.html")):
            return p
        p = os.path.dirname(p)
    raise SystemExit("genba-navi が見つかりません（単価マスター_アートレイズ.html 不在）")


NAVI = _find_navi()                                        # ...\genba-navi
AR2026 = os.path.join(os.path.dirname(os.path.dirname(NAVI)), "AR-2026")
MASTER = os.path.join(NAVI, "単価マスター_アートレイズ.html")
JISSEKI = os.path.join(NAVI, "jisseki_tanka.json")
TEIAN = os.path.join(NAVI, "teian_tanka.json")

# 単価として拾わない行（工事費でなく諸費用・値引き等）
SKIP_NAME = re.compile(
    r"(値引|調整|小計|合計|消費税|諸経費|端数|以下余白|備考|—|^-+$)")
# 「一式」系は単価比較に馴染まないので別バケットへ
ISSHIKI_UNIT = {"式", "一式", "ｾｯﾄ", "セット"}


def norm(s):
    """名称の正規化キー。全半角・空白・記号ゆれを吸収する。"""
    s = unicodedata.normalize("NFKC", str(s or "")).strip()
    s = re.sub(r"[\s　]+", "", s)
    s = s.replace("（", "(").replace("）", ")")
    s = re.sub(r"[・･,、。\.]", "", s)
    return s.lower()


def norm_unit(u):
    u = unicodedata.normalize("NFKC", str(u or "")).strip()
    return {"m2": "㎡", "M2": "㎡", "平米": "㎡", "m²": "㎡",
            "M": "m", "ｍ": "m", "本": "本", "箇所": "ヶ所", "カ所": "ヶ所"}.get(u, u)


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 16), b""):
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------- 見積HTML側

def parse_docstate(html):
    """mitsumori_seikyu_preview.html が埋め込む状態JSONから明細を取る（本命）。"""
    m = re.search(r'<script id="artrays-doc-state"[^>]*>(.*?)</script>',
                  html, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(1))
    except Exception:
        return None
    rows = []
    buckets = list(d.get("flatItems") or []) + list(d.get("groupSummaryItems") or [])
    for g in (d.get("groupItems") or []):
        buckets += list(g.get("middleItems") or []) + list(g.get("items") or [])
    for it in buckets:
        rows.append({
            "名称": it.get("name", ""),
            "数量": it.get("qty", ""),
            "単位": it.get("unit", ""),
            "単価": it.get("price", ""),
            "備考": it.get("note", ""),
        })
    return {"rows": rows, "meta": d.get("fields") or {}, "docType": d.get("docType", "")}


def parse_table(html):
    """状態JSONが無い旧HTML用フォールバック。明細表の行を素で拾う。"""
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S):
        tds = [re.sub(r"<[^>]+>", "", c).strip()
               for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if len(tds) < 5:
            continue
        name, qty, unit, price = tds[0], tds[1], tds[2], tds[3]
        if not name or "工事内容" in name:
            continue
        rows.append({"名称": name, "数量": qty, "単位": unit,
                     "単価": price, "備考": tds[4] if len(tds) > 4 else ""})
    meta = {}
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    if m:
        meta["kojimei"] = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return {"rows": rows, "meta": meta, "docType": ""}


def to_num(v):
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d.\-]", "", unicodedata.normalize("NFKC", str(v)))
    try:
        return float(s) if s not in ("", "-", ".") else None
    except ValueError:
        return None


def extract_file(path):
    html = io.open(path, encoding="utf-8", errors="replace").read()
    got = parse_docstate(html) or parse_table(html)
    anken = (got["meta"].get("ankenKey")
             or os.path.basename(os.path.dirname(os.path.dirname(path))))
    hakko = got["meta"].get("hakkoDate", "")
    out = []
    for r in got["rows"]:
        name = str(r["名称"] or "").strip()
        price = to_num(r["単価"])
        if not name or price is None or price <= 0:
            continue
        if SKIP_NAME.search(name):
            continue
        out.append({
            "名称": name,
            "単位": norm_unit(r["単位"]),
            "単価": int(round(price)),
            "数量": to_num(r["数量"]),
            "備考": str(r.get("備考") or "").strip(),
            "案件キー": anken,
            "発行日": hakko,
            "出典": os.path.relpath(path, AR2026).replace("\\", "/"),
        })
    return out


# ---------------------------------------------------------------- マスター側

PRICE_CELL = re.compile(r'<td class="price-range">(.*?)</td>')


def parse_master(path):
    """工種セクションごとの行を読む。行は (工種, 名称, 単位, 最小, 最大, 生文字列)。"""
    html = io.open(path, encoding="utf-8", errors="replace").read()
    sections = []
    for sm in re.finditer(
            r'<div class="section-wrap[^"]*" data-section="(?P<kw>[^"]*)">(?P<body>.*?)'
            r'(?=<div class="section-wrap|</body>)', html, re.S):
        kw = sm.group("kw")
        body = sm.group("body")
        tm = re.search(r'<span class="section-title-text">(.*?)</span>', body)
        title = re.sub(r"<[^>]+>", "", tm.group(1)).strip() if tm else kw
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
            tds = re.findall(r"<t([dh])[^>]*>(.*?)</t\1>", tr, re.S)
            if len(tds) < 3 or tds[0][0] == "h":
                continue
            cells = [re.sub(r"<[^>]+>", "", c).strip() for _, c in tds]
            lo, hi = parse_price_cell(cells[2])
            rows.append({"名称": cells[0], "単位": norm_unit(cells[1]),
                         "最小": lo, "最大": hi, "単価表記": cells[2],
                         "区分": cells[3] if len(cells) > 3 else "",
                         "備考": cells[4] if len(cells) > 4 else ""})
        sections.append({"工種": title, "キーワード": kw, "行": rows})
    return html, sections


def parse_price_cell(txt):
    """'800〜1,200円' / '15,000円' / '実費' → (最小, 最大) or (None, None)"""
    t = unicodedata.normalize("NFKC", txt or "")
    nums = [int(n.replace(",", "")) for n in re.findall(r"[\d,]+", t)]
    if not nums:
        return None, None
    return min(nums), max(nums)


def match_master(name, unit, sections, cutoff=0.82):
    """マスター内の同義行を探す。同一単位優先＋名称の類似度で判定。"""
    key = norm(name)
    best = None
    for sec in sections:
        for row in sec["行"]:
            mkey = norm(row["名称"])
            if not mkey:
                continue
            # 単位が違うものは別物（㎡単価と箇所単価を混ぜると単価表が壊れる）。
            # 「壁開口(箇所)」に「壁開口補強W-65(m)」がぶら下がった実害があった。
            if row["単位"] and unit and row["単位"] != unit:
                continue
            ratio = difflib.SequenceMatcher(None, key, mkey).ratio()
            if key == mkey:
                ratio = 1.0
            elif key in mkey or mkey in key:
                ratio = max(ratio, 0.9)
            if best is None or ratio > best[0]:
                best = (ratio, sec["工種"], row)
    if best and best[0] >= cutoff:
        return best
    return None


# 工種の優先ルール（上から順に評価。data-section のキーワードは互いに重複するため、
# 「撤去なのに02でなく04に落ちる」等の誤分類をここで先に潰す）
SECTION_RULES = [
    (r"(足場|仮設)", "01"),
    (r"(撤去|解体|斫り|はつり|剥取|剥がし|処分|廃材|産廃|発生材)", "02"),
    (r"(養生|運搬|搬入|搬出|階段設置)", "01"),
    (r"(モルタル|漆喰|珪藻土|ジョリパット|左官|セルフレベリング|土間仕上)", "03"),
    (r"(軽量鉄骨|軽天|lgs|石膏ボード|プラスターボード|pb|捨て貼り|下地組|造作|手すり|コンパネ|木下地)", "04"),
    (r"(建具|扉|ドア枠|襖|障子|サッシ|内窓|ガラス|網戸|アンダーカット)", "05"),
    (r"(クロス|壁紙|cf|クッションフロア|フロアタイル|塩ビタイル|長尺シート|タイルカーペット|巾木|フローリング|カーテン|ワックス|見切り)", "06"),
    (r"(外構|ブロック|フェンス|カーポート|人工芝|整地|土間コンクリート)", "07"),
    (r"(屋根|防水|庇|板金|ガルバリウム|スレート|瓦|ドレン|脱気筒|コーキング|シーリング)", "08"),
    (r"(塗装|塗替|ペイント|吹付|タッチアップ|日塗工)", "09"),
    (r"(コンセント|照明|ダウンライト|分電盤|配線|lan|アンテナ|インターホン|防犯カメラ)", "11"),
    (r"(エアコン|換気扇|ダクト|全熱交換|ロスナイ|空調)", "12"),
    (r"(給水|排水|水栓|給湯器|エコキュート|トイレ|キッチン|ユニットバス|洗面|配管)", "13"),
    (r"(誘導灯|火災警報|感知器|消防|レンジフード)", "14"),
    (r"(日当|人工|作業員|とび|鉄筋|型わく|溶接)", "10"),
]


def guess_section(name, sections):
    """未登録項目の工種を推定する。優先ルール → キーワード長重みの順。"""
    key = norm(name)
    for pat, no in SECTION_RULES:
        if re.search(pat, key):
            for sec in sections:
                if sec["工種"].startswith(no):
                    return sec["工種"]
    best, score = None, 0
    for sec in sections:
        # 長いキーワードほど具体的＝重みを大きく（「配管」より「換気扇」を優先）
        s = sum(len(w) for w in re.split(r"[\s　]+", sec["キーワード"])
                if len(w) >= 2 and norm(w) in key)
        if s > score:
            best, score = sec["工種"], s
    return best or "（要手動分類）"


# ---------------------------------------------------------------- メイン

def find_targets(args, jisseki):
    if args.files:
        return [os.path.abspath(f) for f in args.files]
    pats = ("見_",) if not args.include_seikyu else ("見_", "請_")
    hits = []
    for root, dirs, files in os.walk(AR2026):
        dirs[:] = [d for d in dirs if not d.startswith(("_アーカイブ", "_削除予定", "_破棄"))]
        for fn in files:
            if not fn.lower().endswith(".html"):
                continue
            if not fn.startswith(pats):
                continue
            hits.append(os.path.join(root, fn))
    done = jisseki.get("処理済み", {})
    out = []
    for p in hits:
        rel = os.path.relpath(p, AR2026).replace("\\", "/")
        if args.since:
            mt = dt.date.fromtimestamp(os.path.getmtime(p)).isoformat()
            if mt < args.since:
                continue
        if not args.all and rel in done and done[rel].get("sha1") == sha1(p):
            continue
        out.append(p)
    return sorted(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--since")
    ap.add_argument("--include-seikyu", action="store_true")
    ap.add_argument("--include-isshiki", action="store_true",
                    help="「式」計上の行もマスター反映候補に含める（既定は記録のみ）")
    ap.add_argument("--cutoff", type=float, default=0.82)
    args = ap.parse_args()

    jisseki = {}
    if os.path.exists(JISSEKI):
        jisseki = json.load(io.open(JISSEKI, encoding="utf-8"))

    _, sections = parse_master(MASTER)
    targets = find_targets(args, jisseki)

    items, files_meta = [], []
    for p in targets:
        rows = extract_file(p)
        files_meta.append({"出典": os.path.relpath(p, AR2026).replace("\\", "/"),
                           "sha1": sha1(p), "行数": len(rows)})
        items += rows

    # 同一名称＋単位でまとめ、最新の見積を代表にする（かめさん修正後＝最新が正）
    grouped = {}
    for it in items:
        k = (norm(it["名称"]), it["単位"])
        grouped.setdefault(k, []).append(it)

    teian = {"生成日時": dt.datetime.now().isoformat(timespec="seconds"),
             "対象ファイル": files_meta, "候補": []}

    for (nk, unit), lst in grouped.items():
        lst.sort(key=lambda x: (x["発行日"] or "", x["出典"]))
        latest = lst[-1]
        prices = [x["単価"] for x in lst]
        bucket = "一式" if unit in ISSHIKI_UNIT else "単価"
        hit = match_master(latest["名称"], unit, sections, args.cutoff)
        c = {
            "名称": latest["名称"], "単位": unit, "種別": bucket,
            "実績単価": latest["単価"], "実績最小": min(prices), "実績最大": max(prices),
            "出現数": len(lst),
            "案件キー": latest["案件キー"], "発行日": latest["発行日"],
            "出典": [x["出典"] for x in lst],
        }
        if hit:
            ratio, kousyu, row = hit
            c.update({"判定": None, "工種": kousyu, "マスター名称": row["名称"],
                      "マスター単価": row["単価表記"], "一致度": round(ratio, 2),
                      "マスター最小": row["最小"], "マスター最大": row["最大"]})
            lo, hi = row["最小"], row["最大"]
            if lo is None:
                c["判定"] = "要確認"       # 「実費」等
            elif lo <= latest["単価"] <= hi:
                c["判定"] = "レンジ内"
            elif latest["単価"] < lo / 3 or latest["単価"] > hi * 3:
                # 桁が違うほどの乖離は同義語の誤マッチを疑う。自動で広げると
                # レンジが「1,350〜20,000円」のような使えない幅に壊れる。
                c["判定"] = "要確認"
                c["理由"] = "マスターと3倍以上の乖離（別項目の可能性）"
            else:
                c["判定"] = "レンジ外"
                c["新レンジ案"] = fmt_range(min(lo, latest["単価"]),
                                            max(hi, latest["単価"]))
        else:
            c.update({"判定": "未登録", "工種": guess_section(latest["名称"], sections),
                      "新レンジ案": fmt_range(min(prices), max(prices))})
        # 「式」の行は案件固有の一括計上で単価表に馴染まない。既定では記録のみ。
        if bucket == "一式" and not args.include_isshiki:
            c["判定"] = "一式記録"
        teian["候補"].append(c)

    order = {"レンジ外": 0, "未登録": 1, "要確認": 2, "レンジ内": 3, "一式記録": 4}
    teian["候補"].sort(key=lambda c: (order.get(c["判定"], 9), -c["出現数"]))

    with io.open(TEIAN, "w", encoding="utf-8", newline="\n") as f:
        json.dump(teian, f, ensure_ascii=False, indent=1)

    report(teian)


def fmt_range(lo, hi):
    return "{:,}円".format(lo) if lo == hi else "{:,}〜{:,}円".format(lo, hi)


def report(teian):
    out = sys.stdout
    n = len(teian["対象ファイル"])
    c = teian["候補"]
    cnt = {k: sum(1 for x in c if x["判定"] == k)
           for k in ("レンジ外", "未登録", "要確認", "レンジ内", "一式記録")}
    out.write("# 単価反映 提案（対象見積 {} 件 / 明細 {} 種）\n\n".format(n, len(c)))
    out.write("- レンジ外(要更新) **{レンジ外}** / 未登録(新規追加) **{未登録}** / "
              "要確認 {要確認} / レンジ内(変更不要) {レンジ内} / "
              "一式記録(マスター対象外) {一式記録}\n\n".format(**cnt))
    for label in ("レンジ外", "未登録", "要確認"):
        rows = [x for x in c if x["判定"] == label]
        if not rows:
            continue
        out.write("## {}（{}件）\n\n".format(label, len(rows)))
        out.write("| # | 工種 | 作業内容 | 単位 | 実績単価 | マスター現行 | 新レンジ案 | 出典案件 |\n")
        out.write("|---|---|---|---|---|---|---|---|\n")
        for i, x in enumerate(rows, 1):
            out.write("| {} | {} | {} | {} | {:,}円 | {} | {} | {} |\n".format(
                i, x.get("工種", ""), x["名称"], x["単位"], x["実績単価"],
                x.get("マスター単価", "—"), x.get("新レンジ案", "—"), x["案件キー"]))
        out.write("\n")


if __name__ == "__main__":
    main()
