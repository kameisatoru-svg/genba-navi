"""
みつも朗出力PDF → CSV変換スクリプト（v0.4 / 小規模見積対応）

v0.3からの改善：
- Page 1 も明細処理対象に追加（大項目目次が表紙にしかない小規模見積に対応）
- 末尾見出しが A.【看板貼替工事】でも、ページ内容に大項目記号で始まらない普通の名称行が
  並んでいる場合は CHU_DETAIL として扱う（中項目スキップ型）
- 中項目スキップ型のときは、中項目名 = 大項目名（A.看板貼替工事 → 中項目=「A.看板貼替工事」）
  として小項目の親情報を維持
"""

import re
import csv
import sys
import pdfplumber
from pathlib import Path
from io import StringIO
from collections import defaultdict, Counter


ZEN2HAN = str.maketrans("０１２３４５６７８９", "0123456789")
ZEN_ALPHA_TO_HAN = str.maketrans("ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ", "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
NORM_DOT = str.maketrans({"．": "."})


def normalize(s):
    if s is None:
        return ""
    s = s.translate(ZEN2HAN).translate(ZEN_ALPHA_TO_HAN).translate(NORM_DOT)
    return re.sub(r"\s+", " ", s).strip()


def parse_yen(s):
    if not s:
        return None
    s = str(s).replace(",", "").replace("￥", "").replace("¥", "").replace("\\", "").strip()
    s = s.replace(".-", "")
    if not s or s == "-":
        return None
    try:
        return int(s)
    except ValueError:
        return None


def parse_number(s):
    if not s:
        return None
    s = str(s).replace(",", "").strip()
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        return None


COL_BOUNDS = {
    "name":  (40, 250),
    "unit":  (250, 290),
    "qty":   (290, 350),
    "price": (350, 420),
    "amount":(420, 490),
    "biko":  (490, 700),
}


def column_of(x0):
    for col, (lo, hi) in COL_BOUNDS.items():
        if lo <= x0 < hi:
            return col
    return "other"


def group_into_rows(words, y_tolerance=7.0):
    if not words:
        return []
    sorted_words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    rows = []
    current_row = []
    current_top_min = sorted_words[0]["top"]

    for w in sorted_words:
        if w["top"] - current_top_min <= y_tolerance:
            current_row.append(w)
        else:
            if current_row:
                rows.append(sorted(current_row, key=lambda w: w["x0"]))
            current_row = [w]
            current_top_min = w["top"]

    if current_row:
        rows.append(sorted(current_row, key=lambda w: w["x0"]))
    return rows


def row_to_columns(row_words):
    cols = defaultdict(list)
    for w in row_words:
        col = column_of(w["x0"])
        cols[col].append(w["text"])
    return {col: " ".join(texts).strip() for col, texts in cols.items()}


def extract_header(page):
    text = page.extract_text() or ""
    header = {
        "書類種別": "見積書",
        "発行日": "",
        "見積番号": "",
        "発行元会社名": "株式会社アート・レイズ",
        "取引先会社名": "",
        "工事件名": "",
        "工事場所": "",
        "小計": None,
        "消費税": None,
        "合計金額": None,
    }

    # 発行日：令和 / 平成 両対応
    m = re.search(r"令和\s*([0-9０-９]+)\s*年\s*([0-9０-９]+)\s*月\s*([0-9０-９]+)\s*日", text)
    if m:
        y = int(m.group(1).translate(ZEN2HAN))
        mo = int(m.group(2).translate(ZEN2HAN))
        d = int(m.group(3).translate(ZEN2HAN))
        seireki = 2018 + y  # 令和元年=2019、令和2年=2020、ただし令和元年は5月から（暦上1年=2019）
        header["発行日"] = f"{seireki:04d}-{mo:02d}-{d:02d}"
    else:
        m = re.search(r"平成\s*([0-9０-９]+)\s*年\s*([0-9０-９]+)\s*月\s*([0-9０-９]+)\s*日", text)
        if m:
            y = int(m.group(1).translate(ZEN2HAN))
            mo = int(m.group(2).translate(ZEN2HAN))
            d = int(m.group(3).translate(ZEN2HAN))
            seireki = 1988 + y  # 平成元年=1989
            header["発行日"] = f"{seireki:04d}-{mo:02d}-{d:02d}"

    # 取引先：「○○○ 御中」
    m = re.search(r"^(.+?)\s*御中", text, re.MULTILINE)
    if m:
        header["取引先会社名"] = m.group(1).strip()

    # 工事件名：複数パターン対応
    # ① 現行：「工事件名：○○○」
    # ② H29版：「工事件名 ○○○」（コロンなし・タブまたは空白）
    m = re.search(r"工事件名\s*[:：]\s*(.+?)(?:\s+株式会社|$)", text, re.MULTILINE)
    if not m:
        m = re.search(r"工事件名\s+(.+?)$", text, re.MULTILINE)
    if m:
        kennmei = m.group(1).strip()
        # 「株式会社アート・レイズ」が末尾に紛れ込む場合を除外
        kennmei = re.sub(r"\s*株式会社.*$", "", kennmei).strip()
        header["工事件名"] = kennmei

    # 税込見積金額（現行） or 税込合計金額（H29版）
    m = re.search(r"税込(?:見積|合計)金額\s*[:：]?\s*[¥￥\\]?\s*([\d,]+)", text)
    if m:
        header["合計金額"] = parse_yen(m.group(1))

    # 消費税額
    m = re.search(r"消費税額\s*[:：]\s*[¥￥\\]?\s*([\d,]+)", text)
    if m:
        header["消費税"] = parse_yen(m.group(1))

    # 合計金額（税抜）
    # H29版「税抜合計：」を先に試す（「税込合計金額」と紛らわしいため）
    m = re.search(r"税抜合計\s*[:：]\s*[¥￥\\]?\s*([\d,]+)", text)
    if not m:
        # 現行「合計金額：」（ただし「税込合計金額」「税込見積金額」を除外）
        m = re.search(r"(?<!税込)合計金額\s*[:：]\s*[¥￥\\]?\s*([\d,]+)", text)
    if m:
        header["小計"] = parse_yen(m.group(1))

    return header


RE_DAI = re.compile(r"^([A-Z])\.(.+)$")
RE_CHU = re.compile(r"^([0-9]+)\.(.+)$")
RE_HEADING_DAI = re.compile(r"^([A-Z])\.【(.+)】$")
RE_HEADING_CHU = re.compile(r"^([0-9]+)\.【(.+)】$")

UNITS = {"式", "〃", "㎡", "ｍ", "m", "ヶ所", "台", "本", "個", "SET", "セット", "kg", "枚", "面", "日"}


def is_page_header(name_n, other):
    if name_n in ("No.", "", "内", "訳", "明", "細", "書"):
        return True
    if "Page." in (other or "") or "Page." in name_n:
        return True
    if name_n.startswith("内") and ("訳" in name_n or "明 細" in name_n):
        return True
    if "内" in name_n and "明" in name_n and "細" in name_n:
        return True
    if name_n.startswith("名") and "称" in name_n:
        return True
    if name_n in ("訳 明", "明 細", "内 訳", "内訳", "明細"):
        return True
    if other and ("訳" in other or "明" in other or "細" in other) and not name_n:
        return True
    # 表紙の項目名
    if name_n in ("工事件名", "工事場所", "工事概要", "工事期間", "支払条件", "有効期限"):
        return True
    # 「No. 内」「No. 御」などNo.で始まる断片
    if name_n.startswith("No.") or name_n.startswith("No "):
        return True
    return False


def classify_page(physical_rows):
    """
    ページタイプを判定：
    - DAI_TOC: 大項目目次（A.内装工事 / B.外装工事 ...）
    - CHU_TOC: 中項目目次（1.仮設 / 2.解体 ...）
    - CHU_DETAIL: 中項目内の小項目詳細
    - SKIP_DETAIL: 大項目末尾見出しだが、内容は小項目（小規模見積の中項目スキップ型）
    - COVER: 表紙（Page 1）
    - UNKNOWN

    判定戦略：
    1. 末尾見出し（○.【○○】）を取得
    2. ページ内に「A.〜」型の大項目記号行が複数ある → DAI_TOC
    3. 末尾見出しが大項目で、ページ内に「数字.〜」型の中項目記号行が複数 → CHU_TOC
    4. 末尾見出しがあるが、ページ内に大項目記号でも中項目記号でもない普通の名称行が並ぶ → 詳細ページ
       - 末尾見出しが A.【○○】 → SKIP_DETAIL（中項目スキップ型）
       - 末尾見出しが N.【○○】 → CHU_DETAIL（通常型）
    """
    # 末尾見出し取得
    end_dai_code = None
    end_dai_name = None
    end_chu_no = None
    end_chu_name = None

    for prow in reversed(physical_rows):
        row_text = " ".join(w["text"] for w in prow)
        row_norm = normalize(row_text)
        m = RE_HEADING_DAI.match(row_norm)
        if m:
            end_dai_code = m.group(1)
            end_dai_name = m.group(2)
            break
        m = RE_HEADING_CHU.match(row_norm)
        if m:
            end_chu_no = m.group(1)
            end_chu_name = m.group(2)
            break

    # ページ内の名称列を分類
    dai_names = []  # A.〜 / B.〜
    chu_names = []  # 1.〜 / 2.〜
    plain_names = []  # それ以外の通常の項目名
    for prow in physical_rows:
        cols = row_to_columns(prow)
        name = cols.get("name", "").strip()
        unit = cols.get("unit", "").strip()
        amount = cols.get("amount", "").strip()
        name_n = normalize(name)
        if not name:
            continue
        if is_page_header(name_n, cols.get("other", "")):
            continue
        if RE_HEADING_DAI.match(name_n) or RE_HEADING_CHU.match(name_n):
            continue
        # 数値行（単位や金額がある行）として扱われる行のうち、名称が大項目/中項目記号
        m_dai = RE_DAI.match(name_n)
        m_chu = RE_CHU.match(name_n)
        if m_dai and (unit or amount):
            dai_names.append(name_n)
        elif m_chu and (unit or amount):
            chu_names.append(name_n)
        elif unit or amount:
            plain_names.append(name_n)

    # 判定
    info = {
        "end_dai_code": end_dai_code,
        "end_dai_name": end_dai_name,
        "end_chu_no": end_chu_no,
        "end_chu_name": end_chu_name,
        "dai_count": len(dai_names),
        "chu_count": len(chu_names),
        "plain_count": len(plain_names),
    }

    # 大項目記号行のみ → DAI_TOC（中規模見積の大項目目次ページ or 表紙）
    if len(dai_names) >= 1 and len(plain_names) == 0:
        return "DAI_TOC", info
    # 末尾見出しが大項目で、中項目記号が複数（plainより多い）→ CHU_TOC
    # plain=1 程度のノイズ（中項目見出し本文「N.〜」）は許容
    if end_dai_code and len(chu_names) >= 2 and len(chu_names) > len(plain_names):
        return "CHU_TOC", info
    # 末尾見出しが中項目で plain が並ぶ → CHU_DETAIL
    if end_chu_no and len(plain_names) > 0:
        return "CHU_DETAIL", info
    # 末尾見出しが大項目で chu_names のみ → CHU_TOC（plain=0でも到達するパターン）
    if end_dai_code and len(chu_names) > 0 and len(plain_names) == 0:
        return "CHU_TOC", info
    # 末尾見出しが大項目で plain が主体 → SKIP_DETAIL（中項目スキップ型・小規模見積）
    if end_dai_code and len(plain_names) > 0:
        return "SKIP_DETAIL", info
    # 表紙（dai_names と plain が混在し、末尾見出しなし）
    if len(dai_names) > 0:
        return "DAI_TOC", info
    return "UNKNOWN", info


def parse_pages(pdf, total_pages):
    """全ページを処理（Page 1も含む）"""
    rows = []
    current_dai_code = None
    current_dai_name = None
    current_chu_no = None
    current_chu_name = None

    for page_idx in range(0, total_pages):
        page = pdf.pages[page_idx]
        words = page.extract_words(use_text_flow=False)
        if not words:
            continue

        physical_rows = group_into_rows(words, y_tolerance=8.5)

        page_type, info = classify_page(physical_rows)

        # ページタイプに応じて current コンテキストを更新
        if page_type == "DAI_TOC":
            # Page 1 表紙 or 中規模見積の大項目目次ページ
            # current は更新しない（複数の大項目を扱うため、行ごとに更新）
            pass
        elif page_type == "CHU_TOC":
            # 中項目目次ページ → 大項目を末尾見出しから取得
            current_dai_code = info["end_dai_code"]
            current_dai_name = info["end_dai_name"]
            current_chu_no = None
            current_chu_name = None
        elif page_type == "CHU_DETAIL":
            current_chu_no = info["end_chu_no"]
            current_chu_name = info["end_chu_name"]
            # 大項目は前ページの CHU_TOC で設定済み
        elif page_type == "SKIP_DETAIL":
            # 中項目スキップ型：大項目を中項目名として扱う
            current_dai_code = info["end_dai_code"]
            current_dai_name = info["end_dai_name"]
            # 中項目名 = 大項目名（A.看板貼替工事 → 中項目「A.看板貼替工事」）
            current_chu_no = info["end_dai_code"]
            current_chu_name = info["end_dai_name"]

        page_rows_buffer = []

        for prow in physical_rows:
            cols = row_to_columns(prow)
            name = cols.get("name", "").strip()
            unit = cols.get("unit", "").strip()
            qty_s = cols.get("qty", "").strip()
            price_s = cols.get("price", "").strip()
            amount_s = cols.get("amount", "").strip()
            biko = cols.get("biko", "").strip()
            other = cols.get("other", "").strip()

            name_n = normalize(name)

            # スキップ判定
            if not name and not unit and not amount_s and not biko:
                continue
            if is_page_header(name_n, other):
                continue
            if RE_HEADING_DAI.match(name_n) or RE_HEADING_CHU.match(name_n):
                continue
            if "【合" in name or name_n.startswith("【合"):
                continue
            if not name and not unit and amount_s and not qty_s and not price_s:
                continue
            # ヘッダ表（"単位" "数 量" 等）スキップ
            if name_n in ("単位", "数 量", "単 価", "金 額", "備 考"):
                continue

            # 備考独立行判定
            is_biko_only = (
                name and not unit and not qty_s and not price_s and not amount_s
                and not RE_DAI.match(name_n)
                and not RE_CHU.match(name_n)
            )
            is_subsection_heading = bool(
                is_biko_only and (
                    name_n == "次頁へ続く"
                    or re.match(r"^.+(工事|設備工事)$", name_n)
                )
            )

            if is_biko_only and not is_subsection_heading and page_type in ("CHU_DETAIL", "SKIP_DETAIL", "DAI_TOC"):
                if page_rows_buffer and page_rows_buffer[-1]["row_type"] in ("小項目", "大項目小計", "中項目小計"):
                    if page_rows_buffer[-1]["備考"]:
                        page_rows_buffer[-1]["備考"] += " / " + name
                    else:
                        page_rows_buffer[-1]["備考"] = name
                continue

            if is_subsection_heading:
                continue

            # 大項目目次行（A.〜）
            m_dai = RE_DAI.match(name_n)
            if m_dai and (unit or amount_s):
                qty = parse_number(qty_s)
                amount = parse_yen(amount_s)
                # 表紙ページの大項目目次の場合、current_dai を更新（行ごとに）
                if page_type == "DAI_TOC":
                    current_dai_code = m_dai.group(1)
                    current_dai_name = m_dai.group(2)
                page_rows_buffer.append({
                    "row_type": "大項目小計",
                    "大項目コード": m_dai.group(1),
                    "大項目名": m_dai.group(2),
                    "中項目名": "",
                    "小項目名": "",
                    "仕様・摘要": "",
                    "数量": qty,
                    "単位": unit,
                    "単価": None,
                    "金額": amount,
                    "備考": biko,
                })
                continue

            # 【端数調整】等のDAI_TOCページの調整行（金額列が埋まっている特殊行）
            if page_type == "DAI_TOC" and name and amount_s and not RE_DAI.match(name_n) and not RE_CHU.match(name_n):
                # 「【端数調整】」「【小計】」のような括弧付き名称、または数量なし金額のみの行
                if "【" in name or "端数" in name_n or "調整" in name_n:
                    qty = parse_number(qty_s)
                    amount = parse_yen(amount_s)
                    page_rows_buffer.append({
                        "row_type": "調整",
                        "大項目コード": "",
                        "大項目名": "",
                        "中項目名": "",
                        "小項目名": name,
                        "仕様・摘要": "",
                        "数量": qty,
                        "単位": unit,
                        "単価": None,
                        "金額": amount,
                        "備考": biko,
                    })
                    continue

            # 中項目目次行（N.〜）
            m_chu = RE_CHU.match(name_n)
            if m_chu and (unit or amount_s) and page_type == "CHU_TOC":
                qty = parse_number(qty_s)
                amount = parse_yen(amount_s)
                page_rows_buffer.append({
                    "row_type": "中項目小計",
                    "大項目コード": current_dai_code or "",
                    "大項目名": current_dai_name or "",
                    "中項目名": f"{m_chu.group(1)}.{m_chu.group(2)}",
                    "小項目名": "",
                    "仕様・摘要": "",
                    "数量": qty,
                    "単位": unit,
                    "単価": None,
                    "金額": amount,
                    "備考": biko,
                })
                continue

            # 中項目見出し（CHU_DETAILの先頭行）
            if m_chu and page_type == "CHU_DETAIL":
                continue

            # 小項目データ行
            if page_type in ("CHU_DETAIL", "SKIP_DETAIL") and name and (unit or amount_s):
                qty = parse_number(qty_s)
                unit_price = parse_yen(price_s)
                amount = parse_yen(amount_s)
                # 中項目名の組み立て
                if page_type == "SKIP_DETAIL":
                    chu_label = f"{current_dai_code}.{current_dai_name}"
                else:
                    chu_label = f"{current_chu_no}.{current_chu_name}" if current_chu_no else ""
                page_rows_buffer.append({
                    "row_type": "小項目",
                    "大項目コード": current_dai_code or "",
                    "大項目名": current_dai_name or "",
                    "中項目名": chu_label,
                    "小項目名": name,
                    "仕様・摘要": biko,
                    "数量": qty,
                    "単位": unit,
                    "単価": unit_price,
                    "金額": amount,
                    "備考": biko,
                })

        rows.extend(page_rows_buffer)

    return rows


def write_csv(header, rows, out_path):
    buf = StringIO()
    w = csv.writer(buf)

    w.writerow(["01_見積ヘッダ"])
    w.writerow(["書類種別", "発行日", "見積番号", "発行元会社名", "取引先会社名",
                "工事件名", "小計", "消費税", "合計金額"])
    w.writerow([
        header["書類種別"], header["発行日"], header["見積番号"],
        header["発行元会社名"], header["取引先会社名"], header["工事件名"],
        header["小計"] or "", header["消費税"] or "", header["合計金額"] or "",
    ])
    w.writerow([])

    w.writerow(["02_内訳明細"])
    w.writerow(["見積番号", "大項目コード", "大項目名", "中項目名", "小項目名",
                "仕様・摘要", "数量", "単位", "単価", "金額", "備考", "row_type"])
    for r in rows:
        w.writerow([
            header["見積番号"],
            r["大項目コード"], r["大項目名"], r["中項目名"], r["小項目名"],
            r["仕様・摘要"],
            r["数量"] if r["数量"] is not None else "",
            r["単位"],
            r["単価"] if r["単価"] is not None else "",
            r["金額"] if r["金額"] is not None else "",
            r["備考"],
            r["row_type"],
        ])

    Path(out_path).write_text(buf.getvalue(), encoding="utf-8-sig")


def main(pdf_path, out_csv_path):
    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        header = extract_header(pdf.pages[0])
        rows = parse_pages(pdf, total)

    write_csv(header, rows, out_csv_path)
    return header, rows


if __name__ == "__main__":
    pdf = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads/見積書_ハコニワ_店舗移転工事.pdf"
    out = sys.argv[2] if len(sys.argv) > 2 else "/home/claude/extracted_v4.csv"
    header, rows = main(pdf, out)
    print(f"=== ヘッダ ===")
    for k, v in header.items():
        print(f"  {k}: {v}")
    print(f"\n=== 明細行数: {len(rows)} ===")
    counter = Counter(r["row_type"] for r in rows)
    print(f"\n=== row_type別件数 ===")
    for k, v in counter.most_common():
        print(f"  {k}: {v}")
    print(f"\n=== 備考付き行サンプル ===")
    biko_rows = [r for r in rows if r["備考"]]
    for r in biko_rows[:15]:
        print(f"  [{r['row_type']}] {r['小項目名'] or r['大項目名']:<28} 備考='{r['備考']}'")
    print(f"\n=== 出力先 ===\n  {out}")
