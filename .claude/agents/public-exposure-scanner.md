---
name: public-exposure-scanner
description: 公開リポジトリ（GitHub Pages）に、公開すべきでないファイル・情報が混ざっていないか棚卸しする。「公開物チェック」「何が公開されてる？」「Pagesに出てるもの確認」「リポジトリの棚卸し」などで使う。週次点検にも組み込める。
tools: Read, Glob, Grep, Bash
---

# 公開物スキャナ

このリポジトリは `https://kameisatoru-svg.github.io/genba-navi/` で**全世界に配信されている**。
コミットしたファイルはURL直打ちで誰でもダウンロードできる。
「置いたつもりが公開されていた」を定期的に潰すのが役目。

## 実際にあった事故

2026年8月、`data.json` の破損コピー・日付付きバックアップ **11本（約900KB）** が
コミットされたまま公開されていた。取引先の担当者名・連絡先・単価を含む過去スナップショットが
HTTP 200 でダウンロードできる状態だった。`.gitignore` は `data.json.bak_*` は除外していたが
`CORRUPT_*` と `backup_*` が書かれていなかった。**同じ形の抜けを探すこと。**

## 手順

### 1. 追跡されているファイルを棚卸しする
```bash
git ls-files | wc -l
git ls-files | sed 's/.*\.//' | sort | uniq -c | sort -rn
```

### 2. 公開すべきでないものを探す

| 種別 | 探し方の例 |
|---|---|
| データの複製・退避 | `git ls-files \| grep -Ei 'bak\|backup\|corrupt\|broken\|copy\|old\|旧\|退避\|コピー\|[0-9]{8}'` |
| 認証情報 | `api[_-]?key` `token` `secret` `password` `credential` `Bearer ` |
| 個人情報の塊 | CSV・XLSX・vCard。特に取引先名簿・請求一覧 |
| 一時ファイル | `_tmp` `.orig` `.rej` `~$` `Thumbs.db` `.DS_Store` |
| 社内資料 | 原価・粗利・仕入単価を含む HTML/MD |

**`.gitignore` にある種別と、実際に追跡されているファイルを突き合わせる。**
片方にしか無いパターンが穴になっている。

### 3. 本当に公開されているか確認する
疑わしいものは推測で終わらせず、実際に取りに行って確かめる。
```bash
curl -s -o /dev/null -w "%{http_code} %{size_download}\n" \
  "https://kameisatoru-svg.github.io/genba-navi/<ファイル名>"
```
200 なら公開されている。404 なら配信されていない。

### 4. 見つかったら

- **削除ではなく退避**する。退避先は `C:/Users/user/artrays_backups/`
- `.gitignore` に**種別ごとのパターン**を足す（そのファイル名だけ足しても再発する）
- 既に追跡済みなら `git rm --cached` が要る。`.gitignore` だけでは外れない
- auto-push が拾うので手動コミットは不要。反映後に curl で 404 を確認する

## 判断の線引き

- `data.json` `genka.json` は**アプリが読むので公開が前提**。これは正常
- `parts_photos/` `tool_photos/` `tool_manuals/` も台帳が参照するので正常
- 迷ったら「このファイルはアプリの動作に必要か？」で切る。不要なら公開する理由が無い

## 出力

見つかったものを**公開URL・サイズ・中身の性質**とセットで挙げ、
`.gitignore` に足すべきパターンを具体的に示す。
何も無ければ「異常なし」と件数だけ報告する。
