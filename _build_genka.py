# -*- coding: utf-8 -*-
"""原価管理Sheets(CSV/base64) → genka.json。
2系統の転記(_genka_b64.txt/_v2)から各々クリーン行を最大化抽出して統合し、
残り2行(042/072=AMEX・消耗品費・直接原価=経費)を既知値で補完。
最後に data.json の確定集計(原価)と4分類・件数を突合検証する。"""
import base64, csv, io, json, collections

def load(p): return ''.join(open(p, encoding='utf-8').read().split())
a = load('_genka_b64.txt'); b = load('_genka_b64_v2.txt')

def clean_rows(t):
    if len(t) % 4: return None
    try: d = base64.b64decode(t).decode('utf-8', errors='replace')
    except Exception: return None
    rows = {}
    for l in d.split('\r\n'):
        if l.startswith('RC-26-') and '�' not in l:
            rows[l[:9]] = l
    return rows

def best_del(s):
    best = None
    for i in range(len(s)):
        r = clean_rows(s[:i] + s[i+1:])
        if r is None: continue
        if best is None or len(r) > len(best):
            best = r
            if len(best) >= 90: break
    return best

merged = dict(best_del(a))
for k, v in best_del(b).items():
    merged.setdefault(k, v)
# 破損2行を既知値で補完（AMEX・消耗品費・直接原価→経費。集計影響なし）
merged.setdefault('RC-26-042', 'RC-26-042,AR-26-004,さくら苑 床工事,2026-03-28,アマゾン シーオージェーピー,'
                  'SK11ディスクグラインダー砥石/チップソー(分割),2116,消耗品費,直接原価,カード,AMEX明細,'
                  '親請求書: AMEX_2026-04 / 親注文： 250-6631798-3922206,2026-05-07')
merged.setdefault('RC-26-072', 'RC-26-072,AR-26-004,さくら苑(立願の森),2026-05-12,アマゾン,'
                  'タジマ セフシステム 工具ボックス用車載マウント TB-MT 車の荷台に載せたボ,2505,消耗品費,直接原価,カード,AMEX明細,'
                  'AMEX_2026-05,2026-05-29')

# data.json で 旧案件番号→案件キー
data = json.load(open('data.json', encoding='utf-8'))
old2key, key_set, key2genka = {}, set(), {}
for a_ in data.get('案件', []):
    k = a_.get('案件キー') or a_.get('案件番号')
    if k:
        key_set.add(k); key2genka[k] = a_.get('原価', {})
    if a_.get('旧案件番号'):
        old2key[a_['旧案件番号']] = k

def classify(kanjo, kubun):
    if kubun == '一般経費': return '経費'
    if kubun == '直接原価':
        return kanjo if kanjo in ('材料費', '外注費', '労務費') else '経費'
    return '経費'

groups = collections.OrderedDict()
for rid in sorted(merged):
    row = next(csv.reader(io.StringIO(merged[rid])))
    row = (row + [''] * 13)[:13]
    _, ban, genba, hiduke, mise, hinmoku, kin_s, kanjo, kubun, shiharai, src, biko, touroku = row
    ban = ban.strip()
    try: kin = int(float((kin_s or '0').replace(',', '').strip() or 0))
    except ValueError: kin = 0
    disp = old2key.get(ban, ban)
    e = groups.setdefault(disp, {'旧案件番号': ban if ban.startswith('AR-') else '',
                                 '分類': {'労務費': 0, '材料費': 0, '外注費': 0, '経費': 0},
                                 '合計': 0, '件数': 0, '最終集計日': '2026-06-09', '明細': []})
    e['分類'][classify(kanjo.strip(), kubun.strip())] += kin
    e['合計'] += kin; e['件数'] += 1
    e['明細'].append({'id': rid, '日付': hiduke.strip(), '店舗': mise.strip(), '品目': hinmoku.strip(),
                     '金額': kin, '勘定科目': kanjo.strip(), '原価区分': kubun.strip(),
                     '支払方法': shiharai.strip(), 'ソース': src.strip(), '備考': biko.strip()})

json.dump({'最終集計日': '2026-06-09', '案件': groups},
          open('genka.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# ── 検証：data.json確定集計との突合 ──
print('rows used:', sum(e['件数'] for e in groups.values()), '/ groups:', len(groups))
print(f'{"案件":30} {"件数":>4} {"明細計":>9} {"原価計(dj)":>10}  4分類一致?')
allok = True
for k, e in sorted(groups.items(), key=lambda kv: -kv[1]['合計']):
    dj = key2genka.get(k, {})
    dj4 = {c: dj.get(c, 0) for c in ('労務費', '材料費', '外注費', '経費')}
    same = (dj4 == e['分類'])
    if k in key_set and not same: allok = False
    mark = 'OK' if same else f'DIFF dj={dj4} me={e["分類"]}'
    inkey = '' if k in key_set else ' [未マッチB値]'
    print(f'{k:30} {e["件数"]:>4} {e["合計"]:>9} {dj.get("合計","-"):>10}  {mark}{inkey}')
print('\n全案件 4分類一致(data.json照合):', allok)
