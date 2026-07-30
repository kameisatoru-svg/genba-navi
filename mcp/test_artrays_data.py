#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""artrays_data_server の自己テスト（標準ライブラリのみ）

実データは触らない。テンポラリに data.json のコピーを作って検証する。

実行:  python mcp/test_artrays_data.py
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
SOURCE_DATA = REPO_ROOT / "data.json"

TMP_DIR = Path(tempfile.mkdtemp(prefix="artrays_data_test_"))
TMP_DATA = TMP_DIR / "data.json"
os.environ["ARTRAYS_DATA_JSON"] = str(TMP_DATA)
os.environ["ARTRAYS_BACKUP_DIR"] = str(TMP_DIR / "_backups")
os.environ["ARTRAYS_BACKUP_KEEP"] = "3"

# 最小構成のフォールバック（リポジトリの data.json が無い環境でもテストできる）
FALLBACK = {
    "最終更新": "2026-01-01 00:00",
    "命名ルール": {"案件キー": "[顧客]-[現場]-26"},
    "取引先マスター": [
        {"id": "T-001", "略称": "玉寿会", "正式名称": "社会福祉法人 玉寿会",
         "rel": ["顧客"], "type": ["公共施設"], "basic": {}, "contact": {},
         "memo": "", "注意点": "", "search": "t-001 玉寿会"},
    ],
    "案件": [
        {"案件キー": "玉寿会-さくら床-26", "顧客略": "玉寿会", "現場+工事": "さくら床",
         "正式工事名": "さくら苑 床工事", "施工場所": "熊本県玉名市",
         "ステータス": "入金済み", "元請フラグ": False, "元請名": "", "備考": "",
         "旧案件番号": "AR-26-004",
         "見積": [], "請求": [], "注文書": [], "契約書": [],
         "原価": {"労務費": 0, "材料費": 0, "外注費": 0, "経費": 0,
                  "合計": 0, "件数": 0, "最終集計日": ""}},
    ],
    "中止案件": [], "部材": [], "工具": [], "持込リスト": [],
    "単価マスタ": {"天井": {}, "壁": {}, "床": {}},
}


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "artrays_data_server", HERE / "artrays_data_server.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


srv = _load_module()


class Base(unittest.TestCase):
    def setUp(self):
        if SOURCE_DATA.exists():
            shutil.copy2(SOURCE_DATA, TMP_DATA)
        else:
            TMP_DATA.write_text(json.dumps(FALLBACK, ensure_ascii=False), encoding="utf-8")
        backups = Path(os.environ["ARTRAYS_BACKUP_DIR"])
        if backups.exists():
            shutil.rmtree(backups)
        self.data = srv.load_data()
        # テストで作る案件キーは実データと衝突しない名前にする
        self.new_key = "テスト社-自己テスト-26"

    def tearDown(self):
        try:
            srv.release_lock()
        except OSError:
            pass

    def any_anken_key(self):
        return self.data["案件"][0]["案件キー"]


class TestValidate(Base):
    def test_現状のdata_jsonは検証を通る(self):
        errors, _ = srv.validate(self.data)
        self.assertEqual(errors, [], f"実データに検証エラー: {errors}")

    def test_案件キー重複を検出する(self):
        d = copy.deepcopy(self.data)
        d["案件"].append(copy.deepcopy(d["案件"][0]))
        errors, _ = srv.validate(d)
        self.assertTrue(any("重複" in e for e in errors), errors)

    def test_T番号の形式違反を検出する(self):
        d = copy.deepcopy(self.data)
        d["取引先マスター"][0]["id"] = "T-1"
        errors, _ = srv.validate(d)
        self.assertTrue(any("T-NNN" in e for e in errors), errors)

    def test_金額が文字列なら検出する(self):
        d = copy.deepcopy(self.data)
        d["案件"][0].setdefault("見積", []).append(
            {"書類番号": "見_テスト", "発行日": "2026-01-01", "金額": "100,000"})
        errors, _ = srv.validate(d)
        self.assertTrue(any("金額が数値ではありません" in e for e in errors), errors)

    def test_トップレベルキー欠落を検出する(self):
        d = copy.deepcopy(self.data)
        del d["取引先マスター"]
        errors, _ = srv.validate(d)
        self.assertTrue(any("取引先マスター" in e for e in errors), errors)

    def test_原価合計の不一致は警告になる(self):
        d = copy.deepcopy(self.data)
        d["案件"][0]["原価"] = {"労務費": 100, "材料費": 0, "外注費": 0, "経費": 0,
                                "合計": 999, "件数": 1, "最終集計日": "2026-01-01"}
        errors, warnings = srv.validate(d)
        self.assertEqual(errors, [])
        self.assertTrue(any("合計" in w for w in warnings), warnings)


class TestSafeWrite(Base):
    def test_検証エラーの内容は書き込まれない(self):
        broken = copy.deepcopy(self.data)
        broken["案件"].append(copy.deepcopy(broken["案件"][0]))
        before = TMP_DATA.read_bytes()
        with self.assertRaises(srv.ValidationError):
            srv.save_data(broken, "test")
        self.assertEqual(TMP_DATA.read_bytes(), before, "検証NGなのにファイルが変わっている")

    def test_書き込みでバックアップが残り最終更新が進む(self):
        srv.t_patch_anken({"key": self.any_anken_key(), "fields": {"備考": "自己テスト"}})
        backups = list(Path(os.environ["ARTRAYS_BACKUP_DIR"]).glob("data.json.*.bak"))
        self.assertEqual(len(backups), 1)
        after = srv.load_data()
        self.assertNotEqual(after["最終更新"], self.data["最終更新"])
        self.assertEqual(json.loads(backups[0].read_text(encoding="utf-8"))["最終更新"],
                         self.data["最終更新"], "バックアップは書き込み前の内容であるべき")

    def test_バックアップは上限で間引かれる(self):
        key = self.any_anken_key()
        for i in range(5):
            srv.t_patch_anken({"key": key, "fields": {"備考": f"回{i}"}})
        backups = list(Path(os.environ["ARTRAYS_BACKUP_DIR"]).glob("data.json.*.bak"))
        self.assertLessEqual(len(backups), 3)

    def test_書き込み後もJSONとして読める(self):
        srv.t_patch_anken({"key": self.any_anken_key(), "fields": {"備考": "整合性確認"}})
        json.loads(TMP_DATA.read_text(encoding="utf-8"))  # 例外が出なければOK


class TestLookup(Base):
    def test_旧案件番号で解決できる(self):
        target = next((a for a in self.data["案件"] if a.get("旧案件番号")), None)
        if target is None:
            self.skipTest("旧案件番号を持つ案件がない")
        found, _ = srv.find_anken(self.data, target["旧案件番号"])
        self.assertEqual(found["案件キー"], target["案件キー"])

    def test_存在しないキーはエラーになる(self):
        with self.assertRaises(srv.ToolError):
            srv.require_anken(self.data, "存在しない案件キー_zzz")

    def test_取引先はT番号でも略称でも引ける(self):
        t = self.data["取引先マスター"][0]
        self.assertEqual(srv.t_get_torihikisaki({"key": t["id"]})["id"], t["id"])
        self.assertEqual(srv.t_get_torihikisaki({"key": t["略称"]})["id"], t["id"])

    def test_search_ankenは要約行を返す(self):
        res = srv.t_search_anken({"limit": 5})
        self.assertIn("件数", res)
        if res["案件"]:
            self.assertIn("原価合計", res["案件"][0])
            self.assertNotIn("見積", res["案件"][0], "検索結果に書類配列を含めない")

    def test_overviewが集計を返す(self):
        res = srv.t_data_overview({})
        self.assertEqual(res["件数"]["案件"], len(self.data["案件"]))
        self.assertIn("未入金", res)


class TestMutations(Base):
    def test_案件の新規作成と重複拒否(self):
        srv.t_create_anken({"案件キー": self.new_key, "正式工事名": "自己テスト工事"})
        after = srv.load_data()
        created = next(a for a in after["案件"] if a["案件キー"] == self.new_key)
        self.assertEqual(created["ステータス"], "相談")
        self.assertEqual(created["原価"]["合計"], 0)
        with self.assertRaises(srv.ToolError):
            srv.t_create_anken({"案件キー": self.new_key})

    def test_patchは許可外フィールドを拒否する(self):
        with self.assertRaises(srv.ToolError):
            srv.t_patch_anken({"key": self.any_anken_key(), "fields": {"見積": []}})

    def test_書類の追加と書類番号の重複拒否(self):
        key = self.any_anken_key()
        rec = {"書類番号": "見_自己テスト_001", "発行日": "2026-07-30", "金額": 123456}
        srv.t_append_document({"key": key, "種別": "見積", "record": rec})
        after = srv.load_data()
        a = next(x for x in after["案件"] if x["案件キー"] == key)
        self.assertTrue(any(d["書類番号"] == "見_自己テスト_001" for d in a["見積"]))
        with self.assertRaises(srv.ToolError):
            srv.t_append_document({"key": key, "種別": "見積", "record": rec})

    def test_書類の更新で入金を反映できる(self):
        key = self.any_anken_key()
        srv.t_append_document({"key": key, "種別": "請求", "record": {
            "書類番号": "請_自己テスト_001", "発行日": "2026-07-30",
            "金額": 100000, "入金状況": "minyukin"}})
        srv.t_update_document({"key": key, "種別": "請求", "書類番号": "請_自己テスト_001",
                               "fields": {"入金状況": "nyukin", "入金日": "2026-08-31"}})
        after = srv.load_data()
        a = next(x for x in after["案件"] if x["案件キー"] == key)
        d = next(x for x in a["請求"] if x["書類番号"] == "請_自己テスト_001")
        self.assertEqual(d["入金状況"], "nyukin")
        self.assertEqual(d["入金日"], "2026-08-31")

    def test_存在しない書類番号の更新はエラー(self):
        with self.assertRaises(srv.ToolError):
            srv.t_update_document({"key": self.any_anken_key(), "種別": "請求",
                                   "書類番号": "請_無い_999", "fields": {"金額": 1}})

    def test_set_genkaは合計を自分で計算する(self):
        key = self.any_anken_key()
        res = srv.t_set_genka({"key": key, "労務費": 100, "材料費": 200,
                               "外注費": 300, "経費": 400, "件数": 4})
        self.assertEqual(res["変更後"]["合計"], 1000)
        after = srv.load_data()
        a = next(x for x in after["案件"] if x["案件キー"] == key)
        self.assertEqual(a["原価"]["合計"], 1000)

    def test_set_genkaは数値以外を拒否する(self):
        with self.assertRaises(srv.ToolError):
            srv.t_set_genka({"key": self.any_anken_key(), "材料費": "12,000"})

    def test_取引先の新規登録はT番号を自動採番する(self):
        expected = srv.next_torihikisaki_id(self.data)
        res = srv.t_upsert_torihikisaki({
            "略称": "自己テスト商店", "正式名称": "株式会社 自己テスト商店",
            "rel": ["業者"], "type": ["内装"], "contact": {"tel": "0977-00-0000"}})
        self.assertEqual(res["操作"], "新規登録")
        self.assertEqual(res["取引先"]["id"], expected)
        self.assertTrue(res["取引先"]["search"], "search が自動生成されていない")

    def test_同じ略称の再登録は更新になる(self):
        srv.t_upsert_torihikisaki({"略称": "自己テスト商店", "rel": ["業者"]})
        before = len(srv.load_data()["取引先マスター"])
        res = srv.t_upsert_torihikisaki({"略称": "自己テスト商店", "memo": "追記"})
        self.assertEqual(res["操作"], "更新")
        self.assertEqual(len(srv.load_data()["取引先マスター"]), before)
        self.assertEqual(res["取引先"]["memo"], "追記")


class TestProtocol(Base):
    def test_initializeがツール能力を返す(self):
        resp = srv.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                   "params": {"protocolVersion": "2025-06-18"}})
        self.assertEqual(resp["result"]["protocolVersion"], "2025-06-18")
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_未知のプロトコル版は既定版で応答する(self):
        resp = srv.handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                   "params": {"protocolVersion": "1999-01-01"}})
        self.assertEqual(resp["result"]["protocolVersion"], srv.DEFAULT_PROTOCOL)

    def test_通知にはレスポンスを返さない(self):
        self.assertIsNone(srv.handle_request({"jsonrpc": "2.0",
                                              "method": "notifications/initialized"}))

    def test_tools_listが全ツールを返す(self):
        resp = srv.handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tools = resp["result"]["tools"]
        self.assertEqual(len(tools), len(srv.TOOLS))
        for t in tools:
            self.assertEqual(set(t), {"name", "description", "inputSchema"})
            self.assertEqual(t["inputSchema"]["type"], "object")

    def test_tools_callがJSONテキストを返す(self):
        resp = srv.handle_request({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                   "params": {"name": "data_overview", "arguments": {}}})
        self.assertFalse(resp["result"]["isError"])
        json.loads(resp["result"]["content"][0]["text"])

    def test_ツールのエラーは例外ではなくisErrorで返る(self):
        resp = srv.handle_request({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                                   "params": {"name": "get_anken",
                                              "arguments": {"key": "存在しない_zzz"}}})
        self.assertTrue(resp["result"]["isError"])
        self.assertIn("該当する案件がありません", resp["result"]["content"][0]["text"])

    def test_未知メソッドはJSONRPCエラー(self):
        resp = srv.handle_request({"jsonrpc": "2.0", "id": 5, "method": "no/such"})
        self.assertEqual(resp["error"]["code"], -32601)


def tearDownModule():
    shutil.rmtree(TMP_DIR, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
