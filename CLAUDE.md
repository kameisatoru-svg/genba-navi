# CLAUDE.md — 現場ナビPRO 作業規約

アート・レイズ（大分県別府市・建設/内装リフォーム）の業務管理アプリ。
**ファイル構成と data.json のスキーマは [README.md](README.md) にある。ここは重複させず「守る作法」だけを書く。**

---

## 0. このリポジトリの性格（先に知っておくこと）

- **公開されている。** GitHub Pages（`https://kameisatoru-svg.github.io/genba-navi/`）で配信され、
  リポジトリに置いたファイルは**誰でもURL直打ちでダウンロードできる**。
  `data.json` は アプリが読むので公開が前提。それ以外の退避コピーを置いてはいけない。
- **ビルド工程は無い。** HTMLを直接編集すれば、そのまま本番。パッケージマネージャも無い。
- **auto-push が動いている。** ローカルで保存すると自動でコミット＆プッシュされる。
  **手動 `git commit` は不要**。`index.lock` の残留は自己回復するので触らない。
  → 「あとで消せばいい」は通用しない。置いた瞬間に公開される前提で作業する。

---

## 1. data.json（最重要・破損事故が5回起きている）

`data.json`（約580KB）は案件・取引先・原価・単価すべての**唯一の真実の源泉**。

### やってはいけない
- **Read/Write/Edit で直接編集しない**（hookify がブロックする）
- **`jq` での直編集は禁止**。`jq ... data.json > data.json` は元ファイルを空にする
- 部分置換（str_replace 相当）で書き換えない

### 正しい経路
| やりたいこと | 使うもの |
|---|---|
| 部分的な読み書き・検証 | `artrays-data` MCPサーバー（`mcp/artrays_data_server.py`） |
| 進捗・イベント・ToDo・書類登録・入金 | `python "C:/Users/user/artrays/AR-2026/_運用/genba_progress.py" <sub>` |
| 原価の集計反映 | `genka-aggregate` スキル |
| 取引先の追加 | `meishi-to-data-json` / `invoice-checker-part2` スキル |

`genba_progress.py` は**このリポジトリの外**（`AR-2026/_運用/`）にある。
サブコマンド: `events / event / status / check / move / todo / doc / nyukin / show / sweep`。
`--dry-run` で変更内容だけ確認できる。

### どうしても直接書く場合
必ずアトミック書き込み。`json.dumps` →一時ファイル→ `flush` → `fsync` → `os.replace` →
**書いた後もう一度 `json.load` して検証**。`artrays_data_server.py` の `save_data()` が手本。

### 検証と退避
```bash
python mcp/artrays_data_server.py --check
```
バックアップ・破損コピーは**リポジトリに置かない**。退避先は `C:/Users/user/artrays_backups/`。
（`.gitignore` で `data.json.CORRUPT*` `data.json.backup_*` `data.backup_*` `data.bak_*` を除外済み）

---

## 2. 看板とワークフロー

- **`data.json` の「案件.チェック」が真実の源泉**。看板側で持たない。
- `check_template.js` が `dashboard.html`（ステータス看板）と `workflow.html`（動的描画）の
  **共通定義**。ステージ/項目のidを変えると両方に波及する。
- `workflow.html` は **意図的に `common.css` を読んでいない**（独立させてある）。
  他の18ファイルは `common.css` v2 で統一済み。ここを揃えようとしないこと。

---

## 3. HTML / CSS の作法

- **`type="number"` は使わない。** IMEが有効だと数字を打てず、現場のスマホで入力不能になる。
  → `<input type="text" inputmode="numeric">`（小数は `inputmode="decimal"`）
  既存7ファイルに残存（`floor_plan` / `材料割付_app_` / `mitsumori_*` 等）。**新規では使わない。**
- **`sticky` の子を持つ親に `overflow:hidden` を使わない。** sticky が効かなくなる。角丸はセルに直接当てる。
- 数値入力欄は type を変えるだけでなく、`inputmode` を必ずセットで付ける。

---

## 4. 印刷・提出物

- **A4横（比率1.414）固定**。図面・割付図・仕上げ表。多ければA3横。
- PDF変換時は `@page { margin: 5mm; }` ＋ 縦横比維持。余白0だと外周枠が切れる。
- **文字色**: 顧客提出PDFは全文字 `#000`。画面用でもグレーは `#666` が下限。白抜き文字は不可。
  強調は色ではなく**太字・サイズ**で付ける。
- **文字サイズは px でなく mm 実寸で検算する。** 漢字3.5mm・注記4mm以上（JIS Z 8313）。

---

## 5. 顧客提出物と社内資料を分ける

顧客に出すもの（`見_` `請_` `納_` `完_` `注_`）に**載せてはいけないもの**:

- 案件キー（`大分BD-日出内装-26` 形式）
- 原価コード `RC-26-NNN` / 取引先コード `T-0NN`
- 原価・粗利・仕入単価
- 社内向けの申し送り・メモ

**生成後に grep 検査すること。** hookify が一次検知するが、最終確認は手で。

---

## 6. 見積の作法

- **単価は過去単価 ×1.2 が既定**（かめさんが単価を明示した場合はその値をそのまま使う）
- 機械・什器が搬入済みの改修は、干渉手間を**さらに上乗せ**（×1.2 とは別枠）
- **数量は小数第1位に四捨五入**
- **端数値引きは既定ON**（税抜を1000円単位に切下げ）。手入力・チェック解除で自動OFF
- ページは**連続流し込みが既定**（自動改頁しない）。「次ページへ続く」は継続時のみ出す
- 同名で複数版があるときは、**最終出力時刻のHTMLが正**

---

## 7. Python / MCP

- **標準ライブラリのみ**で書く（依存を増やさない）
- `mcp/*.py` を触ったら必ずテスト:
  ```bash
  PYTHONUTF8=1 python mcp/test_artrays_data.py
  ```
  35件・約1.4秒。`mcp/test_artrays_genka.py` も同様。
- Windows日本語環境なので、**`PYTHONUTF8=1` を付ける**か `encoding='utf-8'` を明示する。
  付け忘れると cp932 で読んで日本語が壊れる（エラーが出ずに壊れることがある）。

---

## 8. hookify（自動チェック）

`.claude/hookify.*.local.md` に5本のルールがある（data.json直接編集をブロック、
顧客提出物への社内情報混入・`type="number"`・薄いグレー文字を警告）。

- **hookify は cwd 直下の `.claude/` しか読まない。** 同じルールを
  `C:/Users/user/.claude/` にも置いてあるので、**編集したら両方に反映する**。
- ルールファイルは Git 管理外（`.gitignore` の `.claude/*.local.md`）。
- プラグイン更新でUTF-8パッチが消えたら `python C:/Users/user/.claude/hookify_utf8_patch.py`。
