#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""artrays-genka — 原価管理Sheets の MCP サーバー（stdio / 依存パッケージなし）

月末経理の「TSVを出す → 手でSheetsに貼る →『貼付完了』と言う → 集計する」を
一本につなぐ。接続先は スプレッドシートに貼った Apps Script ウェブアプリ
（mcp/appsscript/genka_api.gs）。

  genka_import_tsv  → genka_aggregate → genka_sync_to_data_json
  （貼付を代行）      （4費目集計）      （data.json へ書き戻し）

起動:  python mcp/artrays_genka_server.py
疎通:  python mcp/artrays_genka_server.py --ping
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import artrays_data_server as ds  # noqa: E402  data.json の検証・安全な書き込みを再利用

SERVER_NAME = "artrays-genka"
SERVER_VERSION = "1.0.0"

CONFIG_PATH = Path(os.environ.get("ARTRAYS_GENKA_CONFIG")
                   or (Path(__file__).resolve().parent / ".genka_config.json"))
HTTP_TIMEOUT = int(os.environ.get("ARTRAYS_GENKA_TIMEOUT") or 60)
HTTP_RETRIES = 3

# 原価管理Sheets A〜M列
COLUMNS = ["レコードID", "案件番号", "現場名", "日付", "店舗名・業者名", "品目・内容",
           "金額", "勘定科目", "原価区分", "支払方法", "ソース", "備考", "登録日"]
INPUT_COLUMNS = COLUMNS[1:]           # 追記時に渡す12列（A列は採番されるので渡さない）
IDX = {name: i for i, name in enumerate(COLUMNS)}

GENKA_KEYS = ["労務費", "材料費", "外注費", "経費"]
CHOKUSETSU = "直接原価"
IPPAN = "一般経費"

ToolError = ds.ToolError


# --------------------------------------------------------------------------
# Apps Script ウェブアプリとの通信
# --------------------------------------------------------------------------

def load_config() -> dict:
    url = os.environ.get("ARTRAYS_GENKA_URL")
    token = os.environ.get("ARTRAYS_GENKA_TOKEN")
    if url and token:
        return {"url": url, "token": token}
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ToolError(f"{CONFIG_PATH} が JSON として読めません: {e}")
        if cfg.get("url") and cfg.get("token"):
            return {"url": str(cfg["url"]).strip(), "token": str(cfg["token"]).strip()}
    raise ToolError(
        "接続先が未設定です。次のどちらかを行ってください。\n"
        f"  1) {CONFIG_PATH} に {{\"url\": \"<ウェブアプリURL>\", \"token\": \"<トークン>\"}}\n"
        "  2) 環境変数 ARTRAYS_GENKA_URL / ARTRAYS_GENKA_TOKEN を設定\n"
        "セットアップ手順は mcp/README_genka.md を参照。")


def api(action: str, **payload):
    """Apps Script ウェブアプリを呼ぶ。302 リダイレクトは urllib が追う。"""
    cfg = load_config()
    body = json.dumps({"action": action, "token": cfg["token"], **payload},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        cfg["url"], data=body,
        headers={"Content-Type": "application/json; charset=utf-8"})

    last = None
    for attempt in range(HTTP_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as res:
                raw = res.read().decode("utf-8")
            break
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} {e.reason}"
            if e.code < 500:
                raise ToolError(
                    f"Apps Script への接続に失敗しました（{last}）。\n"
                    "URL が『ウェブアプリ』のデプロイURL（/exec で終わる）か確認してください。")
        except urllib.error.URLError as e:
            last = str(e.reason)
        except TimeoutError:
            last = "タイムアウト"
        if attempt < HTTP_RETRIES - 1:
            time.sleep(2 ** attempt)
    else:
        raise ToolError(f"Apps Script に接続できませんでした（{last}）。URL と通信環境を確認してください。")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        head = raw.strip()[:300]
        raise ToolError(
            "Apps Script の応答が JSON ではありません。デプロイ設定（アクセスできるユーザー＝"
            f"全員 / 実行するユーザー＝自分）を確認してください。\n応答の先頭: {head}")
    if not data.get("ok"):
        extra = {k: v for k, v in data.items() if k not in ("ok", "error")}
        detail = ("\n" + json.dumps(extra, ensure_ascii=False)) if extra else ""
        raise ToolError(f"Apps Script 側でエラー: {data.get('error')}{detail}")
    return data


# --------------------------------------------------------------------------
# 集計ロジック（genka-aggregate の仕様をそのまま実装）
# --------------------------------------------------------------------------

def to_amount(v) -> float:
    """『¥1,234』『1,234円』などを数値にする。読めなければ ValueError。"""
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace("¥", "").replace("￥", "")
    s = s.replace("円", "").replace(" ", "")
    if not s:
        raise ValueError("空欄")
    return float(s)


def classify(kamoku: str, kubun: str):
    """(費目, 警告) を返す。genka-aggregate の 4分類マッピングそのまま。"""
    kubun = (kubun or "").strip()
    kamoku = (kamoku or "").strip()
    if kubun == IPPAN:
        return "経費", None
    if kubun == CHOKUSETSU:
        if kamoku in ("材料費", "外注費", "労務費"):
            return kamoku, None
        return "経費", None
    return "経費", f"原価区分が『{kubun or '(空)'}』のため暫定的に経費へ加算"


def aggregate_rows(rows):
    """明細行（A〜M）を案件番号ごとに4費目集計する。"""
    agg, warnings = {}, []
    for r in rows:
        r = list(r) + [""] * (len(COLUMNS) - len(r))
        anken = str(r[IDX["案件番号"]]).strip()
        rc = str(r[IDX["レコードID"]]).strip()
        if not anken:
            warnings.append(f"{rc or '(RC不明)'}: 案件番号が空のため集計から除外")
            continue
        try:
            amount = to_amount(r[IDX["金額"]])
        except ValueError:
            warnings.append(f"{rc or '(RC不明)'}: 金額『{r[IDX['金額']]}』が数値として読めないため除外")
            continue
        bucket, warn = classify(r[IDX["勘定科目"]], r[IDX["原価区分"]])
        if warn:
            warnings.append(f"{rc or '(RC不明)'}: {warn}")
        cur = agg.setdefault(anken, {k: 0.0 for k in GENKA_KEYS} | {"件数": 0})
        cur[bucket] += amount
        cur["件数"] += 1

    out = {}
    for anken, v in agg.items():
        vals = {k: int(round(v[k])) for k in GENKA_KEYS}
        out[anken] = {**vals, "合計": sum(vals.values()), "件数": v["件数"]}
    return out, warnings


def resolve_anken_key(data: dict, anken_no: str):
    """原価管理Sheets の案件番号（AR-26-XXX）→ data.json の案件キー。"""
    norm = str(anken_no).strip().upper().replace(" ", "")
    for a in data["案件"]:
        if str(a.get("旧案件番号", "")).strip().upper().replace(" ", "") == norm:
            return a["案件キー"]
    for a in data["案件"]:
        if str(a.get("案件キー", "")).strip() == str(anken_no).strip():
            return a["案件キー"]
    return None


# --------------------------------------------------------------------------
# TSV の取り込み
# --------------------------------------------------------------------------

def parse_tsv(path: Path):
    """A〜M（13列）でも B〜M（12列）でも受け付け、12列（B〜M）に正規化する。"""
    if not path.exists():
        raise ToolError(f"TSV が見つかりません: {path}")
    text = path.read_text(encoding="utf-8-sig")
    rows, skipped_header = [], False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        cells = line.split("\t")
        if not skipped_header and (cells[0].strip() in ("レコードID", "A", "RC")
                                   or "案件番号" in line):
            skipped_header = True
            continue
        if len(cells) == len(COLUMNS):          # A列付き → A列を捨てる
            cells = cells[1:]
        elif len(cells) == len(INPUT_COLUMNS):
            pass
        else:
            raise ToolError(
                f"{path.name} の {lineno} 行目の列数が {len(cells)} です。"
                f"13列（A〜M）か 12列（B〜M）にしてください。")
        rows.append([c.strip() for c in cells])
    if not rows:
        raise ToolError(f"{path.name} に取り込める行がありません。")
    return rows


def validate_input_rows(rows):
    """追記前に弾けるものを弾く。(errors, normalized) を返す。"""
    errors, out = [], []
    for i, r in enumerate(rows, start=1):
        row = list(r)
        try:
            amount = to_amount(row[INPUT_COLUMNS.index("金額")])
        except (ValueError, IndexError):
            errors.append(f"{i}行目: 金額『{row[INPUT_COLUMNS.index('金額')]}』が数値として読めません")
            continue
        row[INPUT_COLUMNS.index("金額")] = int(round(amount))
        kubun = row[INPUT_COLUMNS.index("原価区分")].strip()
        if kubun not in (CHOKUSETSU, IPPAN):
            errors.append(f"{i}行目: 原価区分は『{CHOKUSETSU}』か『{IPPAN}』"
                          f"（指定: {kubun or '(空)'}）")
        date = row[INPUT_COLUMNS.index("日付")].strip()
        if not date:
            errors.append(f"{i}行目: 日付が空です")
        if not row[INPUT_COLUMNS.index("登録日")].strip():
            row[INPUT_COLUMNS.index("登録日")] = datetime.now().strftime("%Y-%m-%d")
        out.append([str(c) if not isinstance(c, int) else c for c in row])
    return errors, out


# --------------------------------------------------------------------------
# ツール
# --------------------------------------------------------------------------

def t_genka_ping(_args):
    res = api("ping")
    out = {"接続": "OK", "スプレッドシート": res.get("spreadsheet"),
           "シート": res.get("sheet"), "明細行数": res.get("rows"),
           "最終RC": res.get("lastRC"), "次のRC": res.get("nextRC")}
    if res.get("tabs"):
        out["タブ一覧"] = res["tabs"]
    return out


def t_genka_next_rc(_args):
    return {"次のRC": api("next_rc")["nextRC"]}


def t_genka_read(args):
    params = {}
    for names, p in ((("anken_no", "案件番号"), "anken"),
                     (("month", "年月"), "month"),
                     (("kamoku", "勘定科目"), "kamoku")):
        v = ds.pick(args, *names)
        if v:
            params[p] = v
    res = api("read", **params)
    rows = res["rows"]
    limit = int(args.get("limit") or 50)
    return {"該当": res["count"], "全体": res["total"],
            "列": COLUMNS,
            "明細": [dict(zip(COLUMNS, r)) for r in rows[:limit]],
            "打ち切り": max(0, res["count"] - limit)}


def t_genka_append_rows(args):
    rows = args.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ToolError("rows に追記する行の配列を指定してください")
    norm = []
    for i, r in enumerate(rows, start=1):
        if isinstance(r, dict):
            missing = [c for c in INPUT_COLUMNS if c not in r and c != "登録日"]
            if missing:
                raise ToolError(f"{i}行目に不足している列: {', '.join(missing)}")
            norm.append([r.get(c, "") for c in INPUT_COLUMNS])
        elif isinstance(r, list) and len(r) == len(INPUT_COLUMNS):
            norm.append(list(r))
        else:
            raise ToolError(
                f"{i}行目の形式が不正です。{len(INPUT_COLUMNS)}列の配列か、"
                f"列名をキーにしたオブジェクトを渡してください。")

    errors, checked = validate_input_rows(norm)
    if errors:
        raise ToolError("追記前の検証で問題が見つかりました:\n- " + "\n- ".join(errors))

    dry = bool(args.get("dry_run", True))
    res = api("append", rows=checked, dryRun=dry)
    return {
        "実行": "プレビュー（未書き込み）" if dry else "書き込み完了",
        "採番": res["assigned"],
        "重複でスキップ": res["skipped"],
        "追記行数": res["appended"],
        "書き込み後の行数": res["rowsAfter"],
        "次の操作": "dry_run=false で実行すると書き込みます" if dry else "genka_aggregate で集計してください",
    }


def t_genka_import_tsv(args):
    path = args.get("path")
    if not path:
        raise ToolError("path に TSV のパスを指定してください")
    rows = parse_tsv(Path(path))
    return t_genka_append_rows({"rows": rows, "dry_run": args.get("dry_run", True)})


def t_genka_aggregate(args):
    month = ds.pick(args, "month", "年月")
    res = api("read", **({"month": month} if month else {}))
    agg, warnings = aggregate_rows(res["rows"])

    data = ds.load_data()
    matched, unmatched = {}, {}
    for anken_no, v in agg.items():
        key = resolve_anken_key(data, anken_no)
        if key:
            matched[key] = {**v, "案件番号": anken_no}
        else:
            unmatched[anken_no] = v
    for anken_no, v in unmatched.items():
        warnings.append(f"{anken_no}: data.json に対応する案件がありません"
                        f"（{v['件数']}行 / 合計 {v['合計']:,}円）")

    top = sorted(matched.items(), key=lambda kv: -kv[1]["合計"])[:10]
    return {
        "対象行数": res["count"],
        "集計案件数": len(matched),
        "未突合": len(unmatched),
        "警告": warnings,
        "上位10件": [{"案件キー": k, **v} for k, v in top],
        "全件": matched,
    }


def t_genka_sync_to_data_json(args):
    agg = t_genka_aggregate({})
    matched = agg["全件"]
    if not matched:
        raise ToolError("集計結果が空です。先に genka_ping で接続を確認してください。")

    data = ds.load_data()
    today = datetime.now().strftime("%Y-%m-%d")
    changes, zeroed = [], []
    for a in data["案件"]:
        key = a["案件キー"]
        v = matched.get(key)
        new = ({k: v[k] for k in GENKA_KEYS} | {"合計": v["合計"], "件数": v["件数"],
                                                "最終集計日": today}
               if v else
               {k: 0 for k in GENKA_KEYS} | {"合計": 0, "件数": 0, "最終集計日": today})
        old = a.get("原価") or {}
        old_total = old.get("合計") or 0
        if any(old.get(k) != new[k] for k in GENKA_KEYS + ["合計", "件数"]):
            changes.append({"案件キー": key,
                            "変更前": {k: old.get(k, 0) for k in GENKA_KEYS + ["合計"]},
                            "変更後": {k: new[k] for k in GENKA_KEYS + ["合計"]}})
        if old_total > 0 and new["合計"] == 0:
            zeroed.append({"案件キー": key, "消える原価": old_total})
        a["原価"] = new

    # 原価が入っていた案件が0になるのは「シートを部分的にしか読めていない」兆候。
    # 正常な全件集計では、前回と同じシートを見ている限りここは空になる。
    warn_zero = ([f"⚠ {len(zeroed)}件の案件で原価が0にリセットされます"
                  f"（消える合計 {sum(z['消える原価'] for z in zeroed):,}円）。"
                  "原価管理Sheets を全期間読めているか確認してください。"]
                 if zeroed else [])

    if args.get("dry_run", True):
        return {"実行": "プレビュー（未書き込み）", "変更のある案件": len(changes),
                "ゼロ化される案件": zeroed, "変更内容": changes,
                "警告": warn_zero + agg["警告"],
                "次の操作": ("ゼロ化される案件を確認のうえ、意図通りなら "
                             "dry_run=false, allow_zeroing=true で実行してください"
                             if zeroed else "dry_run=false で data.json に書き戻します")}

    if zeroed and not ds.pick(args, "allow_zeroing", "ゼロ化を許可"):
        lines = "\n".join(f"- {z['案件キー']}: {z['消える原価']:,}円 → 0"
                          for z in zeroed[:15])
        more = f"\n…ほか{len(zeroed) - 15}件" if len(zeroed) > 15 else ""
        raise ToolError(
            f"原価が入っている {len(zeroed)}件の案件が0にリセットされるため、書き戻しを中止しました。\n"
            f"{lines}{more}\n\n"
            "原価管理Sheets を全期間読めていない可能性があります（年月で絞った集計や読み取り失敗）。\n"
            "内容を確認して意図通りであれば allow_zeroing=true を付けて再実行してください。")

    meta = ds.save_data(data, "genka_sync")
    return {"実行": "data.json へ書き戻し完了", "変更のある案件": len(changes),
            "ゼロ化された案件": zeroed, "変更内容": changes,
            "警告": warn_zero + agg["警告"], **meta}


def t_genka_validate(_args):
    res = api("read")
    rows = res["rows"]
    data = ds.load_data()
    problems = {"RC重複": [], "案件番号なし": [], "原価区分が不正": [],
                "金額が読めない": [], "data.jsonに無い案件番号": []}
    seen_rc = set()
    unknown = {}
    for r in rows:
        r = list(r) + [""] * (len(COLUMNS) - len(r))
        rc = str(r[IDX["レコードID"]]).strip()
        if rc:
            if rc in seen_rc:
                problems["RC重複"].append(rc)
            seen_rc.add(rc)
        anken = str(r[IDX["案件番号"]]).strip()
        if not anken:
            problems["案件番号なし"].append(rc or "(RC空)")
        elif anken != "共通" and not resolve_anken_key(data, anken):
            unknown.setdefault(anken, 0)
            unknown[anken] += 1
        if str(r[IDX["原価区分"]]).strip() not in (CHOKUSETSU, IPPAN):
            problems["原価区分が不正"].append(
                f"{rc or '(RC空)'}: 『{r[IDX['原価区分']]or '(空)'}』")
        try:
            to_amount(r[IDX["金額"]])
        except ValueError:
            problems["金額が読めない"].append(f"{rc or '(RC空)'}: 『{r[IDX['金額']]}』")
    problems["data.jsonに無い案件番号"] = [f"{k}（{v}行）" for k, v in sorted(unknown.items())]

    total = sum(len(v) for v in problems.values())
    return {"結果": "OK" if total == 0 else "要確認", "対象行数": len(rows),
            "指摘件数": total, "内訳": {k: v for k, v in problems.items() if v}}


TOOLS = [
    {"name": "genka_ping",
     "description": "原価管理Sheets への接続を確認する。シート名・明細行数・最終RC番号・次に採番されるRC番号を返す。まずこれで疎通を見る。",
     "inputSchema": {"type": "object", "properties": {}},
     "handler": t_genka_ping},
    {"name": "genka_next_rc",
     "description": "次に採番される RC-26-NNN を返す。実際の採番は追記時にスプレッドシート側で排他的に行うため、これは確認用。",
     "inputSchema": {"type": "object", "properties": {}},
     "handler": t_genka_next_rc},
    {"name": "genka_read",
     "description": "原価管理Sheets の明細を読む。案件番号（AR-26-xxx）・年月（YYYY-MM）・勘定科目で絞り込める。",
     "inputSchema": {"type": "object", "properties": {
         "anken_no": {"type": "string", "description": "案件番号（AR-26-xxx）"},
         "month": {"type": "string", "description": "年月 YYYY-MM"},
         "kamoku": {"type": "string", "description": "勘定科目（材料費・外注費 など）"},
         "limit": {"type": "integer", "description": "既定50"}}},
     "handler": t_genka_read},
    {"name": "genka_append_rows",
     "description": "原価管理Sheets に行を追記する。A列のRC番号はスプレッドシート側で排他採番するため渡さない。日付・店舗名・金額・品目が同じ行は二重計上として自動スキップする。既定は dry_run=true（プレビュー）。",
     "inputSchema": {"type": "object", "properties": {
         "rows": {"type": "array", "description":
                  "各行は12列の配列（" + " / ".join(INPUT_COLUMNS) + "）または列名をキーにしたオブジェクト"},
         "dry_run": {"type": "boolean", "description": "既定 true。false で実際に書き込む"}},
         "required": ["rows"]},
     "handler": t_genka_append_rows},
    {"name": "genka_import_tsv",
     "description": "amex-categorizer-post や receipt-processor が出力した貼付用TSVを読み込んで原価管理Sheets に追記する。13列(A〜M)・12列(B〜M)のどちらでも受け付ける。手作業の貼り付けを置き換えるツール。既定は dry_run=true。",
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string", "description": "TSV のフルパス"},
         "dry_run": {"type": "boolean", "description": "既定 true"}},
         "required": ["path"]},
     "handler": t_genka_import_tsv},
    {"name": "genka_aggregate",
     "description": "原価管理Sheets を案件別に4費目（労務費・材料費・外注費・経費）で集計する。案件番号は data.json の旧案件番号で案件キーに解決する。書き込みはしない。",
     "inputSchema": {"type": "object", "properties": {
         "month": {"type": "string", "description": "年月 YYYY-MM。省略時は全期間"}}},
     "handler": t_genka_aggregate},
    {"name": "genka_sync_to_data_json",
     "description": "集計結果を data.json の各案件の『原価』へ書き戻す。合計はサーバーが計算し、書き込みは検証・バックアップ・原子的差し替えを経由する。既定は dry_run=true（差分プレビュー）。原価が入っている案件が0にリセットされる場合は、シートを部分的にしか読めていない兆候として書き戻しを中止する。",
     "inputSchema": {"type": "object", "properties": {
         "dry_run": {"type": "boolean", "description": "既定 true。false で実際に書き戻す"},
         "allow_zeroing": {"type": "boolean", "description":
                           "原価が入っている案件を0にリセットしてよい場合のみ true。既定 false"}}},
     "handler": t_genka_sync_to_data_json},
    {"name": "genka_validate",
     "description": "原価管理Sheets を点検する。RC番号の重複・案件番号の欠落・原価区分の不正・金額の読み取り不能・data.json に無い案件番号を報告する。",
     "inputSchema": {"type": "object", "properties": {}},
     "handler": t_genka_validate},
]

TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}


# --------------------------------------------------------------------------
# MCP (JSON-RPC 2.0 over stdio) — artrays_data_server と同じ枠組み
# --------------------------------------------------------------------------

def handle_request(req: dict):
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}

    def ok(result):
        return None if req_id is None else {"jsonrpc": "2.0", "id": req_id, "result": result}

    if method == "initialize":
        proto = params.get("protocolVersion")
        return ok({
            "protocolVersion": proto if proto in ds.SUPPORTED_PROTOCOLS else ds.DEFAULT_PROTOCOL,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": (
                "原価管理Sheets の読み書きサーバー。TSVの手貼りは genka_import_tsv で置き換える。"
                "書き込み系は既定でプレビュー（dry_run=true）なので、内容を確認してから "
                "dry_run=false で実行すること。"),
        })
    if method in ("notifications/initialized", "initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": [{k: t[k] for k in ("name", "description", "inputSchema")}
                             for t in TOOLS]})
    if method == "tools/call":
        name = params.get("name")
        tool = TOOLS_BY_NAME.get(name)
        try:
            if tool is None:
                raise ToolError(f"未知のツールです: {name}")
            result = tool["handler"](params.get("arguments") or {})
            return ok({"content": [{"type": "text",
                                    "text": json.dumps(result, ensure_ascii=False, indent=2)}],
                       "isError": False})
        except ToolError as e:
            return ok({"content": [{"type": "text", "text": str(e)}], "isError": True})
        except Exception as e:
            ds.log(f"tools/call {name} 失敗: {e!r}")
            return ok({"content": [{"type": "text", "text": f"内部エラー: {e!r}"}],
                       "isError": True})
    if method in ("resources/list", "prompts/list"):
        return ok({"resources": []} if method == "resources/list" else {"prompts": []})
    return None if req_id is None else {
        "jsonrpc": "2.0", "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"}}


def serve():
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except AttributeError:  # pragma: no cover
        pass
    print(f"[{SERVER_NAME}] 起動しました", file=sys.stderr, flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        for one in (req if isinstance(req, list) else [req]):
            resp = handle_request(one)
            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()


def main():
    if "--ping" in sys.argv:
        try:
            print(json.dumps(t_genka_ping({}), ensure_ascii=False, indent=2))
            return 0
        except ToolError as e:
            print(str(e))
            return 1
    if "--tools" in sys.argv:
        for t in TOOLS:
            print(f"{t['name']:24} {t['description'][:66]}")
        return 0
    serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
