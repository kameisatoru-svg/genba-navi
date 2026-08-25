---
name: warn-customer-doc-internal-leak
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: (見_|請_|納_|完_|注_|提出|顧客).*\.html$
  - field: content
    operator: regex_match
    pattern: RC-2\d-\d{3}|T-0\d{2}|案件キー|原価|粗利|仕入|社内|申し送り
---

📄 **顧客提出物を編集しています — 社内情報の混入に注意**

このファイル名は顧客提出用の書類（見積 / 請求 / 納品 / 完了 / 注文）に見えます。

**載せてはいけないもの:**
- 案件キー（`大分BD-日出内装-26` 形式）
- 原価コード（`RC-26-NNN`）・取引先コード（`T-0NN`）
- 仕入単価・原価・粗利
- 社内向けの申し送り・メモ

**書き終えたら grep 検査を必ず走らせること。**
併せて、A4横比率・余白5mm・文字色は黒（グレーは #666 が下限）も確認してください。
