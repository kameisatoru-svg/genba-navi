#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""artrays-genka のセットアップ補助（標準ライブラリのみ）

トークン生成・貼り付け用コードの表示・接続先の保存・疎通確認をまとめて行う。
ブラウザ操作（Apps Script を貼る／デプロイする）だけは人がやる必要がある。

対話で実行:
    python mcp/setup_genka.py

すでにURLとトークンがある場合:
    python mcp/setup_genka.py --url https://script.google.com/macros/s/XXX/exec --token abc123

いまの設定で疎通だけ見る:
    python mcp/setup_genka.py --check
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("ARTRAYS_GENKA_CONFIG") or (HERE / ".genka_config.json"))
GS_PATH = HERE / "appsscript" / "genka_api.gs"


def hr(title=""):
    print("\n" + "=" * 68)
    if title:
        print(title)
        print("=" * 68)


def load_existing():
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def save_config(url: str, token: str):
    CONFIG_PATH.write_text(
        json.dumps({"url": url, "token": token}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    try:
        os.chmod(CONFIG_PATH, 0o600)   # Windows では概ね無視される
    except OSError:
        pass
    print(f"\n✓ 接続先を保存しました: {CONFIG_PATH}")
    print("  （.gitignore 済みなので Git には入りません）")


def normalize_url(url: str) -> str:
    url = (url or "").strip().strip('"').strip("'")
    if not url:
        raise SystemExit("URL が空です。")
    if not url.startswith("https://"):
        raise SystemExit(f"URL が https:// で始まっていません: {url}")
    if url.endswith("/dev"):
        raise SystemExit(
            "そのURLは開発用（/dev）です。ウェブアプリのURL（/exec で終わるもの）を使ってください。\n"
            "デプロイ → デプロイを管理 → ウェブアプリのURL からコピーできます。")
    if not url.endswith("/exec"):
        print(f"⚠ URL が /exec で終わっていません: {url}")
        print("  ウェブアプリのURLか確認してください（このまま進めます）")
    return url


def do_check(url: str, token: str) -> int:
    os.environ["ARTRAYS_GENKA_URL"] = url
    os.environ["ARTRAYS_GENKA_TOKEN"] = token
    sys.path.insert(0, str(HERE))
    import artrays_genka_server as gk   # 設定後に読み込む

    print("\n疎通を確認しています…")
    try:
        res = gk.t_genka_ping({})
    except gk.ToolError as e:
        print("\n✗ 接続できませんでした\n")
        print(str(e))
        print("\n困ったときは mcp/README_genka.md の「困ったとき」を見てください。")
        return 1
    print("\n✓ 接続できました\n")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print("\n次の1行で Claude に登録すれば完了です:")
    print(f'  claude mcp add artrays-genka -- python "{HERE / "artrays_genka_server.py"}"')
    return 0


def interactive() -> int:
    existing = load_existing()

    hr("artrays-genka セットアップ")
    print("ブラウザでの操作は2つだけです（コードを貼る／デプロイする）。")
    print("それ以外はこのスクリプトが行います。")

    token = existing.get("token") or secrets.token_urlsafe(32)
    if existing.get("token"):
        print(f"\n既存のトークンを使います（{CONFIG_PATH.name} から読み込み）")
    else:
        print("\nトークンを生成しました。")

    hr("手順1  スプレッドシートに Apps Script を貼る")
    print("1. 原価管理スプレッドシートを開く")
    print("2. 上部メニュー  拡張機能 → Apps Script")
    print("3. 「コード.gs」の中身を全部消して、次のファイルの中身を貼り付ける")
    print(f"     {GS_PATH}")
    if GS_PATH.exists():
        print(f"     （{len(GS_PATH.read_text(encoding='utf-8').splitlines())} 行）")
    else:
        print("     ⚠ ファイルが見つかりません。git pull してください。")
    print("4. 保存（Ctrl+S）")

    hr("手順2  トークンを設定する")
    print("Apps Script エディタの左側  歯車（プロジェクトの設定）")
    print("  → 一番下「スクリプト プロパティ」→「スクリプト プロパティを追加」")
    print("\n  プロパティ:  API_TOKEN")
    print(f"  値       :  {token}")
    print("\n  ↑ この値をコピーして貼り付けてください")
    input("\n貼り付けて保存したら Enter を押してください… ")

    hr("手順3  ウェブアプリとしてデプロイする")
    print("右上「デプロイ」→「新しいデプロイ」")
    print("  種類の選択（歯車）→ ウェブアプリ")
    print("  次のユーザーとして実行  : 自分")
    print("  アクセスできるユーザー  : 全員")
    print("  →「デプロイ」")
    print("\n初回は承認画面が出ます。")
    print("  「詳細」→「(安全でないページ) に移動」→「許可」")
    print("\n完了すると『ウェブアプリ』のURLが出ます（/exec で終わるもの）。")

    default = existing.get("url", "")
    prompt = f"\nURL を貼り付けてください{f' [{default}]' if default else ''}: "
    url = input(prompt).strip() or default
    url = normalize_url(url)

    save_config(url, token)
    return do_check(url, token)


def main():
    ap = argparse.ArgumentParser(description="artrays-genka のセットアップ補助")
    ap.add_argument("--url", help="ウェブアプリのURL（/exec で終わるもの）")
    ap.add_argument("--token", help="API_TOKEN と同じ文字列")
    ap.add_argument("--check", action="store_true", help="保存済みの設定で疎通だけ確認する")
    ap.add_argument("--gen-token", action="store_true", help="トークンだけ生成して表示する")
    args = ap.parse_args()

    if args.gen_token:
        print(secrets.token_urlsafe(32))
        return 0

    if args.check:
        cfg = load_existing()
        url = os.environ.get("ARTRAYS_GENKA_URL") or cfg.get("url")
        token = os.environ.get("ARTRAYS_GENKA_TOKEN") or cfg.get("token")
        if not url or not token:
            print(f"接続先が未設定です。先に次を実行してください:\n  python {Path(__file__).name}")
            return 1
        return do_check(url, token)

    if args.url or args.token:
        cfg = load_existing()
        url = normalize_url(args.url or cfg.get("url", ""))
        token = args.token or cfg.get("token")
        if not token:
            print("--token を指定するか、対話モードで実行してください。")
            return 1
        save_config(url, token)
        return do_check(url, token)

    try:
        return interactive()
    except (KeyboardInterrupt, EOFError):
        print("\n中断しました。")
        return 130


if __name__ == "__main__":
    sys.exit(main())
