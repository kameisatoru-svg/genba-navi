---
name: warn-print-light-gray
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: \.html$|\.css$
  - field: content
    operator: regex_match
    pattern: (?<![-\w])color\s*:\s*#(?:[7-9a-fA-F]{3}\b|[7-9a-fA-F]{2}[0-9a-fA-F]{4})
---

🖨️ **印刷で飛ぶ薄さの文字色を指定しています**

`#777` より薄いグレーを文字色に使っています。紙に出すと読めなくなります。

**ルール:**
- 顧客提出PDFは**全文字 `#000`（黒）**
- 画面用でもグレーは **`#666` が下限**
- 強調は色の濃淡ではなく**太字・サイズ**で付ける
- 白抜き文字も不可

画面専用で提出物に載らないUI部品（プレースホルダ等）であれば、この警告は無視して構いません。
