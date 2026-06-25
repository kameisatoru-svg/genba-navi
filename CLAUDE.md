# 作業ルール（アート・レイズ 現場ナビPRO）

## 見積書・請求書の作成 ★重要

「**見積書を作って**」「**請求書を作って**」と言われたら、**`mitsumori_seikyu_preview.html`（見積・請求HTML）で開いて編集・生成できる形式** を作る。
具体的には **`preview_paste_<案件キー>.csv`**（`#META` + 簡易CSV形式）を作成すること。

- ❌ やらないこと：`見積書_雛形_アートレイズ.html` を直接埋めた静的HTMLを納品する／Googleスプレッドシート・PDFを「見積書」として作る。
- ⭕ 正しい成果物：`preview_paste_<案件キー>.csv`（リポジトリ直下。既存例：`preview_paste_ウインズ-大村建具-26.csv` 等）。利用者がこれを `mitsumori_seikyu_preview.html` の「CSVテキスト貼付」モーダルに貼り付けて読み込み・編集・PDF/HTML出力する。

### preview_paste CSV の書式
1. 先頭に前提・方針を `#` コメントで記載。
2. `#META:` 行（ドキュメントごと）：
   - `ankenKey` … 案件キー
   - `docType` … `mitsumori`（見積）/ `seikyu`（請求）
   - `docNumber` … お客様向け書類番号
   - `customerName` / `kojimei`（工事件名）/ `shisetsu`（施工場所）
   - `issueDate`（YYYY-MM-DD）/ `shiharaiDate`（請求の支払期日）/ `shokeihiRate`（諸経費%・通常10）/ `fileSuffix`（任意）
3. 続けて明細：`品名,数量,単位,単価,備考`（**単価**を入れる。金額＝数量×単価、諸経費(shokeihiRate%)・消費税10%はHTML側で自動計算）。
4. 見積と請求を1ファイルにまとめる場合は `# ---------- 見積書 用 ----------` / `# ---------- 請求書 用 ----------` で各 `#META`〜明細ブロックを分ける。
5. CSVの値にASCIIカンマ `,` を入れない（区切りと衝突するため、`／` や `:` を使う）。

### お客様向け書類番号の採番
`[ARM|ARS|ARO|ARK|ARN]-T[顧客番号]-YYMMDD-NN`
- **ARM=見積** / **ARS=請求** / **ARO=注文** / **ARK=完了** / **ARN=納品**

## data.json
- 取引先・案件マスターの**正**は `data.json`。破損履歴が多いため、編集は対象箇所のみのピンポイント置換で行い、保存後に必ず `python3 -c "import json;json.load(open('data.json'))"` で整合性検証する。

## 案件フォルダ（Google Drive）
- 構成：`AR-2026 > [顧客] > [案件キー]` 配下に `図面/議事/工程/写真/受領/通話記録/材料/書類/業者/経費/_素材`。
- 通話・対面録音の文字起こしは `通話記録`、議事録は `議事`、図面は `図面`、見積等の書類は `書類`。
