#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""artrays_genka_server の自己テスト（標準ライブラリのみ）

本物のスプレッドシートは使わない。Apps Script ウェブアプリと同じ契約を実装した
スタブHTTPサーバーを localhost に立てて、クライアント側のロジックを検証する。
Apps Script が実際に返す 302 リダイレクトも再現する。

実行:  python mcp/test_artrays_genka.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_DATA = HERE.parent / "data.json"

TMP_DIR = Path(tempfile.mkdtemp(prefix="artrays_genka_test_"))
TMP_DATA = TMP_DIR / "data.json"
TOKEN = "test-token-12345"

os.environ["ARTRAYS_DATA_JSON"] = str(TMP_DATA)
os.environ["ARTRAYS_BACKUP_DIR"] = str(TMP_DIR / "_backups")
os.environ["ARTRAYS_GENKA_TOKEN"] = TOKEN

FALLBACK_DATA = {
    "最終更新": "2026-01-01 00:00", "命名ルール": {},
    "取引先マスター": [{"id": "T-001", "略称": "玉寿会", "正式名称": "玉寿会",
                        "rel": ["顧客"], "type": ["公共施設"], "basic": {},
                        "contact": {}, "memo": "", "注意点": "", "search": ""}],
    "案件": [
        {"案件キー": "玉寿会-さくら床-26", "顧客略": "玉寿会", "現場+工事": "さくら床",
         "正式工事名": "さくら苑 床工事", "施工場所": "熊本県玉名市",
         "ステータス": "入金済み", "元請フラグ": False, "元請名": "", "備考": "",
         "旧案件番号": "AR-26-004", "見積": [], "請求": [], "注文書": [], "契約書": [],
         "原価": {"労務費": 0, "材料費": 0, "外注費": 0, "経費": 0,
                  "合計": 0, "件数": 0, "最終集計日": ""}},
    ],
    "中止案件": [], "部材": [], "工具": [], "持込リスト": [],
    "単価マスタ": {"天井": {}, "壁": {}, "床": {}},
}

# ---------------------------------------------------------------- スタブ

SEED_ROWS = [
    ["RC-26-001", "AR-26-004", "さくら苑", "2026-04-02", "コメリ", "ビス・接着剤",
     "12000", "材料費", "直接原価", "カード", "AMEX明細", "", "2026-04-30"],
    ["RC-26-002", "AR-26-004", "さくら苑", "2026-04-05", "川原内装", "内装工事一式",
     "220000", "外注費", "直接原価", "振込", "業者請求書", "", "2026-04-30"],
    ["RC-26-003", "AR-26-004", "さくら苑", "2026-04-08", "ENEOS", "高速・給油",
     "8500", "旅費交通費", "直接原価", "カード", "AMEX明細", "", "2026-04-30"],
    ["RC-26-004", "共通", "共通", "2026-04-10", "ANTHROPIC", "Claude",
     "3000", "通信費", "一般経費", "カード", "AMEX明細", "", "2026-04-30"],
    ["RC-26-005", "AR-26-999", "謎の現場", "2026-05-01", "どこか", "なにか",
     "5000", "材料費", "直接原価", "現金", "領収書", "", "2026-05-31"],
    ["RC-26-006", "AR-26-004", "さくら苑", "2026-05-02", "ダイキ", "副資材",
     "3300", "材料費", "", "現金", "領収書", "区分空欄", "2026-05-31"],
]


class Stub:
    """Apps Script 側（genka_api.gs）と同じ振る舞いを再現する"""

    def __init__(self):
        self.reset()

    def reset(self):
        self.rows = [list(r) for r in SEED_ROWS]
        self.calls = []

    @staticmethod
    def _rc_num(v):
        s = str(v or "")
        return int(s[6:]) if s.startswith("RC-26-") and s[6:].isdigit() else 0

    def _max_rc(self):
        return max([self._rc_num(r[0]) for r in self.rows] or [0])

    @staticmethod
    def _dup_key(date, shop, amount, item):
        n = "".join(c for c in str(amount) if c.isdigit() or c in ".-")
        return "|".join([str(date).strip(), str(shop).strip(), n, str(item).strip()])

    def handle(self, p):
        self.calls.append(p.get("action"))
        if p.get("token") != TOKEN:
            return {"ok": False, "error": "認証に失敗しました"}
        action = p.get("action")

        if action == "ping":
            return {"ok": True, "sheet": "原価管理", "spreadsheet": "原価管理台帳",
                    "rows": len(self.rows),
                    "lastRC": f"RC-26-{self._max_rc():03d}" if self.rows else None,
                    "nextRC": f"RC-26-{self._max_rc() + 1:03d}"}

        if action == "next_rc":
            return {"ok": True, "nextRC": f"RC-26-{self._max_rc() + 1:03d}"}

        if action == "read":
            out = []
            for r in self.rows:
                if p.get("anken") and r[1].strip() != str(p["anken"]).strip():
                    continue
                if p.get("month") and not r[3].startswith(str(p["month"])):
                    continue
                if p.get("kamoku") and r[7].strip() != str(p["kamoku"]).strip():
                    continue
                out.append(list(r))
            return {"ok": True, "count": len(out), "total": len(self.rows), "rows": out}

        if action == "append":
            incoming = p.get("rows") or []
            if not incoming:
                return {"ok": False, "error": "rows が空です"}
            seen = {self._dup_key(r[3], r[4], r[6], r[5]): r[0] for r in self.rows}
            nxt = self._max_rc() + 1
            to_write, assigned, skipped = [], [], []
            for i, r in enumerate(incoming):
                if len(r) != 12:
                    return {"ok": False, "error": f"行 {i+1} の列数が 12 ではありません（{len(r)}）"}
                key = self._dup_key(r[2], r[3], r[5], r[4])
                if key in seen:
                    skipped.append({"index": i, "reason": "既存行と重複",
                                    "既存RC": seen[key], "日付": r[2],
                                    "店舗名": r[3], "金額": r[5]})
                    continue
                rc = f"RC-26-{nxt:03d}"
                nxt += 1
                seen[key] = rc
                assigned.append({"index": i, "RC": rc, "案件番号": r[0], "日付": r[2],
                                 "店舗名": r[3], "金額": r[5]})
                to_write.append([rc] + [str(c) for c in r])
            if not p.get("dryRun"):
                self.rows.extend(to_write)
            return {"ok": True, "dryRun": bool(p.get("dryRun")),
                    "appended": 0 if p.get("dryRun") else len(to_write),
                    "assigned": assigned, "skipped": skipped,
                    "rowsAfter": len(self.rows)}

        return {"ok": False, "error": f"未知の action: {action}"}


STUB = Stub()
LAST_POST = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        payload = json.loads(raw.decode("utf-8"))
        if self.path == "/redirect":
            # Apps Script は POST に 302 を返し、本体は別URLで配る
            LAST_POST["payload"] = payload
            self.send_response(302)
            self.send_header("Location", "/redirected-result")
            self.end_headers()
            return
        if self.path == "/notjson":
            body = b"<!DOCTYPE html><html><body>Google Drive - Sign in</body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/servererror":
            self._send({"ok": False}, code=500)
            return
        self._send(STUB.handle(payload))

    def do_GET(self):
        if self.path == "/redirected-result":
            self._send(STUB.handle(LAST_POST.get("payload", {})))
            return
        self._send({"ok": False, "error": "GET は未対応"}, code=405)


httpd = HTTPServer(("127.0.0.1", 0), Handler)
PORT = httpd.server_address[1]
threading.Thread(target=httpd.serve_forever, daemon=True).start()
os.environ["ARTRAYS_GENKA_URL"] = f"http://127.0.0.1:{PORT}/exec"

spec = importlib.util.spec_from_file_location("artrays_genka_server",
                                              HERE / "artrays_genka_server.py")
gk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gk)


class Base(unittest.TestCase):
    def setUp(self):
        STUB.reset()
        if SOURCE_DATA.exists():
            shutil.copy2(SOURCE_DATA, TMP_DATA)
        else:
            TMP_DATA.write_text(json.dumps(FALLBACK_DATA, ensure_ascii=False),
                                encoding="utf-8")
        os.environ["ARTRAYS_GENKA_URL"] = f"http://127.0.0.1:{PORT}/exec"
        backups = Path(os.environ["ARTRAYS_BACKUP_DIR"])
        if backups.exists():
            shutil.rmtree(backups)

    def row(self, **over):
        base = {"案件番号": "AR-26-004", "現場名": "さくら苑", "日付": "2026-06-01",
                "店舗名・業者名": "テスト商店", "品目・内容": "テスト品",
                "金額": "1000", "勘定科目": "材料費", "原価区分": "直接原価",
                "支払方法": "現金", "ソース": "領収書", "備考": "", "登録日": "2026-06-30"}
        base.update(over)
        return base


class TestConnection(Base):
    def test_pingが接続情報を返す(self):
        r = gk.t_genka_ping({})
        self.assertEqual(r["接続"], "OK")
        self.assertEqual(r["明細行数"], len(SEED_ROWS))
        self.assertEqual(r["次のRC"], "RC-26-007")

    def test_トークン不一致は明確なエラーになる(self):
        os.environ["ARTRAYS_GENKA_TOKEN"] = "wrong"
        try:
            with self.assertRaises(gk.ToolError) as cm:
                gk.t_genka_ping({})
            self.assertIn("認証に失敗", str(cm.exception))
        finally:
            os.environ["ARTRAYS_GENKA_TOKEN"] = TOKEN

    def test_302リダイレクトを追う(self):
        os.environ["ARTRAYS_GENKA_URL"] = f"http://127.0.0.1:{PORT}/redirect"
        r = gk.t_genka_ping({})
        self.assertEqual(r["接続"], "OK")

    def test_HTMLが返ったらデプロイ設定を案内する(self):
        os.environ["ARTRAYS_GENKA_URL"] = f"http://127.0.0.1:{PORT}/notjson"
        with self.assertRaises(gk.ToolError) as cm:
            gk.t_genka_ping({})
        self.assertIn("デプロイ設定", str(cm.exception))

    def test_接続先未設定なら手順を案内する(self):
        url, token = os.environ.pop("ARTRAYS_GENKA_URL"), os.environ.pop("ARTRAYS_GENKA_TOKEN")
        gk.CONFIG_PATH = TMP_DIR / "no_such_config.json"
        try:
            with self.assertRaises(gk.ToolError) as cm:
                gk.t_genka_ping({})
            self.assertIn("接続先が未設定", str(cm.exception))
        finally:
            os.environ["ARTRAYS_GENKA_URL"], os.environ["ARTRAYS_GENKA_TOKEN"] = url, token


class TestRead(Base):
    def test_案件番号で絞れる(self):
        r = gk.t_genka_read({"案件番号": "AR-26-004"})
        self.assertEqual(r["該当"], 4)
        self.assertTrue(all(m["案件番号"] == "AR-26-004" for m in r["明細"]))

    def test_年月で絞れる(self):
        self.assertEqual(gk.t_genka_read({"年月": "2026-04"})["該当"], 4)
        self.assertEqual(gk.t_genka_read({"年月": "2026-05"})["該当"], 2)

    def test_明細は列名つきで返る(self):
        m = gk.t_genka_read({"limit": 1})["明細"][0]
        self.assertEqual(m["レコードID"], "RC-26-001")
        self.assertEqual(m["勘定科目"], "材料費")


class TestAppend(Base):
    def test_dry_runでは書き込まれない(self):
        r = gk.t_genka_append_rows({"rows": [self.row()]})
        self.assertIn("プレビュー", r["実行"])
        self.assertEqual(r["採番"][0]["RC"], "RC-26-007")
        self.assertEqual(len(STUB.rows), len(SEED_ROWS))

    def test_本実行で採番されて書き込まれる(self):
        r = gk.t_genka_append_rows({"rows": [self.row(), self.row(日付="2026-06-02")],
                                    "dry_run": False})
        self.assertEqual(r["追記行数"], 2)
        self.assertEqual([a["RC"] for a in r["採番"]], ["RC-26-007", "RC-26-008"])
        self.assertEqual(len(STUB.rows), len(SEED_ROWS) + 2)

    def test_同じ内容の再投入は重複としてスキップされる(self):
        gk.t_genka_append_rows({"rows": [self.row()], "dry_run": False})
        r = gk.t_genka_append_rows({"rows": [self.row()], "dry_run": False})
        self.assertEqual(r["追記行数"], 0)
        self.assertEqual(len(r["重複でスキップ"]), 1)
        self.assertEqual(r["重複でスキップ"][0]["既存RC"], "RC-26-007")

    def test_原価区分が不正なら通信前に弾く(self):
        before = len(STUB.calls)
        with self.assertRaises(gk.ToolError) as cm:
            gk.t_genka_append_rows({"rows": [self.row(原価区分="経費")]})
        self.assertIn("原価区分", str(cm.exception))
        self.assertEqual(len(STUB.calls), before, "検証前にAPIを呼んでいる")

    def test_金額が数値でなければ弾く(self):
        with self.assertRaises(gk.ToolError) as cm:
            gk.t_genka_append_rows({"rows": [self.row(金額="いくらか")]})
        self.assertIn("金額", str(cm.exception))

    def test_カンマ付き金額は受け付けて数値化する(self):
        r = gk.t_genka_append_rows({"rows": [self.row(金額="¥12,345")], "dry_run": False})
        self.assertEqual(STUB.rows[-1][6], "12345")

    def test_列不足のオブジェクトは弾く(self):
        with self.assertRaises(gk.ToolError) as cm:
            gk.t_genka_append_rows({"rows": [{"案件番号": "AR-26-004"}]})
        self.assertIn("不足", str(cm.exception))

    def test_配列でも渡せる(self):
        arr = [self.row()[c] for c in gk.INPUT_COLUMNS]
        r = gk.t_genka_append_rows({"rows": [arr], "dry_run": False})
        self.assertEqual(r["追記行数"], 1)

    def test_登録日が空なら実行日で埋める(self):
        gk.t_genka_append_rows({"rows": [self.row(登録日="")], "dry_run": False})
        self.assertTrue(STUB.rows[-1][12], "登録日が空のまま書き込まれた")


class TestImportTsv(Base):
    def write_tsv(self, name, lines):
        p = TMP_DIR / name
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    def test_12列TSVを取り込める(self):
        r = self.row()
        p = self.write_tsv("t12.tsv", ["\t".join(str(r[c]) for c in gk.INPUT_COLUMNS)])
        res = gk.t_genka_import_tsv({"path": str(p), "dry_run": False})
        self.assertEqual(res["追記行数"], 1)

    def test_13列TSVはA列を捨てて取り込む(self):
        r = self.row(日付="2026-06-03")
        cells = ["RC-26-999"] + [str(r[c]) for c in gk.INPUT_COLUMNS]
        p = self.write_tsv("t13.tsv", ["\t".join(cells)])
        res = gk.t_genka_import_tsv({"path": str(p), "dry_run": False})
        self.assertEqual(res["採番"][0]["RC"], "RC-26-007", "TSVのA列を無視していない")

    def test_ヘッダー行を読み飛ばす(self):
        r = self.row(日付="2026-06-04")
        p = self.write_tsv("thead.tsv", [
            "\t".join(gk.COLUMNS),
            "\t".join(["RC-26-000"] + [str(r[c]) for c in gk.INPUT_COLUMNS])])
        res = gk.t_genka_import_tsv({"path": str(p), "dry_run": False})
        self.assertEqual(res["追記行数"], 1)

    def test_列数が合わないTSVは明確に断る(self):
        p = self.write_tsv("tbad.tsv", ["a\tb\tc"])
        with self.assertRaises(gk.ToolError) as cm:
            gk.t_genka_import_tsv({"path": str(p)})
        self.assertIn("列数", str(cm.exception))

    def test_存在しないTSVは明確に断る(self):
        with self.assertRaises(gk.ToolError) as cm:
            gk.t_genka_import_tsv({"path": str(TMP_DIR / "no.tsv")})
        self.assertIn("見つかりません", str(cm.exception))


class TestAggregate(Base):
    def test_4分類マッピング(self):
        self.assertEqual(gk.classify("材料費", "直接原価")[0], "材料費")
        self.assertEqual(gk.classify("外注費", "直接原価")[0], "外注費")
        self.assertEqual(gk.classify("労務費", "直接原価")[0], "労務費")
        self.assertEqual(gk.classify("旅費交通費", "直接原価")[0], "経費")
        self.assertEqual(gk.classify("通信費", "一般経費")[0], "経費")

    def test_原価区分が空なら経費に入れて警告する(self):
        bucket, warn = gk.classify("材料費", "")
        self.assertEqual(bucket, "経費")
        self.assertIsNotNone(warn)

    def test_案件別に集計される(self):
        agg, _ = gk.aggregate_rows(SEED_ROWS)
        v = agg["AR-26-004"]
        self.assertEqual(v["材料費"], 12000)
        self.assertEqual(v["外注費"], 220000)
        self.assertEqual(v["経費"], 8500 + 3300)  # 旅費交通費 + 区分空欄
        self.assertEqual(v["合計"], 12000 + 220000 + 8500 + 3300)
        self.assertEqual(v["件数"], 4)

    def test_合計は4費目の和になる(self):
        agg, _ = gk.aggregate_rows(SEED_ROWS)
        for v in agg.values():
            self.assertEqual(v["合計"], sum(v[k] for k in gk.GENKA_KEYS))

    def test_金額が読めない行は除外して警告する(self):
        rows = SEED_ROWS + [["RC-26-900", "AR-26-004", "", "2026-06-01", "x", "y",
                             "たくさん", "材料費", "直接原価", "", "", "", ""]]
        agg, warnings = gk.aggregate_rows(rows)
        self.assertEqual(agg["AR-26-004"]["件数"], 4)
        self.assertTrue(any("読めない" in w for w in warnings))

    def test_旧案件番号で案件キーに解決する(self):
        data = gk.ds.load_data()
        self.assertEqual(gk.resolve_anken_key(data, "AR-26-004"), "玉寿会-さくら床-26")
        self.assertIsNone(gk.resolve_anken_key(data, "AR-26-999"))

    def test_未突合の案件番号は警告に出る(self):
        r = gk.t_genka_aggregate({})
        self.assertGreaterEqual(r["未突合"], 1)
        self.assertTrue(any("AR-26-999" in w for w in r["警告"]))

    def test_年月で絞って集計できる(self):
        self.assertEqual(gk.t_genka_aggregate({"年月": "2026-04"})["対象行数"], 4)


class TestSync(Base):
    def test_dry_runではdata_jsonを変えない(self):
        before = TMP_DATA.read_bytes()
        r = gk.t_genka_sync_to_data_json({})
        self.assertIn("プレビュー", r["実行"])
        self.assertEqual(TMP_DATA.read_bytes(), before)

    def test_原価が0にリセットされる場合は中止する(self):
        """シートを部分的にしか読めていない事故を、書き戻し前に止める"""
        data = gk.ds.load_data()
        has_cost = [a for a in data["案件"] if (a.get("原価") or {}).get("合計", 0) > 0]
        if not has_cost:
            self.skipTest("原価が入った案件がない")
        before = TMP_DATA.read_bytes()
        with self.assertRaises(gk.ToolError) as cm:
            gk.t_genka_sync_to_data_json({"dry_run": False})   # 許可なしで実行
        self.assertIn("0にリセット", str(cm.exception))
        self.assertEqual(TMP_DATA.read_bytes(), before, "中止したのに書き込まれている")

    def test_ゼロ化を許可すれば書き戻せる(self):
        r = gk.t_genka_sync_to_data_json({"dry_run": False, "ゼロ化を許可": True})
        self.assertIn("完了", r["実行"])

    def test_dry_runはゼロ化を先に知らせる(self):
        r = gk.t_genka_sync_to_data_json({})
        data = gk.ds.load_data()
        if any((a.get("原価") or {}).get("合計", 0) > 0 for a in data["案件"]):
            self.assertTrue(r["ゼロ化される案件"])
            self.assertTrue(any("0にリセット" in w for w in r["警告"]))

    def test_本実行で原価が書き戻る(self):
        gk.t_genka_sync_to_data_json({"dry_run": False, "ゼロ化を許可": True})
        data = gk.ds.load_data()
        a = next(x for x in data["案件"] if x["案件キー"] == "玉寿会-さくら床-26")
        self.assertEqual(a["原価"]["材料費"], 12000)
        self.assertEqual(a["原価"]["外注費"], 220000)
        self.assertEqual(a["原価"]["合計"], 243800)
        self.assertEqual(a["原価"]["件数"], 4)
        self.assertTrue(a["原価"]["最終集計日"])

    def test_書き戻しでもdata_jsonの検証を通る(self):
        gk.t_genka_sync_to_data_json({"dry_run": False, "ゼロ化を許可": True})
        errors, _ = gk.ds.validate(gk.ds.load_data())
        self.assertEqual(errors, [])

    def test_書き戻しでバックアップが残る(self):
        gk.t_genka_sync_to_data_json({"dry_run": False, "ゼロ化を許可": True})
        backups = list(Path(os.environ["ARTRAYS_BACKUP_DIR"]).glob("data.json.*.bak"))
        self.assertEqual(len(backups), 1)

    def test_Sheetsに無い案件は原価0で埋める(self):
        gk.t_genka_sync_to_data_json({"dry_run": False, "ゼロ化を許可": True})
        for a in gk.ds.load_data()["案件"]:
            self.assertEqual(set(gk.GENKA_KEYS) - set(a["原価"]), set(),
                             f"{a['案件キー']} の原価に費目が欠けている")
            self.assertEqual(a["原価"]["合計"],
                             sum(a["原価"][k] for k in gk.GENKA_KEYS))


class TestDuplicates(Base):
    # 実際に起きた二重登録の再現：同じ取引だが店舗名・品目の表記が違う
    DUP_ROW = ["RC-26-007", "AR-26-004", "さくら苑", "2026-04-02", "コメリＨ＆Ｇ",
               "ビス、接着剤", "12000", "材料費", "直接原価", "カード", "AMEX明細",
               "", "2026-04-30"]

    def setUp(self):
        super().setUp()
        STUB.rows.append(list(self.DUP_ROW))

    def test_表記違いの二重登録を疑いとして検出する(self):
        r = gk.t_genka_find_duplicates({})
        self.assertEqual(r["完全重複"]["組数"], 0, "厳密キーでは拾えないはず")
        self.assertEqual(r["重複の疑い"]["組数"], 1)
        g = r["重複の疑い"]["明細"][0]
        self.assertEqual(sorted(g["RC"]), ["RC-26-001", "RC-26-007"])
        self.assertEqual(r["重複の疑い"]["余分な金額"], 12000)

    def test_完全重複も検出する(self):
        STUB.rows.append(list(SEED_ROWS[1]))
        STUB.rows[-1][0] = "RC-26-008"
        r = gk.t_genka_find_duplicates({})
        self.assertEqual(r["完全重複"]["組数"], 1)
        self.assertEqual(r["完全重複"]["余分な金額"], 220000)

    def test_追記時に表記違いの重複を警告する(self):
        row = self.row(案件番号="AR-26-004", 日付="2026-04-05",
                       金額="220000", **{"店舗名・業者名": "川原内装(株)"})
        r = gk.t_genka_append_rows({"rows": [row]})
        self.assertIn("⚠ 重複の疑い", r)
        self.assertEqual(r["⚠ 重複の疑い"]["件数"], 1)
        self.assertIn("RC-26-002",
                      r["⚠ 重複の疑い"]["明細"][0]["同じ案件・日付・金額の既存行"])

    def test_疑いがあっても弾かずに書ける(self):
        """判断は人がする。自動で落とすと正当な往復高速代などを失う"""
        row = self.row(案件番号="AR-26-004", 日付="2026-04-05",
                       金額="220000", **{"店舗名・業者名": "川原内装(株)"})
        r = gk.t_genka_append_rows({"rows": [row], "dry_run": False})
        self.assertEqual(r["追記行数"], 1)

    def test_無関係な行では警告しない(self):
        r = gk.t_genka_append_rows({"rows": [self.row()]})
        self.assertNotIn("⚠ 重複の疑い", r)


class TestValidate(Base):
    def test_問題を種類ごとに報告する(self):
        r = gk.t_genka_validate({})
        self.assertEqual(r["結果"], "要確認")
        self.assertIn("原価区分が不正", r["内訳"])
        self.assertIn("data.jsonに無い案件番号", r["内訳"])
        self.assertTrue(any("AR-26-999" in s for s in r["内訳"]["data.jsonに無い案件番号"]))

    def test_共通行は未突合としない(self):
        r = gk.t_genka_validate({})
        self.assertFalse(any("共通" in s for s in r["内訳"].get("data.jsonに無い案件番号", [])))


class TestProtocol(Base):
    def test_スキーマのプロパティ名はASCIIのみ(self):
        """日本語の引数名は Anthropic API に 400 で弾かれ、ツールが呼べなくなる"""
        pat = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")
        for t in gk.TOOLS:
            schema = t["inputSchema"]
            for k in (schema.get("properties") or {}):
                self.assertRegex(k, pat, f"{t['name']} のプロパティ名『{k}』がASCIIでない")
            for k in (schema.get("required") or []):
                self.assertRegex(k, pat, f"{t['name']} の required『{k}』がASCIIでない")

    def test_日本語の引数名でも受け付ける(self):
        self.assertEqual(gk.t_genka_read({"案件番号": "AR-26-004"})["該当"],
                         gk.t_genka_read({"anken_no": "AR-26-004"})["該当"])
        self.assertEqual(gk.t_genka_aggregate({"年月": "2026-04"})["対象行数"],
                         gk.t_genka_aggregate({"month": "2026-04"})["対象行数"])
        r = gk.t_genka_sync_to_data_json({"dry_run": False, "ゼロ化を許可": True})
        self.assertIn("完了", r["実行"])

    def test_tools_listが9件返る(self):
        resp = gk.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = resp["result"]["tools"]
        self.assertEqual(len(tools), 9)
        for t in tools:
            self.assertEqual(set(t), {"name", "description", "inputSchema"})

    def test_initializeが応答する(self):
        resp = gk.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                  "params": {"protocolVersion": "2025-06-18"}})
        self.assertEqual(resp["result"]["serverInfo"]["name"], "artrays-genka")

    def test_tools_callが動く(self):
        resp = gk.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                  "params": {"name": "genka_ping", "arguments": {}}})
        self.assertFalse(resp["result"]["isError"])

    def test_エラーはisErrorで返る(self):
        resp = gk.handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                  "params": {"name": "genka_import_tsv",
                                             "arguments": {"path": "/no/such.tsv"}}})
        self.assertTrue(resp["result"]["isError"])
        self.assertIn("見つかりません", resp["result"]["content"][0]["text"])


def tearDownModule():
    httpd.shutdown()
    shutil.rmtree(TMP_DIR, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
