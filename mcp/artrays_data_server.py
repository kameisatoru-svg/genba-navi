#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""artrays-data — data.json 専用の MCP サーバー（stdio / 依存パッケージなし）

data.json を「全文読み → 全文書き戻し」する運用をやめ、
必要な部分だけを読み書きするためのツール群を提供する。

設計方針
  1. 壊さない  : 書き込みは 検証 → 旧内容を _backups/ へ退避 → 一時ファイル → os.replace(原子的)
  2. 軽い      : 案件1件・取引先1件の取得で 380KB を読み込ませない
  3. 依存ゼロ  : 標準ライブラリのみ。pip install 不要（Windows の素の Python で動く）

起動:  python mcp/artrays_data_server.py
検証:  python mcp/artrays_data_server.py --check
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

SERVER_NAME = "artrays-data"
SERVER_VERSION = "1.0.0"
DEFAULT_PROTOCOL = "2025-06-18"
SUPPORTED_PROTOCOLS = {"2024-11-05", "2025-03-26", "2025-06-18"}

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = Path(os.environ.get("ARTRAYS_DATA_JSON") or (REPO_ROOT / "data.json")).resolve()
BACKUP_DIR = Path(os.environ.get("ARTRAYS_BACKUP_DIR") or (DATA_PATH.parent / "_backups")).resolve()
BACKUP_KEEP = int(os.environ.get("ARTRAYS_BACKUP_KEEP") or 30)
LOCK_PATH = BACKUP_DIR / ".data.json.lock"
LOCK_STALE_SEC = 60

DOC_KINDS = ["見積", "請求", "注文書", "契約書", "完了書", "納品書"]
ANKEN_SCALAR_FIELDS = [
    "顧客略", "現場+工事", "正式工事名", "施工場所", "ステータス",
    "元請フラグ", "元請名", "備考", "旧案件番号", "規模", "最終更新",
]
KNOWN_STATUS = [
    "相談", "現地調査待ち", "見積準備", "見積提出済み", "施工予定", "施工中",
    "施工完了", "完了", "完了(請求書作成済み)", "請求済み", "入金済み",
    "保守管理(継続)", "中止",
]
GENKA_KEYS = ["労務費", "材料費", "外注費", "経費"]
ID_RE = re.compile(r"^T-\d{3}$")


class ToolError(Exception):
    """ツール実行時のユーザー向けエラー（スタックトレースは出さない）"""


class ValidationError(ToolError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("検証エラーのため書き込みを中止しました:\n- " + "\n- ".join(errors))


# --------------------------------------------------------------------------
# 入出力
# --------------------------------------------------------------------------

def now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def load_data() -> dict:
    if not DATA_PATH.exists():
        raise ToolError(f"data.json が見つかりません: {DATA_PATH}")
    raw = DATA_PATH.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ToolError(
            f"data.json が JSON として壊れています（{e}）。"
            f"\n_backups/ の直近バックアップ、または .git/data.json.goodbak から復旧してください。"
        )
    if not isinstance(data, dict):
        raise ToolError("data.json のトップレベルがオブジェクトではありません。")
    return data


def acquire_lock():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for _ in range(50):
        try:
            fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return
        except FileExistsError:
            try:
                if time.time() - LOCK_PATH.stat().st_mtime > LOCK_STALE_SEC:
                    LOCK_PATH.unlink(missing_ok=True)  # 放置ロックを奪う
                    continue
            except OSError:
                pass
            time.sleep(0.1)
    raise ToolError("data.json のロックを取得できませんでした（別の処理が書き込み中）。")


def release_lock():
    LOCK_PATH.unlink(missing_ok=True)


def make_backup(reason: str):
    """書き込み直前の内容を _backups/ に退避し、古いものを間引く。"""
    if not DATA_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^0-9A-Za-z_.-]+", "_", reason)[:40] or "write"
    dest = BACKUP_DIR / f"data.json.{datetime.now():%Y%m%d_%H%M%S}.{safe}.bak"
    shutil.copy2(DATA_PATH, dest)
    backups = sorted(BACKUP_DIR.glob("data.json.*.bak"))
    for old in backups[:-BACKUP_KEEP]:
        old.unlink(missing_ok=True)
    return dest


def baseline_errors() -> set:
    """書き込み前から data.json に在るエラー。これは新しい書き込みの妨げにしない。"""
    try:
        return set(validate(load_data())[0])
    except ToolError:
        return set()


def save_data(data: dict, reason: str) -> dict:
    """検証 → バックアップ → 原子的書き込み。

    ブロックするのは「この書き込みが新しく持ち込んだエラー」だけ。既存の不整合を
    抱えたファイルでも、無関係な更新は通す（直さないと何もできない状態を作らない）。
    """
    errors, warnings = validate(data)
    if errors:
        known = baseline_errors()
        new_errors = [e for e in errors if e not in known]
        if new_errors:
            raise ValidationError(new_errors)
        warnings = [f"[既存の不整合] {e}" for e in errors] + warnings
    data["最終更新"] = now_stamp()
    acquire_lock()
    try:
        backup = make_backup(reason)
        tmp = DATA_PATH.with_name(DATA_PATH.name + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, DATA_PATH)  # 同一ボリューム内なら原子的
    finally:
        release_lock()
    return {"最終更新": data["最終更新"], "バックアップ": str(backup) if backup else None,
            "警告": warnings}


# --------------------------------------------------------------------------
# 検証
# --------------------------------------------------------------------------

def validate(data: dict):
    """(errors, warnings) を返す。errors が1件でもあれば書き込みは行わない。"""
    errors, warnings = [], []

    for key, typ in [("取引先マスター", list), ("案件", list), ("中止案件", list),
                     ("部材", list), ("工具", list), ("持込リスト", list),
                     ("命名ルール", dict), ("単価マスタ", dict)]:
        if key not in data:
            errors.append(f"トップレベルキー『{key}』がありません")
        elif not isinstance(data[key], typ):
            errors.append(f"『{key}』の型が {typ.__name__} ではありません")
    if errors:
        return errors, warnings

    # 取引先マスター
    seen_ids = set()
    for i, t in enumerate(data["取引先マスター"]):
        where = f"取引先[{i}]"
        if not isinstance(t, dict):
            errors.append(f"{where} がオブジェクトではありません")
            continue
        tid = t.get("id", "")
        if not ID_RE.match(str(tid)):
            errors.append(f"{where} の id『{tid}』が T-NNN 形式ではありません")
        elif tid in seen_ids:
            errors.append(f"取引先 id『{tid}』が重複しています")
        else:
            seen_ids.add(tid)
        if not str(t.get("略称", "")).strip():
            errors.append(f"{where}({tid}) の略称が空です")
        for f in ("rel", "type"):
            if f in t and not isinstance(t[f], list):
                errors.append(f"{where}({tid}) の {f} が配列ではありません")

    # 案件 / 中止案件
    # 案件キーの一意性はコレクション単位で見る。中止案件は「参考保管のコピー」として
    # 案件側にも同じキーが残る運用なので、両方に在ること自体はエラーにしない。
    for coll in ("案件", "中止案件"):
        seen_keys = set()
        for i, a in enumerate(data[coll]):
            where = f"{coll}[{i}]"
            if not isinstance(a, dict):
                errors.append(f"{where} がオブジェクトではありません")
                continue
            key = a.get("案件キー", "")
            if not str(key).strip():
                errors.append(f"{where} の案件キーが空です")
            elif key in seen_keys:
                errors.append(f"{coll} 内で案件キー『{key}』が重複しています")
            else:
                seen_keys.add(key)

            for kind in DOC_KINDS:
                docs = a.get(kind)
                if docs is None:
                    continue
                if not isinstance(docs, list):
                    errors.append(f"{where}({key}) の『{kind}』が配列ではありません")
                    continue
                nums = set()
                for d in docs:
                    if not isinstance(d, dict):
                        errors.append(f"{where}({key}) の『{kind}』に非オブジェクトが含まれます")
                        continue
                    amount = d.get("金額")
                    if amount is not None and not isinstance(amount, (int, float)):
                        errors.append(f"{key} / {kind} / {d.get('書類番号','?')} の金額が数値ではありません")
                    num = d.get("書類番号")
                    if num:
                        if num in nums:
                            warnings.append(f"{key} の『{kind}』に書類番号の重複『{num}』")
                        nums.add(num)

            genka = a.get("原価")
            if genka is not None:
                if not isinstance(genka, dict):
                    errors.append(f"{where}({key}) の原価がオブジェクトではありません")
                else:
                    for gk in GENKA_KEYS:
                        v = genka.get(gk)
                        if v is not None and not isinstance(v, (int, float)):
                            errors.append(f"{key} の原価.{gk} が数値ではありません")
                    total = genka.get("合計")
                    calc = sum(genka.get(gk) or 0 for gk in GENKA_KEYS
                               if isinstance(genka.get(gk), (int, float)))
                    if isinstance(total, (int, float)) and abs(total - calc) > 0.5:
                        warnings.append(f"{key} の原価.合計({total}) が4費目の和({calc}) と一致しません")

            if a.get("ステータス") and a["ステータス"] not in KNOWN_STATUS:
                warnings.append(f"{key} のステータス『{a['ステータス']}』は既知の一覧にありません")

    # 中止案件にコピーがあるのに、案件側が中止になっていない取り違え
    chushi_keys = {a.get("案件キー") for a in data["中止案件"] if isinstance(a, dict)}
    for a in data["案件"]:
        if isinstance(a, dict) and a.get("案件キー") in chushi_keys and a.get("ステータス") != "中止":
            warnings.append(
                f"{a.get('案件キー')} は中止案件にも在りますが、案件側のステータスは『{a.get('ステータス')}』です")

    # 部材 / 工具 の id 重複
    for coll in ("部材", "工具"):
        ids = [r.get("id") for r in data[coll] if isinstance(r, dict)]
        dupes = {i for i in ids if i and ids.count(i) > 1}
        for d in sorted(dupes):
            errors.append(f"{coll} の id『{d}』が重複しています")

    return errors, warnings


# --------------------------------------------------------------------------
# 参照ヘルパー
# --------------------------------------------------------------------------

def all_anken(data: dict, include_chushi: bool = False):
    rows = list(data["案件"])
    if include_chushi:
        rows += list(data["中止案件"])
    return rows


def find_anken(data: dict, key: str, include_chushi: bool = True):
    """案件キー完全一致 → 旧案件番号 → 部分一致 の順で解決する。

    戻り値: (案件オブジェクト, 候補リスト)。一意に決まらないときは (None, 候補)。
    """
    key = (key or "").strip()
    if not key:
        raise ToolError("案件キーが空です")
    rows = all_anken(data, include_chushi)

    for a in rows:
        if a.get("案件キー") == key:
            return a, []
    norm = key.upper().replace(" ", "")
    for a in rows:
        if str(a.get("旧案件番号", "")).upper().replace(" ", "") == norm:
            return a, []
    hits = [a for a in rows
            if key in str(a.get("案件キー", ""))
            or key in str(a.get("正式工事名", ""))
            or key in str(a.get("顧客略", ""))
            or key in str(a.get("現場+工事", ""))]
    if len(hits) == 1:
        return hits[0], []
    return None, [{"案件キー": a.get("案件キー"), "正式工事名": a.get("正式工事名"),
                   "ステータス": a.get("ステータス")} for a in hits]


def require_anken(data: dict, key: str, include_chushi: bool = True):
    a, cands = find_anken(data, key, include_chushi)
    if a:
        return a
    if cands:
        lines = "\n".join(f"- {c['案件キー']} / {c['正式工事名']} / {c['ステータス']}" for c in cands)
        raise ToolError(f"『{key}』に複数の案件が該当します。案件キーを指定してください:\n{lines}")
    raise ToolError(f"『{key}』に該当する案件がありません。")


def anken_digest(a: dict) -> dict:
    genka = a.get("原価") or {}
    return {
        "案件キー": a.get("案件キー"),
        "正式工事名": a.get("正式工事名"),
        "顧客略": a.get("顧客略"),
        "ステータス": a.get("ステータス"),
        "施工場所": a.get("施工場所"),
        "旧案件番号": a.get("旧案件番号"),
        "見積件数": len(a.get("見積") or []),
        "請求合計": sum(d.get("金額") or 0 for d in (a.get("請求") or [])),
        "原価合計": genka.get("合計", 0),
    }


def next_torihikisaki_id(data: dict) -> str:
    nums = [int(t["id"][2:]) for t in data["取引先マスター"]
            if isinstance(t.get("id"), str) and ID_RE.match(t["id"])]
    return f"T-{(max(nums) + 1) if nums else 1:03d}"


# --------------------------------------------------------------------------
# ツール実装
# --------------------------------------------------------------------------

def t_data_overview(_args):
    data = load_data()
    status = {}
    for a in data["案件"]:
        status[a.get("ステータス", "?")] = status.get(a.get("ステータス", "?"), 0) + 1
    mishuu = [s for a in data["案件"] for s in (a.get("請求") or [])
              if s.get("入金状況") != "nyukin"]
    return {
        "最終更新": data.get("最終更新"),
        "件数": {k: len(data[k]) for k in
                 ["案件", "中止案件", "取引先マスター", "部材", "工具", "持込リスト"]},
        "ステータス内訳": dict(sorted(status.items(), key=lambda kv: -kv[1])),
        "未入金": {"件数": len(mishuu), "金額": sum(s.get("金額") or 0 for s in mishuu)},
        "data.json": str(DATA_PATH),
    }


def t_get_anken(args):
    data = load_data()
    a = require_anken(data, args.get("key", ""))
    sections = args.get("sections")
    if not sections:
        return a
    out = {k: a.get(k) for k in ANKEN_SCALAR_FIELDS if k in a}
    out["案件キー"] = a.get("案件キー")
    for s in sections:
        if s in a:
            out[s] = a[s]
    return out


def t_search_anken(args):
    data = load_data()
    rows = all_anken(data, bool(args.get("中止含む")))
    kw = (args.get("キーワード") or "").strip()
    cust = (args.get("顧客") or "").strip()
    status = (args.get("ステータス") or "").strip()

    def match(a):
        if cust and cust not in str(a.get("顧客略", "")):
            return False
        if status and status not in str(a.get("ステータス", "")):
            return False
        if args.get("元請のみ") and not a.get("元請フラグ"):
            return False
        if kw:
            blob = json.dumps({k: a.get(k) for k in
                               ["案件キー", "正式工事名", "顧客略", "現場+工事",
                                "施工場所", "備考", "旧案件番号"]}, ensure_ascii=False)
            if kw not in blob:
                return False
        return True

    hits = [anken_digest(a) for a in rows if match(a)]
    limit = int(args.get("limit") or 30)
    return {"件数": len(hits), "案件": hits[:limit]}


def t_list_mishuukin(_args):
    data = load_data()
    rows = []
    for a in data["案件"]:
        for s in (a.get("請求") or []):
            if s.get("入金状況") == "nyukin":
                continue
            rows.append({
                "案件キー": a.get("案件キー"),
                "顧客略": a.get("顧客略"),
                "書類番号": s.get("書類番号"),
                "発行日": s.get("発行日"),
                "支払期限": s.get("支払期限"),
                "金額": s.get("金額"),
                "入金状況": s.get("入金状況"),
            })
    rows.sort(key=lambda r: (r.get("支払期限") or "9999", r.get("発行日") or ""))
    return {"件数": len(rows), "合計金額": sum(r.get("金額") or 0 for r in rows), "請求": rows}


def t_search_torihikisaki(args):
    data = load_data()
    kw = (args.get("キーワード") or "").strip().lower()
    rel = (args.get("rel") or "").strip()
    hits = []
    for t in data["取引先マスター"]:
        if rel and rel not in (t.get("rel") or []):
            continue
        if kw:
            blob = " ".join([str(t.get("id", "")), str(t.get("略称", "")),
                             str(t.get("正式名称", "")), str(t.get("search", "")),
                             str(t.get("memo", ""))]).lower()
            if kw not in blob:
                continue
        hits.append({"id": t.get("id"), "略称": t.get("略称"),
                     "正式名称": t.get("正式名称"), "rel": t.get("rel"),
                     "type": t.get("type")})
    limit = int(args.get("limit") or 30)
    return {"件数": len(hits), "取引先": hits[:limit]}


def t_get_torihikisaki(args):
    data = load_data()
    key = (args.get("key") or "").strip()
    if not key:
        raise ToolError("key が空です")
    for t in data["取引先マスター"]:
        if t.get("id") == key or t.get("略称") == key:
            return t
    hits = [t for t in data["取引先マスター"]
            if key in str(t.get("正式名称", "")) or key in str(t.get("略称", ""))
            or key.lower() in str(t.get("search", "")).lower()]
    if len(hits) == 1:
        return hits[0]
    if hits:
        raise ToolError("複数該当します: " + ", ".join(f"{t['id']}({t['略称']})" for t in hits))
    raise ToolError(f"『{key}』に該当する取引先がありません。")


def t_validate_data(_args):
    data = load_data()
    errors, warnings = validate(data)
    return {"結果": "OK" if not errors else "NG", "エラー": errors, "警告": warnings,
            "バックアップ数": len(list(BACKUP_DIR.glob("data.json.*.bak"))) if BACKUP_DIR.exists() else 0}


def t_list_backups(_args):
    if not BACKUP_DIR.exists():
        return {"件数": 0, "バックアップ": [], "保存先": str(BACKUP_DIR)}
    rows = []
    for p in sorted(BACKUP_DIR.glob("data.json.*.bak"), reverse=True)[:20]:
        st = p.stat()
        rows.append({"ファイル": p.name, "サイズ": st.st_size,
                     "日時": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")})
    return {"件数": len(rows), "保存先": str(BACKUP_DIR), "バックアップ": rows}


def t_create_anken(args):
    data = load_data()
    key = (args.get("案件キー") or "").strip()
    if not key:
        raise ToolError("案件キーは必須です（例: 玉寿会-さくら床-26）")
    existing, _ = find_anken(data, key)
    if existing and existing.get("案件キー") == key:
        raise ToolError(f"案件キー『{key}』は既に存在します。")
    anken = {
        "案件キー": key,
        "顧客略": args.get("顧客略") or key.split("-")[0],
        "現場+工事": args.get("現場+工事") or (key.split("-")[1] if "-" in key else ""),
        "正式工事名": args.get("正式工事名") or "",
        "施工場所": args.get("施工場所") or "",
        "ステータス": args.get("ステータス") or "相談",
        "元請フラグ": bool(args.get("元請フラグ")),
        "元請名": args.get("元請名") or "",
        "備考": args.get("備考") or "",
        "旧案件番号": args.get("旧案件番号") or "",
        "見積": [], "請求": [], "注文書": [], "契約書": [],
        "原価": {"労務費": 0, "材料費": 0, "外注費": 0, "経費": 0,
                 "合計": 0, "件数": 0, "最終集計日": ""},
    }
    data["案件"].append(anken)
    meta = save_data(data, f"create_anken_{key}")
    return {"作成": key, **meta}


def t_patch_anken(args):
    data = load_data()
    a = require_anken(data, args.get("key", ""))
    fields = args.get("fields") or {}
    if not isinstance(fields, dict) or not fields:
        raise ToolError("fields に更新内容を指定してください")
    unknown = [k for k in fields if k not in ANKEN_SCALAR_FIELDS]
    if unknown:
        raise ToolError(
            f"このツールで更新できないフィールドです: {', '.join(unknown)}\n"
            f"（書類は append_document / update_document、原価は set_genka を使ってください）\n"
            f"更新可能: {', '.join(ANKEN_SCALAR_FIELDS)}")
    before = {k: a.get(k) for k in fields}
    a.update(fields)
    meta = save_data(data, f"patch_anken_{a['案件キー']}")
    return {"案件キー": a["案件キー"], "変更前": before, "変更後": fields, **meta}


def t_append_document(args):
    data = load_data()
    a = require_anken(data, args.get("key", ""))
    kind = args.get("種別")
    if kind not in DOC_KINDS:
        raise ToolError(f"種別は {', '.join(DOC_KINDS)} のいずれかです（指定: {kind}）")
    rec = args.get("record")
    if not isinstance(rec, dict) or not rec:
        raise ToolError("record にオブジェクトを指定してください")
    docs = a.setdefault(kind, [])
    num = rec.get("書類番号")
    if num and any(d.get("書類番号") == num for d in docs):
        raise ToolError(f"書類番号『{num}』は {a['案件キー']} の『{kind}』に既に存在します。"
                        f"更新なら update_document を使ってください。")
    docs.append(rec)
    meta = save_data(data, f"append_{kind}_{a['案件キー']}")
    return {"案件キー": a["案件キー"], "種別": kind, "追加": rec, "件数": len(docs), **meta}


def t_update_document(args):
    data = load_data()
    a = require_anken(data, args.get("key", ""))
    kind = args.get("種別")
    if kind not in DOC_KINDS:
        raise ToolError(f"種別は {', '.join(DOC_KINDS)} のいずれかです（指定: {kind}）")
    num = args.get("書類番号")
    fields = args.get("fields") or {}
    if not isinstance(fields, dict) or not fields:
        raise ToolError("fields に更新内容を指定してください")
    docs = a.get(kind) or []
    target = next((d for d in docs if d.get("書類番号") == num), None)
    if target is None:
        avail = ", ".join(str(d.get("書類番号")) for d in docs) or "（なし）"
        raise ToolError(f"{a['案件キー']} の『{kind}』に書類番号『{num}』がありません。存在するのは: {avail}")
    before = {k: target.get(k) for k in fields}
    target.update(fields)
    meta = save_data(data, f"update_{kind}_{a['案件キー']}")
    return {"案件キー": a["案件キー"], "種別": kind, "書類番号": num,
            "変更前": before, "変更後": fields, **meta}


def t_set_genka(args):
    data = load_data()
    a = require_anken(data, args.get("key", ""))
    vals = {}
    for gk in GENKA_KEYS:
        v = args.get(gk, 0) or 0
        if not isinstance(v, (int, float)):
            raise ToolError(f"{gk} は数値で指定してください（指定: {v!r}）")
        vals[gk] = v
    genka = {**vals, "合計": sum(vals.values()),
             "件数": int(args.get("件数") or 0),
             "最終集計日": args.get("最終集計日") or datetime.now().strftime("%Y-%m-%d")}
    before = a.get("原価")
    a["原価"] = genka
    meta = save_data(data, f"set_genka_{a['案件キー']}")
    return {"案件キー": a["案件キー"], "変更前": before, "変更後": genka, **meta}


def t_upsert_torihikisaki(args):
    data = load_data()
    ryaku = (args.get("略称") or "").strip()
    tid = (args.get("id") or "").strip()
    if not ryaku and not tid:
        raise ToolError("略称 または id のどちらかは必須です")

    target = None
    if tid:
        target = next((t for t in data["取引先マスター"] if t.get("id") == tid), None)
        if target is None:
            raise ToolError(f"id『{tid}』の取引先がありません。新規なら id を省略してください。")
    else:
        target = next((t for t in data["取引先マスター"] if t.get("略称") == ryaku), None)

    created = target is None
    if created:
        target = {"id": next_torihikisaki_id(data), "略称": ryaku, "正式名称": "",
                  "rel": [], "type": [], "basic": {}, "contact": {},
                  "memo": "", "注意点": "", "search": ""}
        data["取引先マスター"].append(target)

    for f in ("略称", "正式名称", "memo", "注意点", "search"):
        if args.get(f) is not None:
            target[f] = args[f]
    for f in ("rel", "type"):
        if args.get(f) is not None:
            v = args[f]
            target[f] = v if isinstance(v, list) else [v]
    for f in ("basic", "contact"):
        if isinstance(args.get(f), dict):
            target.setdefault(f, {}).update(args[f])

    if not str(target.get("search", "")).strip():
        target["search"] = " ".join(filter(None, [
            str(target.get("id", "")).lower(), target.get("略称", ""),
            target.get("正式名称", "")]))

    meta = save_data(data, f"upsert_torihikisaki_{target['id']}")
    return {"操作": "新規登録" if created else "更新", "取引先": target, **meta}


TOOLS = [
    {
        "name": "data_overview",
        "description": "data.json の全体像（最終更新・各コレクション件数・案件ステータス内訳・未入金合計）を返す。まず状況を掴みたいときに使う。",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": t_data_overview,
    },
    {
        "name": "get_anken",
        "description": "案件を1件取得する。key は 案件キー / 旧案件番号(AR-26-xxx) / 部分一致 のいずれでも解決する。sections で必要な配列だけに絞れる（見積・請求・注文書・契約書・完了書・納品書・原価・チェック・動き）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "案件キー・旧案件番号・現場名の一部"},
                "sections": {"type": "array", "items": {"type": "string"},
                             "description": "取得する配列名。省略時は案件全体"},
            },
            "required": ["key"],
        },
        "handler": t_get_anken,
    },
    {
        "name": "search_anken",
        "description": "案件を条件で検索し、要約行（案件キー・工事名・ステータス・請求合計・原価合計）で返す。全文を読み込まずに一覧を掴むためのツール。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "キーワード": {"type": "string"},
                "顧客": {"type": "string"},
                "ステータス": {"type": "string"},
                "元請のみ": {"type": "boolean"},
                "中止含む": {"type": "boolean"},
                "limit": {"type": "integer", "description": "既定30"},
            },
        },
        "handler": t_search_anken,
    },
    {
        "name": "list_mishuukin",
        "description": "未入金（入金状況が nyukin 以外）の請求を、支払期限順に一覧する。入金管理の確認用。",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": t_list_mishuukin,
    },
    {
        "name": "search_torihikisaki",
        "description": "取引先マスターを検索する（略称・正式名称・search・memo を対象）。rel で 顧客/業者/仕入先/元請 に絞れる。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "キーワード": {"type": "string"},
                "rel": {"type": "string", "description": "顧客 / 業者 / 仕入先 / 元請 など"},
                "limit": {"type": "integer", "description": "既定30"},
            },
        },
        "handler": t_search_torihikisaki,
    },
    {
        "name": "get_torihikisaki",
        "description": "取引先を1件取得する。key は T番号 / 略称 / 正式名称の一部。",
        "inputSchema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
        "handler": t_get_torihikisaki,
    },
    {
        "name": "validate_data",
        "description": "data.json の整合性を検証する（案件キー重複・T番号形式・金額の型・原価合計の不一致など）。書き込み前後の点検用。",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": t_validate_data,
    },
    {
        "name": "list_backups",
        "description": "_backups/ に退避された data.json バックアップの新しい順一覧。復旧時にどれを戻すか判断するために使う。",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": t_list_backups,
    },
    {
        "name": "create_anken",
        "description": "案件を新規作成する（書類配列と原価0の雛形付き）。案件キーの重複は拒否する。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "案件キー": {"type": "string", "description": "[顧客4文字以内]-[現場+工事8文字以内]-26"},
                "顧客略": {"type": "string"},
                "現場+工事": {"type": "string"},
                "正式工事名": {"type": "string"},
                "施工場所": {"type": "string"},
                "ステータス": {"type": "string", "description": "既定は『相談』"},
                "元請フラグ": {"type": "boolean"},
                "元請名": {"type": "string"},
                "備考": {"type": "string"},
                "旧案件番号": {"type": "string"},
            },
            "required": ["案件キー"],
        },
        "handler": t_create_anken,
    },
    {
        "name": "patch_anken",
        "description": "案件のスカラー項目（ステータス・備考・正式工事名など）を部分更新する。書類配列と原価は専用ツール側で扱う。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "fields": {"type": "object", "description": "更新する項目。指定可: " + " / ".join(ANKEN_SCALAR_FIELDS)},
            },
            "required": ["key", "fields"],
        },
        "handler": t_patch_anken,
    },
    {
        "name": "append_document",
        "description": "案件に書類レコードを追加する（見積・請求・注文書・契約書・完了書・納品書）。同じ書類番号があれば拒否する。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "種別": {"type": "string", "enum": DOC_KINDS},
                "record": {"type": "object", "description": "書類番号・発行日・金額・ファイル・備考など"},
            },
            "required": ["key", "種別", "record"],
        },
        "handler": t_append_document,
    },
    {
        "name": "update_document",
        "description": "既存の書類レコードを部分更新する。入金反映（入金状況=nyukin・入金日）にも使う。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "種別": {"type": "string", "enum": DOC_KINDS},
                "書類番号": {"type": "string"},
                "fields": {"type": "object"},
            },
            "required": ["key", "種別", "書類番号", "fields"],
        },
        "handler": t_update_document,
    },
    {
        "name": "set_genka",
        "description": "案件の原価（労務費・材料費・外注費・経費）を設定する。合計はサーバー側で計算するため手計算のズレが起きない。genka-aggregate の書き戻し口。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "労務費": {"type": "number"},
                "材料費": {"type": "number"},
                "外注費": {"type": "number"},
                "経費": {"type": "number"},
                "件数": {"type": "integer"},
                "最終集計日": {"type": "string", "description": "YYYY-MM-DD。省略時は本日"},
            },
            "required": ["key"],
        },
        "handler": t_set_genka,
    },
    {
        "name": "upsert_torihikisaki",
        "description": "取引先を登録・更新する。新規の T番号はサーバー側で採番するため重複しない。名刺登録・未登録業者の追加に使う。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "更新時のみ。新規は省略（自動採番）"},
                "略称": {"type": "string"},
                "正式名称": {"type": "string"},
                "rel": {"type": "array", "items": {"type": "string"}, "description": "顧客 / 業者 / 仕入先 / 元請 など"},
                "type": {"type": "array", "items": {"type": "string"}},
                "basic": {"type": "object"},
                "contact": {"type": "object", "description": "tel / mobile / fax / mail / address / touroku / furikomi"},
                "memo": {"type": "string"},
                "注意点": {"type": "string"},
                "search": {"type": "string"},
            },
        },
        "handler": t_upsert_torihikisaki,
    },
]

TOOLS_BY_NAME = {t["name"]: t for t in TOOLS}


# --------------------------------------------------------------------------
# MCP (JSON-RPC 2.0 over stdio)
# --------------------------------------------------------------------------

def log(msg: str):
    print(f"[{SERVER_NAME}] {msg}", file=sys.stderr, flush=True)


def call_tool(name: str, args: dict):
    tool = TOOLS_BY_NAME.get(name)
    if tool is None:
        raise ToolError(f"未知のツールです: {name}")
    return tool["handler"](args or {})


def handle_request(req: dict):
    """レスポンスを返す。通知（id なし）の場合は None。"""
    method = req.get("method")
    req_id = req.get("id")
    params = req.get("params") or {}

    def ok(result):
        return None if req_id is None else {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code, message):
        return None if req_id is None else {"jsonrpc": "2.0", "id": req_id,
                                            "error": {"code": code, "message": message}}

    if method == "initialize":
        client_proto = params.get("protocolVersion")
        proto = client_proto if client_proto in SUPPORTED_PROTOCOLS else DEFAULT_PROTOCOL
        return ok({
            "protocolVersion": proto,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": (
                "アート・レイズの data.json を安全に読み書きするサーバー。"
                "data.json を丸ごと Read/Write せず、必ずこのツール群を使うこと。"
                "書き込みは自動でバックアップ・検証される。"
            ),
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
        args = params.get("arguments") or {}
        try:
            result = call_tool(name, args)
            text = json.dumps(result, ensure_ascii=False, indent=2)
            return ok({"content": [{"type": "text", "text": text}], "isError": False})
        except ToolError as e:
            return ok({"content": [{"type": "text", "text": str(e)}], "isError": True})
        except Exception as e:  # 想定外は落とさずエラー内容を返す
            log(f"tools/call {name} 失敗: {e!r}")
            return ok({"content": [{"type": "text", "text": f"内部エラー: {e!r}"}],
                       "isError": True})

    if method in ("resources/list", "prompts/list"):
        return ok({"resources": []} if method == "resources/list" else {"prompts": []})

    return err(-32601, f"Method not found: {method}")


def serve():
    try:
        sys.stdin.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except AttributeError:  # pragma: no cover
        pass
    log(f"起動しました data.json={DATA_PATH}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            log(f"JSON として読めない入力を無視: {line[:120]}")
            continue
        for one in (req if isinstance(req, list) else [req]):
            resp = handle_request(one)
            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
    log("標準入力が閉じたため終了します")


def main():
    if "--check" in sys.argv:
        try:
            report = t_validate_data({})
        except ToolError as e:
            print(str(e))
            return 2
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["結果"] == "OK" else 1
    if "--tools" in sys.argv:
        for t in TOOLS:
            print(f"{t['name']:22} {t['description'][:70]}")
        return 0
    serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
