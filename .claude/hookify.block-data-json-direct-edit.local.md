---
name: block-data-json-direct-edit
enabled: true
event: file
action: block
conditions:
  - field: file_path
    operator: regex_match
    pattern: data\.json$
---

🛑 **data.json を直接編集しようとしています（ブロックしました）**

data.json は現場ナビ全体の真実の源泉です。直接 Edit/Write すると、
書き込み途中で落ちた場合に**末尾が破損して全案件が表示できなくなります**。

**正しい進め方:**
- 案件の進捗・イベント・TODO → `python genba_progress.py event|todo|sweep ...`
- 原価の反映 → `genka-aggregate` スキル
- 取引先の追加 → `meishi-to-data-json` / `invoice-checker-part2` スキル

**どうしても直接書く必要がある場合:**
必ず「dumps → 一時ファイル → `os.replace` → 再読込で検証」のアトミック書き込みで行うこと。
部分置換（str_replace 相当）は禁止です。
