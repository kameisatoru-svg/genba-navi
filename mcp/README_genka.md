# artrays-genka MCP サーバー

原価管理Sheets を読み書きする MCP サーバー。
Python 標準ライブラリのみ（pip install 不要）。

---

## なぜ作ったか

月末経理の流れは、いまここで人が挟まっている。

```
ec-invoice-download → amex-categorizer → amex-categorizer-post
                                              ↓ TSVを出力
                                    【かめさんが手でSheetsに貼る】 ← ここ
                                              ↓「貼付完了」と言う
                                         genka-aggregate
```

`genka-aggregate` のスキル説明にも「Sheets書き込みコネクタが無いため本体台帳への
行追記は手作業のまま」と書いてある。このサーバーはそこを埋める。

```
genka_import_tsv → genka_aggregate → genka_sync_to_data_json
（貼付を代行）      （4費目集計）      （data.json へ書き戻し）
```

あわせて、手作業では防げなかった2つを構造的に潰す。

- **RC-26-NNN の二重採番** … 採番をスプレッドシート側で `LockService` 排他にした
- **貼り直しによる二重計上** … 日付・店舗名・金額・品目が同じ行は自動でスキップする

---

## ツール一覧（8個）

| ツール | 用途 |
|---|---|
| `genka_ping` | 疎通確認。シート名・明細行数・最終RC・次のRCを返す |
| `genka_read` | 明細を読む（案件番号・年月・勘定科目で絞込） |
| `genka_next_rc` | 次に採番されるRC番号（確認用） |
| `genka_append_rows` | 行を追記。RCは渡さない（シート側で排他採番） |
| `genka_import_tsv` | 貼付用TSVを取り込んで追記。**手貼りの置き換え** |
| `genka_aggregate` | 案件別に4費目集計（案件番号→案件キーは旧案件番号で解決） |
| `genka_sync_to_data_json` | 集計結果を data.json の『原価』へ書き戻す |
| `genka_validate` | RC重複・案件番号欠落・原価区分の不正・金額の読み取り不能を点検 |

### 書き込み系は既定でプレビュー

`genka_append_rows` / `genka_import_tsv` / `genka_sync_to_data_json` は
**既定が `dry_run: true`**。何が起きるかを見てから `dry_run: false` で実行する。

### ゼロ化ガード

`genka_sync_to_data_json` は、原価が入っている案件が0にリセットされる場合は
**書き戻しを中止する**。シートを部分的にしか読めていない事故（読み取り失敗・
年月で絞った集計を全体に適用）を、data.json を壊す前に止めるため。

意図通りなら `ゼロ化を許可: true` を付けて再実行する。

---

## セットアップ

### 1. Apps Script を貼る

1. 原価管理スプレッドシートを開く
2. **拡張機能 → Apps Script**
3. `コード.gs` の中身を消して、[`appsscript/genka_api.gs`](appsscript/genka_api.gs) を全部貼る
4. 保存

### 2. トークンを設定する

長いランダム文字列を用意する（PowerShell）:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Apps Script エディタで **プロジェクトの設定（歯車）→ スクリプト プロパティ → プロパティを追加**

| プロパティ | 値 |
|---|---|
| `API_TOKEN` | 上で作った文字列 |

### 3. ウェブアプリとしてデプロイ

**デプロイ → 新しいデプロイ → 種類の選択（歯車）→ ウェブアプリ**

| 項目 | 値 |
|---|---|
| 次のユーザーとして実行 | **自分** |
| アクセスできるユーザー | **全員** |

初回は Google の承認画面が出る。「詳細」→「（安全でないページ）に移動」で進む
（自分が書いたスクリプトなのでこの警告は出る）。

デプロイ後に出る **ウェブアプリURL**（`.../exec` で終わる）をコピーする。

> **アクセス範囲について**：OAuth なしで叩けるようにするため「全員」にする必要がある。
> URL を知っている人は誰でもリクエストを送れるので、**実際の防御は `API_TOKEN` だけ**。
> 必ず32文字以上のランダム文字列にして、URLとトークンを人に渡さないこと。
> 心配なら、Apps Script 側の `handle()` に IP 制限や利用時間帯の制限を足せる。

### 4. 接続先を書く

`mcp/.genka_config.json`（`.gitignore` 済み・Gitには入らない）:

```json
{
  "url": "https://script.google.com/macros/s/XXXXXXXX/exec",
  "token": "手順2で作った文字列"
}
```

環境変数 `ARTRAYS_GENKA_URL` / `ARTRAYS_GENKA_TOKEN` でも同じ。

### 5. 疎通確認

```powershell
python mcp\artrays_genka_server.py --ping
```

こう出れば成功:

```json
{ "接続": "OK", "スプレッドシート": "原価管理台帳", "シート": "原価管理",
  "明細行数": 312, "最終RC": "RC-26-312", "次のRC": "RC-26-313" }
```

### 6. MCP サーバーとして登録

```powershell
claude mcp add artrays-genka -- python "C:\Users\user\artrays\claude ai\genba-navi\mcp\artrays_genka_server.py"
```

---

## 月末経理の流れ（導入後）

```
1. genka_validate              いまのシートの状態を点検
2. genka_import_tsv            貼付用TSVを取り込む（まずプレビュー）
   → 採番結果と重複スキップを確認
3. genka_import_tsv dry_run=false   本実行
4. genka_aggregate             案件別4費目集計・警告を確認
5. genka_sync_to_data_json     差分プレビュー
6. genka_sync_to_data_json dry_run=false   data.json へ書き戻し
```

`data.json` への書き戻しは `artrays-data` の安全な書き込み機構
（検証 → `_backups/` へ退避 → 原子的差し替え）をそのまま通る。

---

## 困ったとき

| 症状 | 原因と対処 |
|---|---|
| `認証に失敗しました` | `.genka_config.json` の token と スクリプトプロパティ `API_TOKEN` が不一致 |
| `応答が JSON ではありません` | デプロイ設定が「アクセスできるユーザー＝全員」になっていない（ログイン画面のHTMLが返っている） |
| `HTTP 404` | URL が `/exec` で終わっていない。`/dev` はエディタ用なので使わない |
| `接続できませんでした` | ネットワーク。3回まで自動リトライする（2秒→4秒） |
| コードを直したのに反映されない | Apps Script は**再デプロイが必要**。デプロイ → デプロイを管理 → 編集 → バージョン「新バージョン」→ デプロイ |

---

## テスト

```bash
python mcp/test_artrays_genka.py   # 44件
```

本物のスプレッドシートは使わない。Apps Script と同じ契約を実装したスタブを
localhost に立てて、採番・重複スキップ・4分類マッピング・TSV取り込み・
data.json 書き戻し・ゼロ化ガード・302リダイレクト追従までを検証する。
