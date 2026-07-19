# -*- coding: utf-8 -*-
"""
extract_tanka.py が出した teian_tanka.json を、かめさんの採否に従って

  (a) jisseki_tanka.json  … 実績単価の正本（全候補を必ず記録）
  (b) 単価マスター_アートレイズ.html … 採用したものだけ反映

へ書き込む。書き込みはバックアップ＋一時ファイル＋os.replace＋再検証のアトミック手順。

usage:
  python apply_tanka.py --dry-run                 # 何が起きるか表示のみ
  python apply_tanka.py --record-only             # 実績記録だけ（マスターは触らない）
  python apply_tanka.py --all-rangeout            # レンジ外を全部マスター更新
  python apply_tanka.py --all-new                 # 未登録を全部マスター追加
  python apply_tanka.py --pick "ソフト巾木貼|m,巾木塗装|m"
  python apply_tanka.py --from-file saiyou.txt    # 1行1件 "名称|単位"
"""
import argparse
import datetime as dt
import io
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract_tanka import (NAVI, MASTER, JISSEKI, TEIAN, AR2026,   # noqa: E402
                           parse_master, norm, norm_unit, fmt_range)

BACKUP_DIR = os.path.join(NAVI, "_アーカイブ", "単価マスター_バックアップ")


def atomic_write(path, text):
    """data.json 破損の教訓：一時ファイル→os.replace→再読込検証で書く。"""
    tmp = path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    got = io.open(tmp, encoding="utf-8").read()
    if got != text:
        os.remove(tmp)
        raise SystemExit("書き込み検証に失敗（内容不一致）: " + path)
    os.replace(tmp, path)


def backup(path):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M")
    dst = os.path.join(BACKUP_DIR, "{}.{}.bak".format(
        os.path.basename(path), stamp))
    shutil.copy2(path, dst)
    return dst


def key_of(c):
    return "{}|{}".format(c["名称"], c["単位"])


def load_picks(args, teian):
    picks = set()
    for c in teian["候補"]:
        if args.all_rangeout and c["判定"] == "レンジ外":
            picks.add(key_of(c))
        if args.all_new and c["判定"] == "未登録":
            picks.add(key_of(c))
    if args.pick:
        picks |= {p.strip() for p in args.pick.split(",") if p.strip()}
    if args.from_file:
        for line in io.open(args.from_file, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#"):
                picks.add(line)
    return picks


# ------------------------------------------------------------ マスター書き換え

ROW_TMPL = ('          <tr><td>{name}</td><td class="unit">{unit}</td>'
            '<td class="price-range">{price}</td><td class="kubun">{kubun}</td>'
            '<td class="note">{note}</td></tr>\n')


def update_master(html, sections, picked, today):
    """picked（候補dictのlist）をマスターHTMLへ反映して新HTMLを返す。"""
    changed, added, skipped = [], [], []

    for c in picked:
        note_add = "実績{} {}".format(today[:7].replace("-", "/"), c["案件キー"])

        if c["判定"] == "レンジ外":
            # 既存行の単価セルを新レンジへ差し替える（行はマスター名称で特定）
            target = c.get("マスター名称")
            pat = re.compile(
                r'(<tr[^>]*><td>' + re.escape(target) +
                r'</td><td class="unit">[^<]*</td><td class="price-range">)'
                r'([^<]*)(</td>)')
            m = pat.search(html)
            if not m:
                skipped.append((c, "マスター行が見つからない: " + str(target)))
                continue
            html = pat.sub(lambda mm: mm.group(1) + c["新レンジ案"] + mm.group(3),
                           html, count=1)
            html = stamp_note(html, target, note_add)
            changed.append((c, m.group(2), c["新レンジ案"]))

        elif c["判定"] == "未登録":
            sec = next((s for s in sections if s["工種"] == c.get("工種")), None)
            if sec is None:
                skipped.append((c, "工種が未確定（要手動分類）"))
                continue
            row = ROW_TMPL.format(
                name=esc(c["名称"]), unit=esc(c["単位"]),
                price=c.get("新レンジ案") or fmt_range(c["実績単価"], c["実績単価"]),
                kubun=esc(c.get("区分") or "材工共"), note=esc(note_add))
            html = insert_row(html, sec["工種"], row)
            added.append(c)
        else:
            skipped.append((c, "判定が『{}』のため対象外".format(c["判定"])))

    return html, changed, added, skipped


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def stamp_note(html, target_name, note_add):
    """更新した行の備考末尾に実績スタンプを足す（重複時は差し替え）。"""
    pat = re.compile(
        r'(<tr[^>]*><td>' + re.escape(target_name) +
        r'</td>.*?<td class="note">)(.*?)(</td>)', re.S)

    def rep(m):
        note = re.sub(r"\s*／?\s*実績\d{4}/\d{2}[^<]*", "", m.group(2)).strip()
        note = "" if note in ("—", "-") else note
        joined = (note + " ／ " + note_add) if note else note_add
        return m.group(1) + joined + m.group(3)

    return pat.sub(rep, html, count=1)


def insert_row(html, kousyu_title, row_html):
    """指定工種セクションの </tbody> 直前へ1行挿入する。"""
    i = html.find('<span class="section-title-text">' + kousyu_title)
    if i < 0:
        # タイトルに ※外注 等が付くケースは前方一致で拾う
        m = re.search(r'<span class="section-title-text">' +
                      re.escape(kousyu_title.split("｜")[0]) + r'[^<]*</span>', html)
        if not m:
            raise SystemExit("工種セクションが見つかりません: " + kousyu_title)
        i = m.start()
    j = html.find("</tbody>", i)
    if j < 0:
        raise SystemExit("tbody が見つかりません: " + kousyu_title)
    return html[:j] + row_html + "        " + html[j:]


# ------------------------------------------------------------ 実績JSON記録

def record_jisseki(teian, today):
    data = {"最終更新": today, "項目": {}, "処理済み": {}}
    if os.path.exists(JISSEKI):
        data.update(json.load(io.open(JISSEKI, encoding="utf-8")))
    data["最終更新"] = today
    items = data.setdefault("項目", {})
    for c in teian["候補"]:
        k = key_of(c)
        rec = items.setdefault(k, {"名称": c["名称"], "単位": c["単位"], "履歴": []})
        seen = {(h["単価"], h["出典"]) for h in rec["履歴"]}
        for src in c["出典"]:
            pair = (c["実績単価"], src)
            if pair not in seen:
                rec["履歴"].append({"単価": c["実績単価"], "案件キー": c["案件キー"],
                                    "発行日": c["発行日"], "出典": src})
                seen.add(pair)
        rec["最新単価"] = c["実績単価"]
        rec["最新日付"] = c["発行日"]
        rec["最終判定"] = c["判定"]
    done = data.setdefault("処理済み", {})
    for f in teian["対象ファイル"]:
        done[f["出典"]] = {"sha1": f["sha1"], "反映日": today, "行数": f["行数"]}
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--record-only", action="store_true")
    ap.add_argument("--all-rangeout", action="store_true")
    ap.add_argument("--all-new", action="store_true")
    ap.add_argument("--pick")
    ap.add_argument("--from-file")
    args = ap.parse_args()

    if not os.path.exists(TEIAN):
        raise SystemExit("teian_tanka.json がありません。先に extract_tanka.py を実行してください。")
    teian = json.load(io.open(TEIAN, encoding="utf-8"))
    today = dt.date.today().isoformat()

    html, sections = parse_master(MASTER)
    picks = set() if args.record_only else load_picks(args, teian)
    picked = [c for c in teian["候補"] if key_of(c) in picks]
    missing = picks - {key_of(c) for c in teian["候補"]}

    new_html, changed, added, skipped = update_master(html, sections, picked, today)
    jisseki = record_jisseki(teian, today)

    print("■ マスター更新: 単価差し替え {} 件 / 新規追加 {} 件 / 見送り {} 件".format(
        len(changed), len(added), len(skipped)))
    for c, old, new in changed:
        print("   更新  {} [{}]  {} → {}".format(c["名称"], c["単位"], old, new))
    for c in added:
        print("   追加  {}｜{} [{}] {}".format(
            c["工種"], c["名称"], c["単位"], c.get("新レンジ案")))
    for c, why in skipped:
        print("   見送り {} … {}".format(c["名称"], why))
    for k in sorted(missing):
        print("   ⚠ 指定が候補に無い: " + k)
    print("■ 実績記録: 項目 {} 種 / 処理済みファイル {} 件".format(
        len(jisseki["項目"]), len(jisseki["処理済み"])))

    if args.dry_run:
        print("（--dry-run のため書き込みなし）")
        return

    if changed or added:
        b = backup(MASTER)
        atomic_write(MASTER, new_html)
        _, secs2 = parse_master(MASTER)
        n_before = sum(len(s["行"]) for s in sections)
        n_after = sum(len(s["行"]) for s in secs2)
        if n_after != n_before + len(added):
            raise SystemExit(
                "検証失敗：行数 {}→{}（期待 {}）。{} から戻してください".format(
                    n_before, n_after, n_before + len(added), b))
        print("マスター更新完了（バックアップ: {}）行数 {}→{}".format(
            os.path.relpath(b, NAVI), n_before, n_after))

    atomic_write(JISSEKI, json.dumps(jisseki, ensure_ascii=False, indent=1) + "\n")
    json.load(io.open(JISSEKI, encoding="utf-8"))     # 再パース検証
    print("jisseki_tanka.json 更新完了")


if __name__ == "__main__":
    main()
