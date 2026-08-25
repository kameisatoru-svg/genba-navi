---
name: warn-type-number-ime
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: \.html$
  - field: content
    operator: regex_match
    pattern: type\s*=\s*["']number["']
---

⌨️ **`type="number"` を使おうとしています**

現場ナビのHTMLアプリでは `type="number"` は**禁止**です。
IMEが有効なままだと数字が入力できず、現場でスマホから打てなくなります。

**正しい書き方:**
```html
<input type="text" inputmode="numeric" ...>
```

小数を扱う欄なら `inputmode="decimal"` を使ってください。
