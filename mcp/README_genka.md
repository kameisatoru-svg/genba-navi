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
- **貼り直しによる二重計上** … 日付・店舗名・金額・品目が同じ行は自動でスキップする。
  加えて、案件番号・日付・金額が同じで**店舗名の表記だけが違う**行は「重複の疑い」として
  警告する（弾きはしない。往復の高速代など正当な同額2件を落とさないため）

> 実際に AMEX 2026-04 分で 14件 ¥118,974 の二重登録が起きている
> （RC-26-029〜042 と RC-26-043〜056）。店舗名の表記が違ったため厳密キーでは
> 素通りする事例で、これを機に「疑い」の警告を追加した。

---

## ツール一覧（9個）

> 引数名は英字。Anthropic API がツール定義のプロパティ名に
> `^[a-zA-Z0-9_.-]{1,64}$` を要求するため、日本語の引数名は使えない
> （使うと 400 エラーでツールが一切呼べなくなる）。
> ただしハンドラ側は日本語名で渡されても受け付ける。

| ツール | 用途 |
|---|---|
| `genka_ping` | 疎通確認。シート名・明細行数・最終RC・次のRCを返す |
| `genka_read` | 明細を読む（`anken_no` 案件番号 / `month` 年月 / `kamoku` 勘定科目 で絞込） |
| `genka_next_rc` | 次に採番されるRC番号（確認用） |
| `genka_append_rows` | 行を追記。RCは渡さない（シート側で排他採番） |
| `genka_import_tsv` | 貼付用TSVを取り込んで追記。**手貼りの置き換え** |
| `genka_aggregate` | 案件別に4費目集計（案件番号→案件キーは旧案件番号で解決） |
| `genka_sync_to_data_json` | 集計結果を data.json の『原価』へ書き戻す |
| `genka_find_duplicates` | 二重登録を探す（完全重複と、店舗名の表記違いによる『重複の疑い』） |
| `genka_validate` | RC重複・案件番号欠落・原価区分の不正・金額の読み取り不能を点検 |

### 書き込み系は既定でプレビュー

`genka_append_rows` / `genka_import_tsv` / `genka_sync_to_data_json` は
**既定が `dry_run: true`**。何が起きるかを見てから `dry_run: false` で実行する。

### ゼロ化ガード

`genka_sync_to_data_json` は、原価が入っている案件が0にリセットされる場合は
**書き戻しを中止する**。シートを部分的にしか読めていない事故（読み取り失敗・
年月で絞った集計を全体に適用）を、data.json を壊す前に止めるため。

意図通りなら `allow_zeroing: true` を付けて再実行する。

---

## セットアップ

### いちばん簡単な方法

```powershell
cd "C:\Users\user\artrays\claude ai\genba-navi"
python mcp\setup_genka.py
```

トークン生成・接続先の保存・疎通確認をこれが全部やる。
人がやるのは**ブラウザでの2操作だけ**（コードを貼る／デプロイする）で、
必要なタイミングで画面に指示が出る。

うまくいかないときや、手順を自分で追いたいときは以下を参照。

---

### 1. Apps Script を貼る

> **新しいスプレッドシートは作らない。** いま使っている原価管理台帳をそのまま使う。
> 貼り付けるコードは `SpreadsheetApp.getActive()` で「開いたスプレッドシート自身」を
> 操作する**コンテナバインド スクリプト**になるため、既存のシートの中から開く必要がある。

1. 原価管理スプレッドシートを開く
   （`1f_SXMlN07czsI7YsPMvv8bQhsWpU5Aiyg_HtM9L0LdM`）
   > ファイル名は「原価管理」だが、**タブ名は既定の `シート1` のまま**。
   > コード側の既定値もそれに合わせてある。
2. **拡張機能 → Apps Script**
3. エディタ上で **Ctrl+A → Delete** で中身を空にする
   > 既定で入っている `function myFunction() { }` も消すこと。
   > 残したままその中に貼ると `doGet` / `doPost` が入れ子になり、
   > ウェブアプリとして呼び出せない。
4. [`appsscript/genka_api.gs`](appsscript/genka_api.gs) の中身を全部貼る
5. 保存（Ctrl+S）

貼れたかの確認は、エディタ上部の**関数ドロップダウン**を見るのが早い。
`doGet` / `doPost` / `actionPing` などが並べばOK。`myFunction` しか出ないなら
まだ入れ子になっている。

既存の行は一切書き換えない。このスクリプトがするのは**最終行への追記だけ**で、
読み取りは表示値の取得のみ。列構成（A〜M）も現状のまま使う。

タブ名を変えた場合は、**スクリプトプロパティ `SHEET_NAME`** に新しい名前を入れる
（`API_TOKEN` と同じ画面。コードを直す必要も再デプロイも不要）。
設定していなければ `シート1` を探し、見つからなければエラーに**実際のタブ名一覧**が出る。

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
python mcp\setup_genka.py --check
```

（サーバー単体でも見られる: `python mcp\artrays_genka_server.py --ping`）

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
   （原価が0になる案件があると中止される。意図通りなら allow_zeroing=true）
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
| `シート『シート1』が見つかりません` | タブ名が違う。エラーに実際のタブ名一覧が出るので、その名前をスクリプトプロパティ `SHEET_NAME` に設定する（再デプロイ不要）。ここまで来ていればURL・トークン・コードは正しい |
| `接続できませんでした` | ネットワーク。3回まで自動リトライする（2秒→4秒） |
| コードを直したのに反映されない | Apps Script は**再デプロイが必要**。デプロイ → デプロイを管理 → 編集 → バージョン「新バージョン」→ デプロイ |

---

## テスト

```bash
python mcp/test_artrays_genka.py   # 51件
```

本物のスプレッドシートは使わない。Apps Script と同じ契約を実装したスタブを
localhost に立てて、採番・重複スキップ・4分類マッピング・TSV取り込み・
data.json 書き戻し・ゼロ化ガード・302リダイレクト追従までを検証する。
