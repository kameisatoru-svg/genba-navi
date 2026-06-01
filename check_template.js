/* ============================================================
   check_template.js — ステータス看板＋ワークフロー共通定義
   ----------------------------------------------------------
   案件ステータスごとのチェック項目テンプレート。
   dashboard.html（ステータス看板）・workflow.html（動的描画）の
   両方から参照する唯一の真実。

   スキーマ:
   CHECK_TEMPLATE[ステータス] = {
     description: '簡潔な説明',
     stages: [
       {
         id:    'stage_id',
         label: 'ステージ表示名',
         icon:  'svg-icon-id',   // workflow.html 内 SVG sprite の id
         color: '#hexcolor',     // ステージヘッダ色
         items: [
           { id: 'item_id', label: '項目名', detail: '補足説明' }
         ]
       }
     ]
   }

   状態（保存値）:
   - undefined (= 未着手・todo)
   - 'wip'  : 着手中
   - 'done' : 完了
   - 'na'   : 該当なし（進捗バーの分母から除外）

   ステータス遷移時の孤立チェックの扱い（2026/5/18確定）:
   - 案件のステータスが進む（例: 相談→見積準備）と、前ステータスの
     テンプレート項目は新テンプレートにないため UI に表示されなくなる
   - これら「孤立キー」は data.json に**そのまま残す**（自動削除しない）
   - 履歴として保持され、将来 anken-summary 側で「完了履歴」として参照可能
   - 表面上は見えないだけで、データ量的にもごく軽微

   注意:
   - スキーマ変更時は dashboard.html / workflow.html / anken-checklist SKILL.md
     の3つを同時に確認すること
   - 単純なテキストエディタでも開けるよう、シンプルなJS定数として保つ

   命名規約（2026/6/1 統一・重複整理）:
   - 書類フローは必ず「PDF発行 → 送付 → data.json に反映」の3点をこの順で並べる
       * id は pdf / send / register（ステージidで一意になるので接頭辞は付けない）
       * label は「○○書PDF発行」「○○書送付」「data.json に反映」で統一
       * 「data.json に反映」の detail に、どの配列・項目を更新するかを書く
   - 写真項目は「○○写真の撮影」で統一（着工前・完工 など）
   - カレンダー項目は「カレンダー登録（用途）」で統一（全角カッコ）
   - 同じ書類実務を複数ステータスに重複して置かない。
     例）契約書締結・注文請書は「施工予定」に集約。「見積提出済み」は
         受注見込みの確認とドラフト準備までに留める（取りこぼしは
         getCarryOverItems の持ち越し機構が拾う）
   ============================================================ */

const CHECK_TEMPLATE = {
  '相談': {
    description: '問合せ受領から現地調査・見積方針確定まで',
    stages: [
      {
        id: 'contact',
        label: 'コンタクト',
        icon: 'customer-icon',
        color: '#3498db',
        items: [
          { id: 'first',    label: '初回問合せの記録',        detail: '通話・メール・LINE等の経路を備考に残す' },
          { id: 'kokyaku',  label: '顧客マスター登録',        detail: '新規顧客の場合 T-XXX を採番（meishi-to-data-json）' },
          { id: 'reg',      label: '案件登録（data.json）',    detail: '案件キー採番・案件配列に追加' },
          { id: 'apo',      label: '初回面談アポ',            detail: '電話・現場訪問・オンラインのいずれかを段取り' }
        ]
      },
      {
        id: 'survey',
        label: '現地調査',
        icon: 'survey-icon',
        color: '#e67e22',
        items: [
          { id: 'schedule', label: '現調日時の調整',          detail: '顧客と現調日時を確定・カレンダー登録' },
          { id: 'photo',    label: '現場写真の撮影',          detail: '全景・問題箇所・周辺状況を案件フォルダに保存' },
          { id: 'sumpo',    label: '寸法計測・スケッチ',      detail: '主要寸法とラフスケッチを記録' },
          { id: 'memo',     label: '現場メモ作成',            detail: '所見・特記事項を 00_履歴_案件キー.md に追記' }
        ]
      },
      {
        id: 'prep',
        label: '見積方針',
        icon: 'estimate-icon',
        color: '#9b59b6',
        items: [
          { id: 'spec',     label: '仕様・商品の擦り合わせ',  detail: 'グレード・色・数量レンジを顧客と確認' },
          { id: 'mat',      label: '材料割付',                detail: '使用部材と数量を確定（材料割付_app）' },
          { id: 'tanka',    label: '単価決定',                detail: '単価マスタを参照・必要なら更新' },
          { id: 'gyousha',  label: '協力業者への打診',        detail: '外注が必要なら業者向け概算依頼' }
        ]
      }
    ]
  },

  '見積準備': {
    description: '見積書を作成して顧客に提出するまで',
    stages: [
      {
        id: 'compose',
        label: '見積作成',
        icon: 'estimate-icon',
        color: '#3498db',
        items: [
          { id: 'breakdown', label: '内訳作成',                detail: '材料・労務・諸経費を積算（みつも朗 or mitsumori-seikyu-create）' },
          { id: 'amount',    label: '金額確定',                detail: '合計・消費税・端数処理を確認' },
          { id: 'review',    label: '体裁チェック',            detail: '宛名・件名・有効期限・備考を確認' },
          { id: 'pdf',       label: '見積書PDF発行',           detail: 'PDF化して案件フォルダに保存' }
        ]
      },
      {
        id: 'submit',
        label: '提出',
        icon: 'order-icon',
        color: '#27ae60',
        items: [
          { id: 'send',      label: '見積書送付',              detail: 'メール・郵送・対面のいずれか' },
          { id: 'register',  label: 'data.json に反映',        detail: '案件の見積[]配列に追加' },
          { id: 'followup',  label: 'フォロー連絡',            detail: '提出から1週間以内に確認連絡' }
        ]
      }
    ]
  },

  '見積提出済み': {
    description: '顧客の検討・受注見込みの確認段階',
    stages: [
      {
        id: 'followup',
        label: 'フォロー',
        icon: 'customer-icon',
        color: '#3498db',
        items: [
          { id: 'arrive',   label: '提出後の到達確認',         detail: 'メール受信確認・郵送到着確認' },
          { id: 'react',    label: '顧客の反応・質疑対応',     detail: '仕様変更要望・金額調整の協議' },
          { id: 'decision', label: '受注見込みの感触確認',     detail: '前向き・保留・他社比較中のいずれか把握' }
        ]
      },
      {
        id: 'contract',
        label: '契約準備',
        icon: 'order-icon',
        color: '#9b59b6',
        items: [
          { id: 'draft',    label: '工事請負契約書ドラフト',   detail: '雛形をベースに案件情報を流し込む（締結・注文請書は施工予定で実施）' }
        ]
      }
    ]
  },

  '施工予定': {
    description: '受注後の着工準備（旧6カテゴリ統合版）',
    stages: [
      {
        id: 'doc_k',
        label: '顧客向け書類',
        icon: 'estimate-icon',
        color: '#3498db',
        items: [
          { id: 'mitsumori_final', label: '見積採用案の確定',           detail: '採用案以外は 旧A/B/C のサフィックスを付与' },
          { id: 'keiyaku',         label: '工事請負契約書',             detail: '顧客と契約締結・PDF保管' },
          { id: 'chumonsho',       label: '注文請書（元請あり）',       detail: '元請への請書発行' }
        ]
      },
      {
        id: 'doc_g',
        label: '業者向け書類',
        icon: 'order-icon',
        color: '#27ae60',
        items: [
          { id: 'order',           label: '業者向け注文書',             detail: '関連業者に対する注文書PDF発行' },
          { id: 'order_recv',      label: '注文請書受領',               detail: '業者からの請書を受領・保管' }
        ]
      },
      {
        id: 'dandori',
        label: '段取り',
        icon: 'survey-icon',
        color: '#3498db',
        items: [
          { id: 'koteihyo_make',   label: '業者用工程表作成',           detail: '作業時間・人員配置を明記' },
          { id: 'koteihyo_send',   label: '業者用工程表送付',           detail: 'メール・LINE等で業者に共有' },
          { id: 'heimen',          label: '平面図（マーキング版）',     detail: '施工範囲を明示した平面図' },
          { id: 'hannyuro',        label: '搬入路確認',                 detail: '車両動線・搬入経路を確認' },
          { id: 'zairyou',         label: '材料発注',                   detail: 'メーカー・商社への発注完了' }
        ]
      },
      {
        id: 'shisetsu',
        label: '施設調整',
        icon: 'customer-icon',
        color: '#e67e22',
        items: [
          { id: 'kagu',            label: '家具移動依頼',               detail: '事前に顧客側で対応する範囲を確認' },
          { id: 'doseni',          label: '動線確保依頼',               detail: '入居者・スタッフの動線を確保' },
          { id: 'shuchi',          label: '入居者・利用者への周知',     detail: '騒音・粉塵・接着剤臭の配慮事項を共有' }
        ]
      },
      {
        id: 'taisei',
        label: '施工体制',
        icon: 'survey-icon',
        color: '#9b59b6',
        items: [
          { id: 'renraku',         label: '業者連絡先確定',             detail: 'data.json 取引先マスターに電話・住所あり' },
          { id: 'shukuhaku',       label: '宿泊予約(遠方時)',           detail: '熊本・福岡など県外時のみ必須' },
          { id: 'cal_shiko',       label: 'カレンダー登録（施工）',     detail: '【施工】Basil 緑(colorId:10)' },
          { id: 'cal_shuku',       label: 'カレンダー登録（宿泊）',     detail: '【宿泊】Blueberry 青(colorId:9)' }
        ]
      }
    ]
  },

  '施工中': {
    description: '施工本番〜完工確認まで',
    stages: [
      {
        id: 'shinkou',
        label: '進行',
        icon: 'order-icon',
        color: '#b97843',
        items: [
          { id: 'photo_before',    label: '着工前写真の撮影',           detail: '全景・施工対象範囲・周辺状況' },
          { id: 'daily',           label: '日次進捗の記録',             detail: '通話記録・写真・所見を 00_履歴_案件キー.md に追記' },
          { id: 'chosei',          label: '現場調整・変更対応',         detail: '仕様変更・追加要望・トラブル対応' }
        ]
      },
      {
        id: 'kanryou',
        label: '完工対応',
        icon: 'estimate-icon',
        color: '#27ae60',
        items: [
          { id: 'photo_after',     label: '完工写真の撮影',             detail: '同じアングルで Before/After を揃える' },
          { id: 'tachiai',         label: '顧客立会い確認',             detail: '仕上がり・残材・清掃状況を顧客と確認' }
        ]
      }
    ]
  },

  '請求済み': {
    description: '完工後の請求書発行・入金待ち',
    stages: [
      {
        id: 'invoice',
        label: '請求',
        icon: 'estimate-icon',
        color: '#7a9d6f',
        items: [
          { id: 'pdf',      label: '請求書PDF発行',              detail: 'mitsumori-seikyu-create で生成' },
          { id: 'send',     label: '請求書送付',                 detail: 'メール・郵送・対面のいずれか' },
          { id: 'register', label: 'data.json に反映',           detail: '案件の請求[]配列に追加' }
        ]
      },
      {
        id: 'docs',
        label: '完了書類',
        icon: 'order-icon',
        color: '#9b59b6',
        items: [
          { id: 'kanryousho',      label: '完了書発行(元請あり)',       detail: '元請への完了報告書' },
          { id: 'nouhinsho',       label: '納品書発行',                 detail: '納品書PDFを案件フォルダに保存' }
        ]
      }
    ]
  },

  '入金済み': {
    description: '入金確認・原価確定・アーカイブ',
    stages: [
      {
        id: 'nyukin',
        label: '入金確認',
        icon: 'estimate-icon',
        color: '#4a7c4e',
        items: [
          { id: 'kakunin',         label: '入金確認',                   detail: '通帳・銀行明細で入金額を照合' },
          { id: 'register',        label: 'data.json に反映',           detail: '請求[].入金状況=nyukin・入金日 を更新' }
        ]
      },
      {
        id: 'genka',
        label: '原価締め',
        icon: 'order-icon',
        color: '#27ae60',
        items: [
          { id: 'amex',            label: 'AMEX明細の振り分け',         detail: 'amex-categorizer-post で原価管理Sheetsに反映' },
          { id: 'aggregate',       label: '原価集計',                   detail: 'genka-aggregate で data.json.原価 を更新' },
          { id: 'archive',         label: 'フォルダアーカイブ',         detail: '_アーカイブ/ への退避を提案' }
        ]
      }
    ]
  },

  '完了(請求書作成済み)': {
    description: 'クローズ済み案件',
    stages: []
  }
};

/* ============================================================
   ステータス順序（持ち越し算出用）
   ============================================================ */
const STATUS_ORDER = [
  '相談',
  '見積準備',
  '見積提出済み',
  '施工予定',
  '施工中',
  '請求済み',
  '入金済み'
];

/* ============================================================
   持ち越し項目の抽出
   ----------------------------------------------------------
   先行施工パターン対応：見積を後回しで施工に進んだケースで、
   前ステータスの「未完了かつ該当ありの項目」を取りこぼさない仕組み。

   現ステータスより前のステータステンプレートを巡回し、
   チェック状態が done / na **以外** の項目を「持ち越し」として返す。

   返り値:
     [{ key, status, stageId, stageLabel, itemId, label, detail, state }]
   ============================================================ */
function getCarryOverItems(anken) {
  if (!anken) return [];
  const currentStatus = anken['ステータス'];
  const currentIdx = STATUS_ORDER.indexOf(currentStatus);
  if (currentIdx <= 0) return [];  // 相談より前 or 順序対象外

  const checks = anken['チェック'] || {};
  // チェック未開始の案件には持ち越しを出さない
  // （checks空 = まだ運用に乗っていない、レガシー案件と同じ扱い）
  if (Object.keys(checks).length === 0) return [];

  const result = [];

  for (let i = 0; i < currentIdx; i++) {
    const prevStatus = STATUS_ORDER[i];
    const tpl = CHECK_TEMPLATE[prevStatus];
    if (!tpl || !tpl.stages) continue;
    for (const stage of tpl.stages) {
      for (const item of stage.items) {
        const key = `${stage.id}.${item.id}`;
        const state = checks[key];
        if (state !== 'done' && state !== 'na') {
          result.push({
            key,
            status: prevStatus,
            stageId: stage.id,
            stageLabel: stage.label,
            itemId: item.id,
            label: item.label,
            detail: item.detail,
            state: state || 'todo'
          });
        }
      }
    }
  }
  return result;
}
