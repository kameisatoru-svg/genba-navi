#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""看板テンプレート（check_template.js）と data.json のズレを検査する。

現場ナビは「data.json の 案件.チェック が真実の源泉」で、
dashboard.html と workflow.html はどちらも check_template.js の
CHECK_TEMPLATE を見て描画する。両者がズレると:

  - テンプレートに無いステータスの案件 -> ワークフローが描けない
  - テンプレートに無い項目IDが data 側に残る -> 保存されているのに表示されない
  - data 側で一度も使われない項目 -> 定義したつもりで機能していない

このスクリプトは読み取り専用。何も書き換えない。

  python tools/kanban_check.py
"""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JS = REPO / "check_template.js"
DATA = REPO / "data.json"


def out(text: str = "") -> None:
    sys.stdout.buffer.write((text + chr(10)).encode("utf-8", errors="replace"))


def extract_literal(src: str, name: str) -> str:
    """const <name> = { ... } の中括弧の対応を取って literal を切り出す。"""
    m = re.search(r"const\s+" + re.escape(name) + r"\s*=\s*\{", src)
    if not m:
        raise ValueError(name + " の定義が見つかりません")
    start = src.index("{", m.start())
    depth = 0
    in_str = None
    i = start
    while i < len(src):
        c = src[i]
        if in_str:
            if c == "\\":
                i += 2
                continue
            if c == in_str:
                in_str = None
        elif c in "'\"":
            in_str = c
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
        i += 1
    raise ValueError(name + " の括弧が閉じていません")


def js_to_py(blob: str):
    """データだけのJSオブジェクトリテラルを JSON に寄せて読む。"""
    # 文字列の外側だけを対象にコメントを落とす
    cleaned = []
    in_str = None
    i = 0
    while i < len(blob):
        c = blob[i]
        if in_str:
            cleaned.append(c)
            if c == "\\":
                if i + 1 < len(blob):
                    cleaned.append(blob[i + 1])
                i += 2
                continue
            if c == in_str:
                in_str = None
            i += 1
            continue
        if c in "'\"":
            in_str = c
            cleaned.append(c)
            i += 1
            continue
        if blob.startswith("//", i):
            while i < len(blob) and blob[i] != chr(10):
                i += 1
            continue
        if blob.startswith("/*", i):
            i = blob.find("*/", i)
            i = len(blob) if i < 0 else i + 2
            continue
        cleaned.append(c)
        i += 1
    s = "".join(cleaned)

    # 'xxx' -> "xxx"（内部に " が無い前提。この定義では成立している）
    s = re.sub(r"'([^'\]*)'", lambda m: json.dumps(m.group(1), ensure_ascii=False), s)
    # 裸のキー -> "キー"
    s = re.sub(r"([{,]\s*)([A-Za-z_$][\w$]*)(\s*:)", r'\1"\2"\3', s)
    # 末尾カンマ
    s = re.sub(r",(\s*[}\]])", r"\1", s)
    return json.loads(s)


def main() -> int:
    src = io.open(JS, encoding="utf-8").read()
    tpl = js_to_py(extract_literal(src, "CHECK_TEMPLATE"))

    # CHECK_TEMPLATE['A'] = CHECK_TEMPLATE['B'] のエイリアスを反映
    aliases = re.findall(
        r"CHECK_TEMPLATE\[\s*['\"]([^'\"]+)['\"]\s*\]\s*=\s*"
        r"CHECK_TEMPLATE\[\s*['\"]([^'\"]+)['\"]\s*\]", src)
    for dst, srck in aliases:
        if srck in tpl:
            tpl[dst] = tpl[srck]

    # ステータス -> {stage.item} の集合
    keys_by_status = {}
    for status, body in tpl.items():
        ids = set()
        for st in (body.get("stages") or []):
            sid = st.get("id")
            for it in (st.get("items") or []):
                ids.add("%s.%s" % (sid, it.get("id")))
        keys_by_status[status] = ids
    all_template_keys = set().union(*keys_by_status.values()) if keys_by_status else set()

    data = json.load(io.open(DATA, encoding="utf-8"))
    ankens = data.get("案件") or []

    missing_status = {}
    orphan_keys = {}
    used_keys = set()
    no_check = 0

    for a in ankens:
        key = a.get("案件キー") or "(キー無し)"
        status = a.get("ステータス")
        chk = a.get("チェック")
        if not isinstance(chk, dict):
            no_check += 1
        else:
            used_keys |= set(chk)
        if status not in tpl:
            missing_status.setdefault(status, []).append(key)
            continue
        if isinstance(chk, dict):
            extra = set(chk) - keys_by_status[status]
            if extra:
                orphan_keys[key] = (status, sorted(extra))

    unused = sorted(all_template_keys - used_keys)

    out("=== 看板テンプレート整合チェック ===")
    out("案件 %d件 / テンプレート定義ステータス %d種（エイリアス %d件を含む）"
        % (len(ankens), len(tpl), len(aliases)))
    out()

    ng = False

    out("[1] テンプレートに定義が無いステータス")
    if missing_status:
        ng = True
        for st, keys in sorted(missing_status.items(), key=lambda x: -len(x[1])):
            out("  ✗ 「%s」 … %d件" % (st, len(keys)))
            for k in keys[:5]:
                out("        %s" % k)
            if len(keys) > 5:
                out("        ... 他 %d件" % (len(keys) - 5))
        out("    → この案件は workflow.html でチェックリストを描画できない")
    else:
        out("  なし")
    out()

    out("[2] ステータスに存在しない項目IDを持つ案件（保存されているが表示されない）")
    if orphan_keys:
        ng = True
        for k, (st, extra) in list(orphan_keys.items())[:15]:
            out("  ✗ %s（%s）: %s" % (k, st, ", ".join(extra[:6])))
        if len(orphan_keys) > 15:
            out("  ... 他 %d件" % (len(orphan_keys) - 15))
    else:
        out("  なし")
    out()

    out("[3] テンプレートにあるが一度も使われていない項目ID")
    if unused:
        out("  △ %d件（定義したが機能していない可能性）" % len(unused))
        for k in unused[:15]:
            out("        %s" % k)
        if len(unused) > 15:
            out("        ... 他 %d件" % (len(unused) - 15))
    else:
        out("  なし")
    out()

    out("[4] チェック未作成の案件: %d件" % no_check)
    out()
    out("判定: %s" % ("要対応（[1][2] を先に）" if ng else "整合している"))
    return 1 if ng else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        out("kanban_check エラー: %s" % e)
        sys.exit(2)
