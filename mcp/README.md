# artrays-data MCP サーバー

`data.json` を **部分的に・安全に** 読み書きするための MCP サーバー。
Python 標準ライブラリのみで動く（pip install 不要）。

---

## なぜ作ったか

| 現状 | 問題 |
|---|---|
| `data.json` が 380KB（案件69・取引先46・部材44・工具45） | 案件1件を確認するのに全文を読み込んでいた |
| 13個のスキルが SKILL.md 内 162 箇所で data.json を参照 | 全部が「全文読み → 全文書き戻し」 |
| リポジトリに `data.json.CORRUPT_*` / `.broken_*` が **21ファイル** | 書き戻しの失敗が繰り返し起きている |
| 原価の `合計`・取引先の `T-NNN` を都度手計算・手採番 | ズレ・重複が入り込む |

このサーバーは上の4つに直接対応する。

```
【従来】data.json 全文(380KB) を読む → 一部を書き換える → 全文を書き戻す
【以後】get_anken("AR-26-004", sections=["請求"]) → 必要な数百バイトだけ
        update_document(...)                     → 検証 → バックアップ → 原子的書き込み
```

---

## 安全機構

書き込みは毎回この順で行われる。途中で止まっても `data.json` は壊れない。

1. **検証** — 案件キー重複・T番号の形式・金額の型・トップレベルキーの欠落などを確認
2. **既存エラーの除外** — 書き込み前から在った不整合はブロック理由にしない
   （直さないと何も更新できない、という状態を作らないため。警告としては必ず報告する）
3. **バックアップ** — 書き込み **直前の内容** を `_backups/data.json.<日時>.<理由>.bak` に退避（既定30世代・古いものは自動削除）
4. **原子的書き込み** — 一時ファイルへ書く → `fsync` → `os.replace` で差し替え。
   書き込み途中でプロセスが落ちても、`data.json` は「前の内容」か「新しい内容」のどちらかで、中途半端な状態にならない
5. **ロック** — 同時書き込みを排他（60秒放置されたロックは自動解放）

`最終更新` は書き込みのたびにサーバー側で更新するので、更新忘れが起きない。

---

## ツール一覧（14個）

### 参照

| ツール | 用途 |
|---|---|
| `data_overview` | 最終更新・各件数・ステータス内訳・未入金合計。まず全体を掴む |
| `get_anken` | 案件を1件取得。`key` は **案件キー / 旧案件番号(AR-26-xxx) / 部分一致** のどれでも解決。`sections` で必要な配列だけに絞れる |
| `search_anken` | 顧客・ステータス・キーワードで検索。要約行（請求合計・原価合計付き）で返す |
| `list_mishuukin` | 未入金の請求を支払期限順に一覧 |
| `search_torihikisaki` | 取引先検索（略称・正式名称・search・memo が対象、`rel` で絞込） |
| `get_torihikisaki` | 取引先を1件取得（T番号 / 略称 / 正式名称の一部） |
| `validate_data` | 整合性チェック（エラー・警告の一覧） |
| `list_backups` | `_backups/` の新しい順一覧 |

### 更新

| ツール | 用途 |
|---|---|
| `create_anken` | 案件を新規作成（書類配列・原価0の雛形付き／キー重複は拒否） |
| `patch_anken` | ステータス・備考などスカラー項目の部分更新（書類・原価は対象外） |
| `append_document` | 見積 / 請求 / 注文書 / 契約書 / 完了書 / 納品書 を追加（書類番号の重複は拒否） |
| `update_document` | 既存書類の部分更新。入金反映（`入金状況` / `入金日`）もこれ |
| `set_genka` | 原価4費目を設定。**`合計` はサーバーが計算する** |
| `upsert_torihikisaki` | 取引先の登録・更新。**新規の T番号は自動採番**（重複しない） |

エラーは例外ではなく `isError: true` のテキストで返るので、
「複数該当します／候補はこれです」といった案内をそのまま読んで次の手が打てる。

---

## セットアップ

### Claude Code（CLI）

```powershell
claude mcp add artrays-data -- python "C:\Users\user\artrays\claude ai\genba-navi\mcp\artrays_data_server.py"
```

### Claude Desktop

`claude_desktop_config.json` に追記：

```json
{
  "mcpServers": {
    "artrays-data": {
      "command": "python",
      "args": ["C:\\Users\\user\\artrays\\claude ai\\genba-navi\\mcp\\artrays_data_server.py"]
    }
  }
}
```

### 環境変数（任意）

| 変数 | 既定 | 用途 |
|---|---|---|
| `ARTRAYS_DATA_JSON` | リポジトリ直下の `data.json` | 別の場所の data.json を使う |
| `ARTRAYS_BACKUP_DIR` | data.json と同じ場所の `_backups/` | バックアップ先 |
| `ARTRAYS_BACKUP_KEEP` | `30` | 残す世代数 |

---

## コマンドラインからも使える

```bash
python mcp/artrays_data_server.py --check    # data.json を検証（OK=0 / NG=1 で終了）
python mcp/artrays_data_server.py --tools    # ツール一覧
python mcp/test_artrays_data.py              # 自己テスト（31件・実データは触らない）
```

`--check` は `data_json_doctor.bat` の「壊れていないか」判定を、
JSON として読めるかだけでなく **中身の整合性まで**広げたもの。

---

## スキル側の移行

以下のスキルが data.json を直接読み書きしている。順次このサーバー経由に置き換えると効果が大きい。

| スキル | 置き換え先 |
|---|---|
| `genka-aggregate` | 丸ごと `artrays-genka` の `genka_aggregate` → `genka_sync_to_data_json` に置換（[README_genka.md](README_genka.md)） |
| `amex-categorizer-post` | TSVの手貼り → `genka_import_tsv`（RC採番・重複検知つき） |
| `receipt-processor` | 同上 |
| `meishi-to-data-json` | 取引先の新規登録 → `upsert_torihikisaki`（T番号の採番が自動） |
| `invoice-checker-part2` | 未登録業者の追加 → `upsert_torihikisaki` |
| `receipt-processor` | 案件名の解決 → `search_anken` / `get_anken`（全文読み込み不要） |
| `anken-checklist` / `anken-summary` | 案件の参照 → `get_anken` の `sections` 指定 |
| `mitsumori-seikyu-create` | 発行した書類の記録 → `append_document` |
| `ar2026-daily-update-check` | 整合性チェック → `validate_data` |

移行の要点は **「data.json を Read/Write で直接触らない」** の一点。
これを守るかぎり、壊れた場合でも `_backups/` に直前の内容が必ず残る。

---

## バックアップの扱い

`_backups/` は `.gitignore` 済み（Git には入らない）。
リポジトリ直下に溜まっている `data.json.CORRUPT_*` / `.broken_*` / `.bak_*` は
このサーバーの導入後は増えないため、様子を見てから整理してよい。

復旧が必要になったら：

```bash
python mcp/artrays_data_server.py --check                  # 現状を確認
ls _backups/                                                # または list_backups ツール
copy _backups\data.json.20260730_101500.patch_anken_xxx.bak data.json
```
