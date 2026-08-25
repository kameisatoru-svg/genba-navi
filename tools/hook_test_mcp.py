#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PostToolUse フック: mcp/ 配下の Python を編集したら該当テストを走らせる。

mcp/ には artrays_data_server(35件) と artrays_genka_server(61件) の
自己テストが既にある。手で走らせないと回らない状態だったので、
編集を検知して自動で回す。編集したファイルに対応するスイートだけを選ぶ。

失敗したときだけ exit 2 で Claude に差し戻す。

Claude Code の設定: .claude/settings.json の PostToolUse
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# 編集されたファイル -> 走らせるテスト
SUITES = {
    "artrays_data_server.py": "test_artrays_data.py",
    "test_artrays_data.py": "test_artrays_data.py",
    "artrays_genka_server.py": "test_artrays_genka.py",
    "test_artrays_genka.py": "test_artrays_genka.py",
    "setup_genka.py": "test_artrays_genka.py",
}


def read_hook_input() -> dict:
    try:
        raw = sys.stdin.buffer.read()
        return json.loads(raw.decode("utf-8", errors="replace")) if raw else {}
    except Exception:
        return {}


def edited_paths(data: dict) -> list:
    ti = data.get("tool_input") or {}
    paths = []
    if ti.get("file_path"):
        paths.append(str(ti["file_path"]))
    for e in (ti.get("edits") or []):
        if isinstance(e, dict) and e.get("file_path"):
            paths.append(str(e["file_path"]))
    return paths


def main() -> int:
    data = read_hook_input()

    targets = []
    for p in edited_paths(data):
        norm = p.replace("\\", "/")
        if "/mcp/" not in norm and not norm.endswith(tuple(SUITES)):
            continue
        suite = SUITES.get(Path(norm).name)
        if suite and suite not in targets:
            targets.append(suite)

    if not targets:
        return 0

    failed = []
    for suite in targets:
        path = REPO / "mcp" / suite
        if not path.exists():
            continue
        try:
            proc = subprocess.run(
                [sys.executable, str(path)],
                capture_output=True, cwd=str(REPO), timeout=300,
                env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
            )
        except Exception as e:
            print("%s を実行できませんでした: %s" % (suite, e), file=sys.stderr)
            continue
        if proc.returncode != 0:
            tail = proc.stderr.decode("utf-8", errors="replace").strip().splitlines()
            failed.append((suite, tail[-25:]))

    if failed:
        out = []
        for suite, tail in failed:
            out.append("%s が失敗しました:" % suite)
            out += ["    " + t for t in tail]
            out.append("")
        out.append("mcp/ を変更したので自動でテストを回しました。先に直してください。")
        print("\n".join(out), file=sys.stderr)
        return 2

    print("mcp テスト通過: %s" % ", ".join(targets), file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print("hook_test_mcp 内部エラー: %s" % e, file=sys.stderr)
        sys.exit(0)
