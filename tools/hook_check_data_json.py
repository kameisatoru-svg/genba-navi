#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PostToolUse フック: data.json が変化していたら即検証する。

現場ナビの data.json は過去に5回、末尾破損を起こしている。
書き込みの「入口」は hookify のルールで塞いだが、それをすり抜けた
経路（スキル・MCP・Bash）で壊れた場合、気づくのが翌日以降になっていた。
このフックは data.json が変化した直後に検証を走らせ、その場で気づけるようにする。

判定は mcp/artrays_data_server.py --check（約0.2秒）に委譲する。
エラーがあるときだけ exit 2 で Claude に差し戻す。警告は既知のものが
常時出ているため、ここでは件数だけ添える。

Claude Code の設定: .claude/settings.json の PostToolUse
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data.json"
STATE = REPO / ".claude" / ".data_json_state"



def emit(text: str) -> None:
    """stderr へUTF-8バイトで直接書く（cp932 で落ちないように）。"""
    try:
        sys.stderr.buffer.write((text + chr(10)).encode("utf-8", errors="replace"))
        sys.stderr.buffer.flush()
    except Exception:
        pass

def read_hook_input() -> dict:
    """stdin をUTF-8固定で読む（cp932 だと日本語が壊れるため）。"""
    try:
        raw = sys.stdin.buffer.read()
        return json.loads(raw.decode("utf-8", errors="replace")) if raw else {}
    except Exception:
        return {}


def fingeremit() -> str:
    st = DATA.stat()
    return "%d:%d" % (st.st_mtime_ns, st.st_size)


def main() -> int:
    read_hook_input()  # 入力は使わないが、読み切らないと相手が待つ

    if not DATA.exists():
        return 0

    # data.json が変わっていなければ何もしない
    try:
        fp = fingerprint()
        if STATE.exists() and STATE.read_text(encoding="utf-8").strip() == fp:
            return 0
    except OSError:
        fp = None

    try:
        proc = subprocess.run(
            [sys.executable, str(REPO / "mcp" / "artrays_data_server.py"), "--check"],
            capture_output=True, cwd=str(REPO), timeout=60,
            env={**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"},
        )
        report = json.loads(proc.stdout.decode("utf-8", errors="replace") or "{}")
    except Exception as e:
        print("data.json の検証を実行できませんでした: %s" % e)
        return 0  # 検証できないことを理由に作業を止めない

    errors = report.get("エラー") or []
    warns = report.get("警告") or []

    if errors:
        lines = ["data.json の検証でエラーが出ています（%d件）。" % len(errors), ""]
        lines += ["  - %s" % e for e in errors[:10]]
        if len(errors) > 10:
            lines.append("  ... 他 %d件" % (len(errors) - 10))
        lines += [
            "",
            "直前の書き込みで壊れた可能性があります。先に直してください。",
            "  退避コピー: mcp/_backups/ ",
            "  再検証:     python mcp/artrays_data_server.py --check",
        ]
        emit("\n".join(lines))
        return 2  # exit 2 = stderr を Claude に渡す

    # 正常。指紋を記録して次回は素通りさせる
    try:
        if fp:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(fp, encoding="utf-8")
    except OSError:
        pass

    if warns:
        emit("data.json OK（既知の警告 %d件）" % len(warns))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # フックが原因でセッションを止めない
        emit("hook_check_data_json 内部エラー: %s" % e)
        sys.exit(0)
