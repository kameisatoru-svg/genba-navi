# -*- coding: utf-8 -*-
"""原価管理Sheets(CSV/base64) → genka.json 変換。
genka-aggregate スキルと同じ4分類マッピングで集計しつつ、案件別の明細行も保持する。
data.json の 旧案件番号 で案件キーへ突き合わせる。"""
import base64, csv, io, json, collections

with open('_genka_b64.txt', encoding='utf-8') as f:
    raw = base64.b64decode(f.read()).decode('utf-8')

lines = raw.splitlines()
# 1行目はヘッダ（タブ区切り）。データ行はカンマ区切り。
data_lines = lines[1:]
reader = csv.reader(io.StringIO('\n'.join(data_lines)))

# data.json で 旧案件番号→案件キー の対応表を作る
data = json.load(open('data.json', encoding='utf-8'))
ankens = data.get('案件', [])
old2key = {}
key_set = set()
for a in ankens:
    k = a.get('案件キー') or a.get('案件番号')
    if k:
        key_set.add(k)
    old = a.get('旧案件番号')
    if old:
        old2key[old] = k

def classify(kanjo, kubun):
    """I列(原価区分)・H列(勘定科目) → 4分類キー"""
    if kubun == '一般経費':
        return '経費'
    if kubun == '直接原価':
        if kanjo in ('材料費', '外注費', '労務費'):
            return kanjo
        return '経費'
    return '経費'  # 区分空・異常値は暫定的に経費（取りこぼし防止）

groups = collections.OrderedDict()  # 表示キー → entry
warnings = []

for row in reader:
    if not row or not row[0].strip():
        continue
    # A〜M（13列）。足りない場合は空で補完
    row = (row + [''] * 13)[:13]
    rid, ban, genba, hiduke, mise, hinmoku, kingaku_s, kanjo, kubun, shiharai, src, biko, touroku = row
    ban = ban.strip()
    try:
        kingaku = int(float((kingaku_s or '0').replace(',', '').replace('¥', '').strip() or 0))
    except ValueError:
        kingaku = 0
        warnings.append(f'{rid}: 金額パース不可「{kingaku_s}」→0')
    # 表示キー解決：旧案件番号→案件キー、無ければ案件キー直接一致、無ければ生のB値
    disp = old2key.get(ban) or (ban if ban in key_set else ban)
    if disp not in groups:
        groups[disp] = {
            '旧案件番号': ban if ban.startswith('AR-') else '',
            '分類': {'労務費': 0, '材料費': 0, '外注費': 0, '経費': 0},
            '合計': 0, '件数': 0, '明細': []
        }
    e = groups[disp]
    cat = classify(kanjo, kubun)
    if not kubun:
        warnings.append(f'{rid}: 原価区分が空 → 経費に計上')
    e['分類'][cat] += kingaku
    e['合計'] += kingaku
    e['件数'] += 1
    e['明細'].append({
        'id': rid.strip(), '日付': hiduke.strip(), '店舗': mise.strip(),
        '品目': hinmoku.strip(), '金額': kingaku, '勘定科目': kanjo.strip(),
        '原価区分': kubun.strip(), '支払方法': shiharai.strip(),
        'ソース': src.strip(), '備考': biko.strip()
    })

# 各エントリに最終集計日を付与（M列＝登録日の最大、無ければ集計日）
SHUKEI_BI = '2026-06-09'
for e in groups.values():
    tourokus = [d for d in (m.get('日付') for m in e['明細']) if d]
    e['最終集計日'] = SHUKEI_BI

out = {'最終集計日': SHUKEI_BI, '案件': groups}
with open('genka.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

# 検証レポート
print('=== genka.json 生成 ===')
print(f'グループ数: {len(groups)} / 明細総数: {sum(e["件数"] for e in groups.values())}')
print(f'data.json 案件キー一致: {sum(1 for k in groups if k in key_set)} / 未一致(生B値のまま): {[k for k in groups if k not in key_set]}')
print('--- 案件別 合計（data.json 原価との照合用）---')
for k, e in sorted(groups.items(), key=lambda kv: -kv[1]['合計']):
    c = e['分類']
    print(f'{k:32} 労{c["労務費"]:>9} 材{c["材料費"]:>9} 外{c["外注費"]:>9} 経{c["経費"]:>9} 計{e["合計"]:>10} ({e["件数"]}件)')
if warnings:
    print('--- 警告 ---')
    for w in warnings[:30]:
        print(w)
