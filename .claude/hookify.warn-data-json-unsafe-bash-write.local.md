---
name: warn-data-json-unsafe-bash-write
enabled: true
event: bash
action: warn
conditions:
  - field: command
    operator: contains
    pattern: data.json
  - field: command
    operator: regex_match
    pattern: json\.dump|jq\s|Set-Content|Out-File|Add-Content|sed\s+-i|\.write\(
  - field: command
    operator: not_contains
    pattern: genba_progress.py
---

⚠️ **data.json をコマンド経由で書き換えようとしています**

このコマンドは data.json への**書き込み**を含んでいるように見えます。
過去に末尾破損の事故が起きている箇所です。

**確認事項:**
1. `jq` での直編集は**禁止**です（リダイレクトで元ファイルが空になる事故が起きます）
2. Python で書くなら必ずアトミック書き込み:
   `json.dumps` → 一時ファイルへ書く → `os.replace` → **書いた後もう一度 json.load して検証**
3. 退避バックアップの置き場はリポジトリ外（`C:\Users\user\artrays_backups\`）

進捗・イベント系の更新なら、まず `genba_progress.py` で済まないか検討してください。
