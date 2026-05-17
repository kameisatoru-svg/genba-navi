/* ═══════════════════════════════════════════════════════════════════════════
   vendor_editor.js — 取引先マスター編集共通モジュール
   Phase 1: PAT管理 / GitHub PUT / 編集モーダル / 新規取引先モーダル / トースト

   使い方:
     <script src="vendor_editor.js"></script>
     vendorEditor.init({
       repo: 'kameisatoru-svg/genba-navi',
       branch: 'main',
       filePath: 'data.json',
       onSaved: () => location.reload(),
     });
     vendorEditor.openEdit(vendorObject);   // 編集
     vendorEditor.openNew();                // 新規採番
   ═══════════════════════════════════════════════════════════════════════════ */
(function(){
  'use strict';

  const STORAGE_PAT = 've_github_pat';
  const STORAGE_API = 've_anthropic_key';

  let CONF = {
    repo: 'kameisatoru-svg/genba-navi',
    branch: 'main',
    filePath: 'data.json',
    onSaved: null,
  };

  /* ──────────────────────────────────────────────────────────
     CSS注入（取引先台帳のnavyテーマに合わせる）
     ────────────────────────────────────────────────────────── */
  function injectCss(){
    if(document.getElementById('vendor-editor-css')) return;
    const css = `
      .ve-overlay{position:fixed;inset:0;background:rgba(15,23,35,0.55);z-index:1000;
        display:none;align-items:flex-start;justify-content:center;overflow-y:auto;padding:24px 12px;}
      .ve-overlay.open{display:flex;}
      .ve-modal{background:#fff;width:100%;max-width:720px;border-radius:14px;
        box-shadow:0 20px 60px rgba(0,0,0,0.3);overflow:hidden;font-family:Meiryo,'Yu Gothic',sans-serif;color:#333;}
      .ve-modal-header{background:#1e2d40;color:#fff;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;}
      .ve-modal-header h2{font-size:16px;font-weight:700;margin:0;letter-spacing:0.04em;}
      .ve-modal-close{background:transparent;border:none;color:#fff;font-size:22px;cursor:pointer;padding:0 6px;line-height:1;}
      .ve-modal-body{padding:18px 20px;max-height:calc(100vh - 180px);overflow-y:auto;}
      .ve-modal-footer{padding:12px 20px;border-top:1px solid #eee;display:flex;justify-content:flex-end;gap:8px;background:#fafafa;}
      .ve-btn{padding:9px 18px;border-radius:8px;border:1px solid #aaa;background:#fff;font-size:13px;font-weight:700;
        cursor:pointer;font-family:inherit;min-height:40px;}
      .ve-btn:hover{background:#f4f4f4;}
      .ve-btn-primary{background:#1e2d40;color:#fff;border-color:#1e2d40;}
      .ve-btn-primary:hover{background:#15212f;}
      .ve-btn-danger{background:#dc2626;color:#fff;border-color:#dc2626;}
      .ve-btn-ghost{background:transparent;border:none;color:#1e2d40;font-weight:600;}
      .ve-btn-ghost:hover{background:#eef2f7;}
      .ve-btn-sm{padding:5px 12px;min-height:32px;font-size:12px;}

      .ve-field{margin-bottom:12px;}
      .ve-field label{display:block;font-size:12px;font-weight:700;color:#555;margin-bottom:4px;letter-spacing:0.02em;}
      .ve-field input[type=text], .ve-field input[type=email], .ve-field input[type=tel],
      .ve-field textarea, .ve-field select{
        width:100%;padding:8px 10px;border:1px solid #ccc;border-radius:6px;font-size:14px;
        font-family:inherit;background:#fff;box-sizing:border-box;
      }
      .ve-field textarea{min-height:64px;resize:vertical;line-height:1.5;}
      .ve-field input:focus, .ve-field textarea:focus, .ve-field select:focus{outline:none;border-color:#c8a96e;box-shadow:0 0 0 2px rgba(200,169,110,0.25);}
      .ve-field-row{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
      .ve-field-help{font-size:11px;color:#888;margin-top:3px;}

      .ve-chip-group{display:flex;flex-wrap:wrap;gap:6px;}
      .ve-chip{padding:6px 12px;border-radius:18px;border:1px solid #ccc;background:#fff;font-size:12px;
        font-weight:600;cursor:pointer;user-select:none;font-family:inherit;}
      .ve-chip.on{background:#1e2d40;color:#fff;border-color:#1e2d40;}

      .ve-section{margin-top:18px;padding-top:14px;border-top:1px dashed #ddd;}
      .ve-section:first-child{margin-top:0;padding-top:0;border-top:none;}
      .ve-section-title{font-size:13px;font-weight:700;color:#1e2d40;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;}

      .ve-contact-card{background:#f8f9fb;border:1px solid #e3e6ec;border-radius:8px;padding:10px 12px;margin-bottom:8px;position:relative;}
      .ve-contact-card .ve-contact-remove{position:absolute;top:6px;right:8px;background:transparent;border:none;color:#999;font-size:18px;cursor:pointer;line-height:1;}
      .ve-contact-card .ve-contact-remove:hover{color:#dc2626;}

      .ve-toast{position:fixed;bottom:24px;left:50%;transform:translateX(-50%);
        background:#1e2d40;color:#fff;padding:10px 22px;border-radius:24px;
        font-size:13px;font-weight:700;opacity:0;transition:opacity 0.3s;
        pointer-events:none;z-index:2000;font-family:Meiryo,'Yu Gothic',sans-serif;
        max-width:min(90vw, 700px);text-align:center;}
      .ve-toast.show{opacity:1;pointer-events:auto;}
      .ve-toast.err{background:#dc2626;}
      .ve-toast.err::after{content:' ✕ クリックで閉じる';font-weight:400;font-size:11px;opacity:0.85;}

      .ve-pat-warn{background:#fff8e1;border:1px solid #f6d36a;border-radius:6px;padding:10px 12px;font-size:12px;color:#7a5b00;margin-bottom:12px;}
      .ve-pat-warn code{background:#fff;padding:1px 5px;border-radius:3px;font-size:11px;}

      /* 重複マージモーダル */
      .ve-merge-card{background:#fff;border:1px solid #e3e6ec;border-left:4px solid #c8a96e;border-radius:8px;padding:10px 12px;margin-bottom:10px;}
      .ve-merge-card-head{display:flex;align-items:center;gap:10px;margin-bottom:6px;flex-wrap:wrap;}
      .ve-merge-tag{background:#1e2d40;color:#fff;font-size:11px;font-weight:700;padding:2px 8px;border-radius:10px;}
      .ve-merge-meta{display:grid;grid-template-columns:1fr 1fr;gap:3px 14px;font-size:12px;color:#333;margin-bottom:8px;}
      .ve-merge-meta b{color:#666;font-weight:600;margin-right:5px;font-size:11px;}
      .ve-merge-action{display:flex;align-items:center;gap:8px;padding-top:8px;border-top:1px dashed #e3e6ec;}
      .ve-merge-action label{font-size:12px;color:#666;font-weight:600;}
      .ve-merge-action select{flex:1;padding:6px 8px;border:1px solid #ccc;border-radius:6px;font-size:13px;font-family:inherit;background:#fff;}
      .ve-merge-current{background:#f8f9fb;border-radius:8px;padding:10px 12px;font-size:12px;margin-bottom:10px;line-height:1.6;}
      .ve-merge-current b{color:#666;font-weight:600;}

      /* Eight CSV検索パネル */
      .ve-eight-toggle{width:100%;text-align:left;padding:10px 14px;background:#fff8e8;color:#7a5b00;
        border:1px solid #e8d9a0;border-radius:8px;cursor:pointer;font-family:inherit;font-size:13px;font-weight:700;}
      .ve-eight-toggle:hover{background:#fff3d4;}
      .ve-eight-panel{margin-top:10px;padding:10px 12px;background:#fffbf0;border:1px solid #f0e0a8;border-radius:8px;}
      .ve-eight-results{margin-top:8px;max-height:240px;overflow-y:auto;}
      .ve-eight-hit{background:#fff;border:1px solid #e8e6e0;border-radius:6px;padding:8px 10px;margin-bottom:6px;font-size:12px;display:grid;grid-template-columns:1fr auto;gap:6px;align-items:center;}
      .ve-eight-hit-meta{line-height:1.5;}
      .ve-eight-hit b{color:#666;font-weight:600;margin-right:4px;}
      .ve-eight-apply{padding:6px 12px;background:#c8a96e;color:#1e2d40;border:none;border-radius:6px;font-size:11px;font-weight:700;cursor:pointer;font-family:inherit;white-space:nowrap;}
      .ve-eight-apply:hover{background:#b8996a;}

      /* 重複候補バッジ（カード側に表示） */
      .ve-dup-badge{display:inline-block;background:#f59e0b;color:#fff;font-size:11px;font-weight:700;
        padding:2px 8px;border-radius:10px;margin-left:6px;cursor:pointer;}
      .ve-dup-badge:hover{background:#d97706;}

      @media(max-width:600px){
        .ve-field-row{grid-template-columns:1fr;}
        .ve-modal{max-width:none;}
        .ve-modal-body{padding:14px;}
        .ve-merge-meta{grid-template-columns:1fr;}
        .ve-eight-hit{grid-template-columns:1fr;}
      }
    `;
    const style = document.createElement('style');
    style.id = 'vendor-editor-css';
    style.textContent = css;
    document.head.appendChild(style);
  }

  /* ──────────────────────────────────────────────────────────
     ベースモーダル
     ────────────────────────────────────────────────────────── */
  function ensureOverlay(){
    let ov = document.getElementById('ve-overlay');
    if(ov) return ov;
    ov = document.createElement('div');
    ov.id = 've-overlay';
    ov.className = 've-overlay';
    ov.addEventListener('click', (e) => { if(e.target === ov) closeModal(); });
    document.body.appendChild(ov);
    return ov;
  }
  function openModal(html){
    injectCss();
    const ov = ensureOverlay();
    ov.innerHTML = html;
    ov.classList.add('open');
    document.body.style.overflow = 'hidden';
    // ESC で閉じる
    document.removeEventListener('keydown', escClose);
    document.addEventListener('keydown', escClose);
    return ov.querySelector('.ve-modal');
  }
  function closeModal(){
    const ov = document.getElementById('ve-overlay');
    if(ov){ ov.classList.remove('open'); ov.innerHTML=''; }
    document.body.style.overflow = '';
    document.removeEventListener('keydown', escClose);
  }
  function escClose(e){ if(e.key === 'Escape') closeModal(); }

  /* ──────────────────────────────────────────────────────────
     トースト
     ────────────────────────────────────────────────────────── */
  function toast(msg, isError){
    injectCss();
    let t = document.getElementById('ve-toast');
    if(!t){
      t = document.createElement('div');
      t.id = 've-toast';
      t.className = 've-toast';
      t.addEventListener('click', () => { t.classList.remove('show'); });
      document.body.appendChild(t);
    }
    t.textContent = msg;
    t.classList.toggle('err', !!isError);
    t.classList.add('show');
    clearTimeout(t._timer);
    // エラーは長め＆クリックで消える / 通常は2.2秒
    const duration = isError ? 15000 : 2200;
    t._timer = setTimeout(() => t.classList.remove('show'), duration);
    if(isError) console.error('[vendor_editor toast]', msg);
  }

  /* ──────────────────────────────────────────────────────────
     PAT管理
     ────────────────────────────────────────────────────────── */
  function getPat(){ return localStorage.getItem(STORAGE_PAT) || ''; }
  function setPat(v){
    if(v) localStorage.setItem(STORAGE_PAT, v);
    else localStorage.removeItem(STORAGE_PAT);
  }
  /* Anthropic APIキー管理 */
  function getAnthropicKey(){ return localStorage.getItem(STORAGE_API) || ''; }
  function setAnthropicKey(v){
    if(v) localStorage.setItem(STORAGE_API, v);
    else localStorage.removeItem(STORAGE_API);
  }
  function promptAnthropicKey(){
    return new Promise((resolve) => {
      injectCss();
      const cur = getAnthropicKey();
      const modal = openModal(`
        <div class="ve-modal">
          <div class="ve-modal-header">
            <h2>🤖 Anthropic API Key</h2>
            <button class="ve-modal-close" data-action="close">×</button>
          </div>
          <div class="ve-modal-body">
            <div class="ve-pat-warn">
              名刺画像の自動読み取りに Anthropic API（Claudeモデル）を使用します。<br>
              ① <a href="https://console.anthropic.com/settings/keys" target="_blank">Anthropic Console</a> でAPIキーを発行<br>
              ② 「Create Key」で <code>sk-ant-...</code> をコピー<br>
              ③ 下の欄に貼り付け<br>
              ※ APIキーはこの端末の localStorage のみに保存（外部送信なし）<br>
              ※ 名刺1枚あたり概ね $0.005〜$0.01（Sonnet 4.6使用）
            </div>
            <div class="ve-field">
              <label>API Key</label>
              <input type="text" id="ve-api-input" value="${esc(cur)}" placeholder="sk-ant-api03-xxxxxxxxxxxx" autocomplete="off">
              <div class="ve-field-help">${cur ? '※ 設定済み。再入力で上書きされます。' : ''}</div>
            </div>
          </div>
          <div class="ve-modal-footer">
            ${cur ? '<button class="ve-btn ve-btn-danger" data-action="clear">削除</button>' : ''}
            <button class="ve-btn" data-action="cancel">キャンセル</button>
            <button class="ve-btn ve-btn-primary" data-action="save">保存</button>
          </div>
        </div>
      `);
      modal.addEventListener('click', (e) => {
        const a = e.target.closest('[data-action]');
        if(!a) return;
        const action = a.dataset.action;
        if(action === 'save'){
          const v = document.getElementById('ve-api-input').value.trim();
          if(!v){ toast('APIキーを入力してください', true); return; }
          setAnthropicKey(v);
          toast('APIキーを保存しました');
          closeModal();
          resolve(v);
        }else if(action === 'clear'){
          if(confirm('保存されているAPIキーを削除しますか？')){
            setAnthropicKey('');
            toast('APIキーを削除しました');
            closeModal();
            resolve('');
          }
        }else if(action === 'cancel' || action === 'close'){
          closeModal();
          resolve(cur);
        }
      });
      const inp = document.getElementById('ve-api-input');
      if(inp){
        inp.focus();
        inp.addEventListener('keydown', (e) => {
          if(e.key === 'Enter'){
            e.preventDefault();
            modal.querySelector('[data-action="save"]').click();
          }
        });
      }
    });
  }
  function promptPat(){
    return new Promise((resolve) => {
      injectCss();
      const cur = getPat();
      const modal = openModal(`
        <div class="ve-modal">
          <div class="ve-modal-header">
            <h2>🔑 GitHub Personal Access Token (PAT)</h2>
            <button class="ve-modal-close" data-action="close">×</button>
          </div>
          <div class="ve-modal-body">
            <div class="ve-pat-warn">
              data.json の編集を保存するには GitHub PAT が必要です。<br>
              ① <a href="https://github.com/settings/personal-access-tokens/new" target="_blank">GitHub PAT発行ページ</a> を開く<br>
              ② Repository access: <code>kameisatoru-svg/genba-navi</code> のみ選択<br>
              ③ Permissions: <code>Contents: Read and write</code> を許可<br>
              ④ 発行された <code>github_pat_...</code> を貼り付け<br>
              ※ PATはこの端末の localStorage のみに保存されます（外部送信なし）
            </div>
            <div class="ve-field">
              <label>PAT</label>
              <input type="text" id="ve-pat-input" value="${esc(cur)}" placeholder="github_pat_xxxxxxxxxxxx" autocomplete="off">
              <div class="ve-field-help">${cur ? '※ 設定済み。再入力で上書きされます。' : ''}</div>
            </div>
          </div>
          <div class="ve-modal-footer">
            ${cur ? '<button class="ve-btn ve-btn-danger" data-action="clear">削除</button>' : ''}
            <button class="ve-btn" data-action="cancel">キャンセル</button>
            <button class="ve-btn ve-btn-primary" data-action="save">保存</button>
          </div>
        </div>
      `);
      modal.addEventListener('click', (e) => {
        const a = e.target.closest('[data-action]');
        if(!a) return;
        const action = a.dataset.action;
        if(action === 'save'){
          const v = document.getElementById('ve-pat-input').value.trim();
          if(!v){ toast('PATを入力してください', true); return; }
          setPat(v);
          toast('PATを保存しました');
          closeModal();
          resolve(v);
        }else if(action === 'clear'){
          if(confirm('保存されているPATを削除しますか？')){
            setPat('');
            toast('PATを削除しました');
            closeModal();
            resolve('');
          }
        }else if(action === 'cancel' || action === 'close'){
          closeModal();
          resolve(cur);
        }
      });
      // Enterキー保存
      const inp = document.getElementById('ve-pat-input');
      if(inp){
        inp.focus();
        inp.addEventListener('keydown', (e) => {
          if(e.key === 'Enter'){
            e.preventDefault();
            modal.querySelector('[data-action="save"]').click();
          }
        });
      }
    });
  }

  /* ──────────────────────────────────────────────────────────
     GitHub API: 取得・コミット
     ────────────────────────────────────────────────────────── */
  async function ghHeaders(){
    let pat = getPat();
    if(!pat){
      pat = await promptPat();
      if(!pat) throw new Error('PAT未設定');
    }
    return {
      'Authorization': 'Bearer ' + pat,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
    };
  }
  async function fetchDataJson(retry){
    const headers = await ghHeaders();
    const url = `https://api.github.com/repos/${CONF.repo}/contents/${CONF.filePath}?ref=${CONF.branch}`;
    const res = await fetch(url, { headers });
    if(!res.ok){
      const txt = await res.text();
      // PATが無効/期限切れ → クリアして1回だけ再入力プロンプト→リトライ
      if((res.status === 401 || res.status === 403) && !retry){
        setPat('');
        const newPat = await promptPat();
        if(!newPat) throw new Error('GitHub PATが必要です（PAT設定ボタンから登録してください）');
        return fetchDataJson(true);
      }
      const hint = (res.status === 401 || res.status === 403)
        ? '\nPATが無効か権限不足です。鍵アイコンから再設定してください。'
        : '';
      throw new Error(`GitHub取得失敗 ${res.status}: ${txt.slice(0,200)}${hint}`);
    }
    const meta = await res.json();
    // contentはbase64 (改行入り)
    const raw = atob(meta.content.replace(/\n/g,''));
    const utf8 = decodeURIComponent(escape(raw));
    return { sha: meta.sha, data: JSON.parse(utf8) };
  }
  async function commitDataJson(newData, message, sha, retry){
    const headers = { ...(await ghHeaders()), 'Content-Type':'application/json' };
    const json = JSON.stringify(newData, null, 2);
    const b64 = btoa(unescape(encodeURIComponent(json)));
    const body = {
      message: message || 'vendor_editor update',
      content: b64,
      sha: sha,
      branch: CONF.branch,
    };
    const url = `https://api.github.com/repos/${CONF.repo}/contents/${CONF.filePath}`;
    const res = await fetch(url, { method:'PUT', headers, body: JSON.stringify(body) });
    if(!res.ok){
      const txt = await res.text();
      if((res.status === 401 || res.status === 403) && !retry){
        setPat('');
        const newPat = await promptPat();
        if(!newPat) throw new Error('GitHub PATが必要です（PAT設定ボタンから登録してください）');
        return commitDataJson(newData, message, sha, true);
      }
      const hint = (res.status === 401 || res.status === 403)
        ? '\nPATが無効か権限不足です。鍵アイコンから再設定してください。'
        : '';
      throw new Error(`コミット失敗 ${res.status}: ${txt.slice(0,200)}${hint}`);
    }
    return await res.json();
  }

  /* ──────────────────────────────────────────────────────────
     ID採番
     ────────────────────────────────────────────────────────── */
  function nextVendorId(master){
    let max = 0;
    (master || []).forEach(v => {
      const m = /^T-(\d+)$/.exec(v.id || '');
      if(m){ const n = parseInt(m[1],10); if(n > max) max = n; }
    });
    return 'T-' + String(max + 1).padStart(3, '0');
  }

  /* ──────────────────────────────────────────────────────────
     編集モーダル（新規/編集共通）
     ────────────────────────────────────────────────────────── */
  const REL_OPTIONS = ['顧客','元請','業者','仕入先','休眠'];
  // 既出typeを集める + よくあるものをデフォルトで
  const TYPE_DEFAULTS = ['公共施設','住宅・個人','店舗・法人','ゼネコン・元請','左官','内装','塗装','防水','板金','電気','水道','建材','機材','その他'];

  function openEditModal(vendor, mode){
    injectCss();
    const isNew = (mode === 'new');
    // 編集中の状態（クローン）
    const v = JSON.parse(JSON.stringify({
      id: vendor.id || '',
      略称: vendor['略称'] || vendor.ryaku || '',
      正式名称: vendor['正式名称'] || vendor.name || '',
      rel: vendor.rel || [],
      type: vendor.type || [],
      basic: { contact: vendor.basic?.contact || '', rep: vendor.basic?.rep || '' },
      contact: {
        tel:     vendor.contact?.tel     || '',
        mobile:  vendor.contact?.mobile  || '',
        fax:     vendor.contact?.fax     || '',
        mail:    vendor.contact?.mail    || '',
        address: vendor.contact?.address || '',
        touroku: vendor.contact?.touroku || '',
        furikomi:vendor.contact?.furikomi|| '',
      },
      contacts: Array.isArray(vendor.contacts) ? vendor.contacts.map(c => ({...c})) : [],
      memo: vendor.memo || '',
      search: vendor.search || '',
    }));

    const modal = openModal(buildEditHtml(v, isNew));
    bindEditHandlers(modal, v, isNew);
  }

  function buildEditHtml(v, isNew){
    return `
      <div class="ve-modal" onclick="event.stopPropagation()">
        <div class="ve-modal-header">
          <h2>${isNew ? '➕ 新規取引先' : '✏️ 編集 ' + esc(v.id)} ${v['略称'] ? '— ' + esc(v['略称']) : ''}</h2>
          <button class="ve-modal-close" data-action="close">×</button>
        </div>
        <div class="ve-modal-body" id="ve-body">

          <div class="ve-section">
            <div class="ve-section-title">基本</div>
            <div class="ve-field-row">
              <div class="ve-field">
                <label>ID${isNew ? '（自動採番）' : ''}</label>
                <input type="text" id="ve-id" value="${esc(v.id)}" ${isNew ? 'readonly placeholder="保存時に採番"' : 'readonly'}>
              </div>
              <div class="ve-field">
                <label>略称 <span style="color:#dc2626;">*</span></label>
                <input type="text" id="ve-ryaku" value="${esc(v['略称'])}" placeholder="例: 玉寿会">
                <div class="ve-field-help">案件キーで使われるキー。短く一意に。</div>
              </div>
            </div>
            <div class="ve-field">
              <label>正式名称 <span style="color:#dc2626;">*</span></label>
              <input type="text" id="ve-name" value="${esc(v['正式名称'])}" placeholder="例: 社会福祉法人 玉寿会(さくら苑)">
            </div>
          </div>

          <div class="ve-section">
            <div class="ve-section-title">関係性 / 業種</div>
            <div class="ve-field">
              <label>関係性</label>
              <div class="ve-chip-group" id="ve-rel">
                ${REL_OPTIONS.map(r => `<button type="button" class="ve-chip ${v.rel.includes(r)?'on':''}" data-rel="${r}">${r}</button>`).join('')}
              </div>
            </div>
            <div class="ve-field">
              <label>業種（カンマ区切り入力可）</label>
              <input type="text" id="ve-type" value="${esc((v.type||[]).join(', '))}" placeholder="例: 左官, 内装">
              <div class="ve-field-help">候補: ${TYPE_DEFAULTS.join(' / ')}</div>
            </div>
          </div>

          <div class="ve-section">
            <button type="button" class="ve-eight-toggle" data-action="toggle-eight" data-label="📇 Eight CSVから情報を引っ張る">📇 Eight CSVから情報を引っ張る ▼</button>
            <div id="ve-eight-panel" style="display:none;">
              <input type="text" id="ve-eight-search" placeholder="社名・氏名・TELで検索（部分一致）" style="width:100%;padding:8px 10px;border:1px solid #ccc;border-radius:6px;font-size:14px;font-family:inherit;box-sizing:border-box;">
              <div class="ve-eight-results" id="ve-eight-results"><div style="font-size:12px;color:#999;">検索ワードを入力</div></div>
            </div>
          </div>

          <div class="ve-section">
            <div class="ve-section-title">主担当 / 代表</div>
            <div class="ve-field-row">
              <div class="ve-field">
                <label>担当者</label>
                <input type="text" id="ve-basic-contact" value="${esc(v.basic.contact)}" placeholder="例: 西 俊至 様(事務課長)">
              </div>
              <div class="ve-field">
                <label>代表者</label>
                <input type="text" id="ve-basic-rep" value="${esc(v.basic.rep)}" placeholder="例: 山田 勝徳 理事長">
              </div>
            </div>
          </div>

          <div class="ve-section">
            <div class="ve-section-title">連絡先</div>
            <div class="ve-field-row">
              <div class="ve-field">
                <label>TEL</label>
                <input type="tel" id="ve-tel" value="${esc(v.contact.tel)}" placeholder="0977-21-0603">
              </div>
              <div class="ve-field">
                <label>携帯</label>
                <input type="tel" id="ve-mobile" value="${esc(v.contact.mobile)}" placeholder="090-xxxx-xxxx">
              </div>
              <div class="ve-field">
                <label>FAX</label>
                <input type="tel" id="ve-fax" value="${esc(v.contact.fax)}">
              </div>
              <div class="ve-field">
                <label>メール</label>
                <input type="email" id="ve-mail" value="${esc(v.contact.mail)}">
              </div>
            </div>
            <div class="ve-field">
              <label>住所</label>
              <input type="text" id="ve-address" value="${esc(v.contact.address)}" placeholder="〒xxx-xxxx 大分県…">
            </div>
            <div class="ve-field-row">
              <div class="ve-field">
                <label>登録番号</label>
                <input type="text" id="ve-touroku" value="${esc(v.contact.touroku)}" placeholder="T1234567890123">
              </div>
              <div class="ve-field">
                <label>振込先</label>
                <input type="text" id="ve-furikomi" value="${esc(v.contact.furikomi)}" placeholder="○○銀行 △△支店 普通 1234567">
              </div>
            </div>
          </div>

          <div class="ve-section">
            <div class="ve-section-title">
              <span>追加担当者 (contacts[])</span>
              <button class="ve-btn ve-btn-sm" id="ve-add-contact" type="button">＋ 担当者追加</button>
            </div>
            <div id="ve-contacts">${buildContactsHtml(v.contacts)}</div>
            <div class="ve-field-help" style="margin-top:6px;">主担当以外の担当者・別名刺を保持。金融機関のように毎年担当が変わる相手は memo に履歴として残すのが推奨です。</div>
          </div>

          <div class="ve-section">
            <div class="ve-section-title">メモ / 検索キーワード</div>
            <div class="ve-field">
              <label>メモ</label>
              <textarea id="ve-memo" placeholder="契約日・案件履歴・特記事項など">${esc(v.memo)}</textarea>
            </div>
            <div class="ve-field">
              <label>検索キーワード</label>
              <input type="text" id="ve-search" value="${esc(v.search)}" placeholder="${esc(v.id.toLowerCase())} 略称 担当者 地域 業種 ...">
              <div class="ve-field-help">取引先台帳の検索ボックスで引っかける用。空でも保存可。</div>
            </div>
          </div>

          <div class="ve-section">
            <div class="ve-section-title">コミット情報</div>
            <div class="ve-field">
              <label>コミットメッセージ（任意）</label>
              <input type="text" id="ve-commit-msg" placeholder="${isNew ? '新規取引先追加' : v.id + ' 更新'}">
            </div>
          </div>

        </div>
        <div class="ve-modal-footer">
          <button class="ve-btn ve-btn-ghost" data-action="config-pat" type="button">🔑 PAT再設定</button>
          <div style="flex:1;"></div>
          <button class="ve-btn" data-action="cancel" type="button">キャンセル</button>
          <button class="ve-btn ve-btn-primary" data-action="save" type="button">${isNew ? '採番して保存' : '保存（コミット）'}</button>
        </div>
      </div>
    `;
  }

  function buildContactsHtml(contacts){
    if(!contacts || !contacts.length){
      return '<div style="color:#999;font-size:13px;padding:8px 4px;">追加担当者なし</div>';
    }
    return contacts.map((c, i) => `
      <div class="ve-contact-card" data-idx="${i}">
        <button type="button" class="ve-contact-remove" data-action="remove-contact" data-idx="${i}" title="削除">×</button>
        <div class="ve-field-row">
          <div class="ve-field">
            <label>氏名</label>
            <input type="text" data-ck="name" value="${esc(c.name||'')}">
          </div>
          <div class="ve-field">
            <label>部署</label>
            <input type="text" data-ck="dept" value="${esc(c.dept||'')}">
          </div>
        </div>
        <div class="ve-field-row">
          <div class="ve-field">
            <label>役職</label>
            <input type="text" data-ck="role" value="${esc(c.role||'')}">
          </div>
          <div class="ve-field">
            <label>名刺交換日</label>
            <input type="text" data-ck="exchange_date" value="${esc(c.exchange_date||'')}" placeholder="2025/11/17">
          </div>
        </div>
        <div class="ve-field-row">
          <div class="ve-field">
            <label>TEL直通</label>
            <input type="tel" data-ck="tel" value="${esc(c.tel||'')}">
          </div>
          <div class="ve-field">
            <label>携帯</label>
            <input type="tel" data-ck="mobile" value="${esc(c.mobile||'')}">
          </div>
        </div>
        <div class="ve-field-row">
          <div class="ve-field">
            <label>メール</label>
            <input type="email" data-ck="mail" value="${esc(c.mail||'')}">
          </div>
          <div class="ve-field">
            <label>出典</label>
            <input type="text" data-ck="source" value="${esc(c.source||'')}" placeholder="名刺 / 紹介 / メール...">
          </div>
        </div>
      </div>
    `).join('');
  }

  function bindEditHandlers(modal, v, isNew){
    // 関係性チップ
    modal.querySelectorAll('#ve-rel .ve-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        chip.classList.toggle('on');
      });
    });

    // Eight CSV検索パネル
    bindEightSearchPanel(modal, v);

    // 担当者追加
    modal.querySelector('#ve-add-contact').addEventListener('click', () => {
      // 現在DOMから contacts を読んでから push
      const current = readContacts();
      current.push({ name:'', dept:'', role:'', tel:'', mobile:'', mail:'', exchange_date:'', source:'' });
      const wrap = document.getElementById('ve-contacts');
      wrap.innerHTML = buildContactsHtml(current);
      bindContactRemove();
    });

    bindContactRemove();

    function bindContactRemove(){
      modal.querySelectorAll('[data-action="remove-contact"]').forEach(btn => {
        btn.addEventListener('click', () => {
          const idx = parseInt(btn.dataset.idx, 10);
          const current = readContacts();
          current.splice(idx, 1);
          const wrap = document.getElementById('ve-contacts');
          wrap.innerHTML = buildContactsHtml(current);
          bindContactRemove();
        });
      });
    }

    function readContacts(){
      const result = [];
      modal.querySelectorAll('#ve-contacts .ve-contact-card').forEach(card => {
        const c = {};
        card.querySelectorAll('[data-ck]').forEach(inp => {
          c[inp.dataset.ck] = inp.value.trim();
        });
        result.push(c);
      });
      return result;
    }

    function collectForm(){
      const ryaku = modal.querySelector('#ve-ryaku').value.trim();
      const name = modal.querySelector('#ve-name').value.trim();
      if(!ryaku){ throw new Error('略称は必須です'); }
      if(!name){ throw new Error('正式名称は必須です'); }

      const rels = Array.from(modal.querySelectorAll('#ve-rel .ve-chip.on')).map(c => c.dataset.rel);
      const types = modal.querySelector('#ve-type').value.split(/[,、，]/).map(s => s.trim()).filter(Boolean);

      const obj = {
        id: v.id, // 新規時は save 内で採番
        '略称': ryaku,
        '正式名称': name,
        rel: rels,
        type: types,
        basic: {
          contact: modal.querySelector('#ve-basic-contact').value.trim(),
          rep:     modal.querySelector('#ve-basic-rep').value.trim(),
        },
        contact: {
          tel:      modal.querySelector('#ve-tel').value.trim(),
          mobile:   modal.querySelector('#ve-mobile').value.trim(),
          fax:      modal.querySelector('#ve-fax').value.trim(),
          mail:     modal.querySelector('#ve-mail').value.trim(),
          address:  modal.querySelector('#ve-address').value.trim(),
          touroku:  modal.querySelector('#ve-touroku').value.trim(),
          furikomi: modal.querySelector('#ve-furikomi').value.trim(),
        },
        memo:   modal.querySelector('#ve-memo').value.trim(),
        search: modal.querySelector('#ve-search').value.trim(),
      };

      const contacts = readContacts().filter(c => Object.values(c).some(x => x));
      if(contacts.length) obj.contacts = contacts;

      return obj;
    }

    // フッターボタン
    modal.addEventListener('click', async (e) => {
      const a = e.target.closest('[data-action]');
      if(!a) return;
      const action = a.dataset.action;
      if(action === 'cancel' || action === 'close'){
        closeModal();
      }else if(action === 'config-pat'){
        await promptPat();
      }else if(action === 'save'){
        let payload;
        try{
          payload = collectForm();
        }catch(err){
          toast(err.message, true);
          return;
        }
        a.disabled = true;
        a.textContent = '保存中...';
        try{
          await saveVendor(payload, isNew, modal.querySelector('#ve-commit-msg').value.trim());
          toast(isNew ? `${payload.id} を採番・保存しました` : `${payload.id} を保存しました`);
          closeModal();
          if(typeof CONF.onSaved === 'function') CONF.onSaved(payload);
        }catch(err){
          a.disabled = false;
          a.textContent = isNew ? '採番して保存' : '保存（コミット）';
          toast('保存失敗: ' + err.message, true);
          console.error(err);
        }
      }
    });
  }

  /* 取引先1社をdata.jsonに書き戻す（最新を取得→更新→コミット） */
  async function saveVendor(payload, isNew, commitMsg){
    const { sha, data } = await fetchDataJson();
    const master = data['取引先マスター'] || (data['取引先マスター'] = []);

    if(isNew){
      payload.id = nextVendorId(master);
      // search が空ならIDだけ入れる
      if(!payload.search) payload.search = payload.id.toLowerCase() + ' ' + payload['略称'];
      master.push(payload);
    }else{
      const idx = master.findIndex(m => m.id === payload.id);
      if(idx < 0) throw new Error(`${payload.id} が見つかりません（リロードして再試行）`);
      // 既存のフィールド順を尊重しつつ、編集対象だけ上書き
      master[idx] = mergeKeepOrder(master[idx], payload);
    }

    // 最終更新を今日に
    data['最終更新'] = todayYmd();

    const msg = commitMsg || (isNew
      ? `取引先追加: ${payload.id} ${payload['略称']}`
      : `取引先更新: ${payload.id} ${payload['略称']}`);
    await commitDataJson(data, msg, sha);
    return payload;
  }

  function mergeKeepOrder(existing, patch){
    // フィールド順を保ちつつ patch を適用
    const out = {};
    const allKeys = new Set([...Object.keys(existing), ...Object.keys(patch)]);
    // 既存順を優先
    Object.keys(existing).forEach(k => {
      if(patch.hasOwnProperty(k)) out[k] = patch[k];
      else out[k] = existing[k];
      allKeys.delete(k);
    });
    // 新規キー
    allKeys.forEach(k => { out[k] = patch[k]; });
    return out;
  }

  function todayYmd(){
    const d = new Date();
    const pad = n => String(n).padStart(2,'0');
    return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
  }

  function esc(s){ return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

  /* ══════════════════════════════════════════════════════════════════════
     Phase 2: Eight CSV 連携・重複検出・マージモーダル
     ══════════════════════════════════════════════════════════════════════ */

  let EIGHT_CACHE = null;  // { records: [], loadedAt: ts }
  const EIGHT_TTL_MS = 60_000;

  const EIGHT_SOURCES = [
    'eight_export_latest.csv?v=' + Date.now(),
    'https://kameisatoru-svg.github.io/genba-navi/eight_export_latest.csv?v=' + Date.now(),
  ];

  async function loadEight(force){
    if(!force && EIGHT_CACHE && (Date.now() - EIGHT_CACHE.loadedAt) < EIGHT_TTL_MS){
      return EIGHT_CACHE.records;
    }
    let text = null;
    let lastErr = null;
    for(const u of EIGHT_SOURCES){
      try{
        const r = await fetch(u);
        if(!r.ok) throw new Error('HTTP ' + r.status);
        text = await r.text();
        break;
      }catch(e){ lastErr = e; }
    }
    if(!text) throw new Error('Eight CSV取得失敗: ' + (lastErr && lastErr.message));
    const records = parseEightCsv(text);
    EIGHT_CACHE = { records, loadedAt: Date.now() };
    return records;
  }

  function parseCsvRow(row){
    const result = [];
    let cur = '', inQ = false;
    for(let i = 0; i < row.length; i++){
      const c = row[i];
      if(c === '"'){
        if(inQ && row[i+1] === '"'){ cur += '"'; i++; }
        else inQ = !inQ;
      }else if(c === ',' && !inQ){ result.push(cur); cur = ''; }
      else cur += c;
    }
    result.push(cur);
    return result;
  }

  function parseEightCsv(text){
    const rows = text.split(/\r?\n/);
    let headerIdx = -1;
    for(let i = 0; i < rows.length; i++){
      if(rows[i].startsWith('会社名,') || rows[i].includes(',会社名,')){ headerIdx = i; break; }
    }
    if(headerIdx < 0) return [];
    const headers = parseCsvRow(rows[headerIdx]);
    const f = {};
    ['会社名','部署名','役職','氏名','e-mail','郵便番号','住所','TEL会社','TEL部門','TEL直通','Fax','携帯電話','URL','名刺交換日']
      .forEach(label => { f[label] = headers.indexOf(label); });

    const records = [];
    for(let i = headerIdx + 1; i < rows.length; i++){
      const row = rows[i];
      if(!row || !row.trim()) continue;
      const cols = parseCsvRow(row);
      const g = (k) => f[k] >= 0 && cols[f[k]] != null ? cols[f[k]].trim() : '';
      const rec = {
        company:      g('会社名'),
        dept:         g('部署名'),
        role:         g('役職'),
        name:         g('氏名'),
        mail:         g('e-mail'),
        zip:          g('郵便番号'),
        address:      g('住所'),
        tel:          g('TEL会社'),
        telDept:      g('TEL部門'),
        telDirect:    g('TEL直通'),
        fax:          g('Fax'),
        mobile:       g('携帯電話'),
        url:          g('URL'),
        exchangeDate: g('名刺交換日'),
      };
      if(rec.company || rec.name) records.push(rec);
    }
    return records;
  }

  /* ─── 正規化 ─── */
  function normalizeTel(s){
    return String(s||'').replace(/[^\d]/g, '');
  }
  const LEGAL_FORMS = [
    '株式会社','有限会社','合同会社','合資会社','合名会社',
    '社会福祉法人','医療法人','医療法人社団','学校法人','宗教法人',
    '一般社団法人','公益社団法人','一般財団法人','公益財団法人',
    '特定非営利活動法人','NPO法人','㈱','㈲','(株)','(有)','（株）','（有）',
  ];
  function normalizeCompany(s){
    if(!s) return '';
    let n = String(s).normalize('NFKC');
    n = n.replace(/[\s　]/g, '');
    LEGAL_FORMS.forEach(lf => { n = n.split(lf).join(''); });
    return n.toLowerCase();
  }

  /* ─── 重複検出: vendor ↔ Eight CSV ─── */
  function findDuplicateCandidates(vendor, eightRecords){
    if(!eightRecords || !eightRecords.length) return [];
    const c = vendor.contact || {};
    const vTels = new Set(
      [c.tel, c.mobile, c.fax].map(normalizeTel).filter(t => t.length >= 7)
    );
    const vName  = vendor['正式名称'] || vendor.name || '';
    const vRyaku = vendor['略称']     || vendor.ryaku || '';
    const vNameN  = normalizeCompany(vName);
    const vRyakuN = normalizeCompany(vRyaku);
    const cMailDomain = (c.mail || '').split('@')[1] || '';

    const candidates = [];
    for(const r of eightRecords){
      const eTels = new Set(
        [r.tel, r.telDept, r.telDirect, r.mobile, r.fax].map(normalizeTel).filter(t => t.length >= 7)
      );
      const reasons = [];
      let score = 0;

      // TEL正規化一致
      for(const vt of vTels){
        if(eTels.has(vt)){ reasons.push('TEL一致:' + vt); score += 10; break; }
      }

      // 社名類似
      const eNameN = normalizeCompany(r.company);
      if(eNameN && vNameN){
        if(eNameN === vNameN){ reasons.push('社名完全一致'); score += 8; }
        else if(eNameN.includes(vNameN) || vNameN.includes(eNameN)){ reasons.push('社名部分一致'); score += 5; }
        else if(vRyakuN && eNameN.includes(vRyakuN)){ reasons.push('略称含む'); score += 4; }
      }

      // メールドメイン一致
      if(cMailDomain && r.mail){
        const ed = r.mail.split('@')[1];
        if(ed && ed === cMailDomain){ reasons.push('mailドメイン一致'); score += 6; }
      }

      if(score >= 4) candidates.push({ record: r, reasons, score });
    }
    return candidates.sort((a, b) => b.score - a.score);
  }

  /* ──────────────────────────────────────────────────────────
     重複マージモーダル
     ────────────────────────────────────────────────────────── */
  async function openMergeModal(vendor){
    injectCss();
    const modal = openModal(buildMergeShell(vendor));
    let candidates = [];
    try{
      const records = await loadEight();
      candidates = findDuplicateCandidates(vendor, records);
      renderMergeCandidates(modal, vendor, candidates);
    }catch(err){
      const status = modal.querySelector('#ve-merge-status');
      status.innerHTML = `<span style="color:#dc2626;">読み込み失敗: ${esc(err.message)}</span>`;
      console.error(err);
    }
    bindMergeHandlers(modal, vendor, () => candidates);
  }

  function buildMergeShell(vendor){
    const ryaku = vendor['略称'] || vendor.ryaku || '';
    return `
      <div class="ve-modal">
        <div class="ve-modal-header">
          <h2>🔗 重複マージ — ${esc(vendor.id)} ${esc(ryaku)}</h2>
          <button class="ve-modal-close" data-action="close">×</button>
        </div>
        <div class="ve-modal-body">
          <div class="ve-merge-current">
            <b>現状の data.json:</b><br>
            ${esc(vendor['正式名称'] || vendor.name || '')}<br>
            <b>TEL</b> ${esc(vendor.contact?.tel || '—')} &nbsp;
            <b>携帯</b> ${esc(vendor.contact?.mobile || '—')} &nbsp;
            <b>mail</b> ${esc(vendor.contact?.mail || '—')}<br>
            <b>担当</b> ${esc(vendor.basic?.contact || '—')}
          </div>
          <div id="ve-merge-status" style="color:#666;font-size:12px;padding:6px 0 10px;">Eight CSV 読み込み中...</div>
          <div id="ve-merge-candidates"></div>
        </div>
        <div class="ve-modal-footer">
          <div style="flex:1;font-size:11px;color:#666;">採用区分を選んで「保存」で data.json にコミット</div>
          <button class="ve-btn" data-action="cancel" type="button">閉じる</button>
          <button class="ve-btn ve-btn-primary" data-action="save" type="button">採用分を保存</button>
        </div>
      </div>
    `;
  }

  function renderMergeCandidates(modal, vendor, candidates){
    const status = modal.querySelector('#ve-merge-status');
    const wrap = modal.querySelector('#ve-merge-candidates');
    if(!candidates.length){
      status.textContent = 'Eight CSV からの重複候補は見つかりませんでした。';
      wrap.innerHTML = '';
      return;
    }
    status.innerHTML = `<strong>${candidates.length}件</strong>の候補が見つかりました（スコア順）`;
    wrap.innerHTML = candidates.map((cand, i) => buildMergeCandidate(cand, i)).join('');
  }

  function buildMergeCandidate(cand, idx){
    const r = cand.record;
    const addrFull = (r.zip ? '〒' + r.zip + ' ' : '') + (r.address || '');
    return `
      <div class="ve-merge-card" data-idx="${idx}">
        <div class="ve-merge-card-head">
          <span class="ve-merge-tag">スコア ${cand.score}</span>
          <span style="font-size:12px;color:#1a7a30;font-weight:600;">${esc(cand.reasons.join(' / '))}</span>
        </div>
        <div class="ve-merge-meta">
          <div><b>会社</b>${esc(r.company)}</div>
          <div><b>氏名</b>${esc(r.name)} ${esc(r.dept || '')} ${esc(r.role || '')}</div>
          <div><b>TEL</b>${esc(r.tel || r.telDirect || '')}</div>
          <div><b>携帯</b>${esc(r.mobile)}</div>
          <div><b>mail</b>${esc(r.mail)}</div>
          <div><b>FAX</b>${esc(r.fax)}</div>
          <div style="grid-column:1/-1;"><b>住所</b>${esc(addrFull)}</div>
          <div><b>交換日</b>${esc(r.exchangeDate)}</div>
          <div><b>URL</b>${esc(r.url)}</div>
        </div>
        <div class="ve-merge-action">
          <label>採用区分:</label>
          <select data-action="adopt-select" data-idx="${idx}">
            <option value="reject" selected>却下(無視)</option>
            <option value="contact_update">contact更新(空欄を埋める)</option>
            <option value="contact_overwrite">contact上書き(強制)</option>
            <option value="contacts_add">contacts追加(別担当として)</option>
          </select>
        </div>
      </div>
    `;
  }

  function bindMergeHandlers(modal, vendor, getCandidates){
    modal.addEventListener('click', async (e) => {
      const a = e.target.closest('[data-action]');
      if(!a) return;
      const action = a.dataset.action;
      if(action === 'cancel' || action === 'close'){
        closeModal();
      }else if(action === 'save'){
        const candidates = getCandidates();
        const decisions = [];
        modal.querySelectorAll('select[data-action="adopt-select"]').forEach(sel => {
          const idx = parseInt(sel.dataset.idx, 10);
          const adopt = sel.value;
          if(adopt !== 'reject') decisions.push({ idx, adopt, candidate: candidates[idx] });
        });
        if(!decisions.length){
          toast('採用する候補がありません（すべて却下）', true);
          return;
        }
        a.disabled = true;
        a.textContent = '保存中...';
        try{
          const merged = applyMergeDecisions(vendor, decisions);
          await saveVendor(merged, false, `重複マージ: ${vendor.id} ${vendor['略称'] || vendor.ryaku || ''}`);
          toast(`${vendor.id} にマージしました（${decisions.length}件採用）`);
          closeModal();
          if(typeof CONF.onSaved === 'function') CONF.onSaved(merged);
        }catch(err){
          a.disabled = false;
          a.textContent = '採用分を保存';
          toast('マージ失敗: ' + err.message, true);
          console.error(err);
        }
      }
    });
  }

  function applyMergeDecisions(vendor, decisions){
    const out = JSON.parse(JSON.stringify({
      id: vendor.id,
      '略称': vendor['略称'] || vendor.ryaku || '',
      '正式名称': vendor['正式名称'] || vendor.name || '',
      rel: vendor.rel || [],
      type: vendor.type || [],
      basic: vendor.basic || { contact: '', rep: '' },
      contact: vendor.contact || {tel:'',mobile:'',fax:'',mail:'',address:'',touroku:'',furikomi:''},
      contacts: Array.isArray(vendor.contacts) ? vendor.contacts : [],
      memo: vendor.memo || '',
      search: vendor.search || '',
    }));

    for(const d of decisions){
      const r = d.candidate.record;
      if(d.adopt === 'contact_update' || d.adopt === 'contact_overwrite'){
        const force = (d.adopt === 'contact_overwrite');
        const apply = (k, v) => {
          if(!v) return;
          if(force || !out.contact[k]) out.contact[k] = v;
        };
        apply('tel',    r.tel || r.telDirect);
        apply('mobile', r.mobile);
        apply('fax',    r.fax);
        apply('mail',   r.mail);
        const fullAddr = (r.zip ? '〒' + r.zip + ' ' : '') + (r.address || '');
        if(fullAddr.trim()) apply('address', fullAddr.trim());
        // basic.contact が空なら担当者氏名を入れる
        if(!out.basic.contact && r.name){
          const roleSfx = r.role ? `(${r.role.trim()})` : '';
          out.basic.contact = `${r.name} 様${roleSfx}`;
        }
      }else if(d.adopt === 'contacts_add'){
        out.contacts.push({
          name:          r.name || '',
          dept:          r.dept || '',
          role:          r.role || '',
          tel:           r.tel || r.telDirect || '',
          mobile:        r.mobile || '',
          mail:          r.mail || '',
          fax:           r.fax || '',
          exchange_date: r.exchangeDate || '',
          source:        'Eight',
        });
      }
    }
    return out;
  }

  /* ──────────────────────────────────────────────────────────
     編集モーダル内 Eight CSV 検索パネル
     ────────────────────────────────────────────────────────── */
  function bindEightSearchPanel(modal, vEditing){
    const toggle = modal.querySelector('[data-action="toggle-eight"]');
    const panel = modal.querySelector('#ve-eight-panel');
    if(!toggle || !panel) return;

    toggle.addEventListener('click', async () => {
      const open = panel.style.display !== 'none';
      if(open){
        panel.style.display = 'none';
        toggle.textContent = toggle.dataset.label + ' ▼';
        return;
      }
      panel.style.display = 'block';
      toggle.textContent = toggle.dataset.label + ' ▲';
      // 初回ロード時に既存社名で検索
      const input = panel.querySelector('#ve-eight-search');
      if(!input.value){
        input.value = modal.querySelector('#ve-ryaku').value
                   || modal.querySelector('#ve-name').value || '';
      }
      input.focus();
      runEightSearch(modal);
    });

    const input = panel.querySelector('#ve-eight-search');
    let timer = null;
    input.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(() => runEightSearch(modal), 250);
    });
  }

  async function runEightSearch(modal){
    const input = modal.querySelector('#ve-eight-search');
    const results = modal.querySelector('#ve-eight-results');
    const q = (input.value || '').trim();
    if(!q){ results.innerHTML = '<div style="font-size:12px;color:#999;">検索ワードを入力</div>'; return; }
    results.innerHTML = '<div style="font-size:12px;color:#999;">読み込み中...</div>';
    let records;
    try{
      records = await loadEight();
    }catch(err){
      results.innerHTML = `<div style="font-size:12px;color:#dc2626;">${esc(err.message)}</div>`;
      return;
    }
    const qNorm = q.toLowerCase().normalize('NFKC');
    const qTel = normalizeTel(q);
    const hits = records.filter(r => {
      const s = (r.company + ' ' + r.name + ' ' + r.dept + ' ' + r.role + ' ' + r.mail + ' ' + r.address)
                .toLowerCase().normalize('NFKC');
      if(s.includes(qNorm)) return true;
      if(qTel.length >= 4){
        const allTels = [r.tel, r.telDept, r.telDirect, r.mobile, r.fax].map(normalizeTel).join(' ');
        if(allTels.includes(qTel)) return true;
      }
      return false;
    }).slice(0, 12);

    if(!hits.length){
      results.innerHTML = '<div style="font-size:12px;color:#999;">該当なし</div>';
      return;
    }
    results.innerHTML = hits.map((r, i) => `
      <div class="ve-eight-hit" data-eidx="${i}">
        <div class="ve-eight-hit-meta">
          <b>会社</b>${esc(r.company)} &nbsp; <b>氏名</b>${esc(r.name)}${r.role?'('+esc(r.role)+')':''}<br>
          <b>TEL</b>${esc(r.tel||r.telDirect||'')} &nbsp;
          <b>携帯</b>${esc(r.mobile)} &nbsp;
          <b>mail</b>${esc(r.mail)}<br>
          <b>住所</b>${esc((r.zip?'〒'+r.zip+' ':'') + (r.address||''))}
        </div>
        <button class="ve-eight-apply" data-action="apply-eight" data-eidx="${i}" type="button">この内容を取り込む</button>
      </div>
    `).join('');

    results.querySelectorAll('[data-action="apply-eight"]').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.eidx, 10);
        applyEightToForm(modal, hits[idx]);
      });
    });
  }

  function applyEightToForm(modal, r){
    const setIfEmpty = (id, val) => {
      if(!val) return;
      const el = modal.querySelector('#' + id);
      if(el && !el.value.trim()) el.value = val;
    };
    setIfEmpty('ve-name', r.company);
    setIfEmpty('ve-tel',     r.tel || r.telDirect);
    setIfEmpty('ve-mobile',  r.mobile);
    setIfEmpty('ve-fax',     r.fax);
    setIfEmpty('ve-mail',    r.mail);
    const addrFull = (r.zip ? '〒' + r.zip + ' ' : '') + (r.address || '');
    setIfEmpty('ve-address', addrFull.trim());
    // basic.contact が空なら担当者を埋める
    setIfEmpty('ve-basic-contact', r.name ? `${r.name} 様${r.role?'('+r.role.trim()+')':''}` : '');
    toast(`「${r.company || r.name}」を空欄に取り込みました`);
  }

  /* ══════════════════════════════════════════════════════════════════════
     Phase 3: 名刺画像OCR（Anthropic API直接呼び出し）
     ══════════════════════════════════════════════════════════════════════ */

  const OCR_MODEL = 'claude-sonnet-4-6';
  const OCR_PROMPT = `この名刺画像から取引先情報を抽出してください。
読み取れない項目は空文字列 "" を入れる。推測しない。

以下のJSONだけを返答してください（マークダウンコードブロック・前置きなど不要）:
{
  "company": "正式会社名（株式会社・有限会社などの法人格も含めて記載通り）",
  "dept": "部署名",
  "role": "役職",
  "name": "氏名（姓と名の間は半角スペース）",
  "name_kana": "氏名のフリガナ（あれば）",
  "mail": "メールアドレス",
  "tel": "代表電話番号",
  "tel_direct": "直通電話番号",
  "mobile": "携帯電話番号",
  "fax": "FAX番号",
  "zip": "郵便番号（ハイフン含む）",
  "address": "住所（〒は含めない）",
  "url": "ウェブサイトURL",
  "touroku": "インボイス登録番号（T+13桁）",
  "memo": "その他特記事項（事業内容・キャッチコピー等の重要情報のみ）"
}`;

  async function fileToBase64(file){
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        // data:image/jpeg;base64,xxxxx の xxxxx 部分だけ取り出す
        const result = reader.result;
        const comma = result.indexOf(',');
        resolve(result.substring(comma + 1));
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  /* 画像をリサイズ・JPEG圧縮（Anthropic 5MB制限対策） */
  async function resizeImageToBlob(file, maxLong, quality){
    const url = URL.createObjectURL(file);
    const img = await new Promise((resolve, reject) => {
      const i = new Image();
      i.onload = () => resolve(i);
      i.onerror = reject;
      i.src = url;
    });
    URL.revokeObjectURL(url);
    let scale = 1;
    const longSide = Math.max(img.naturalWidth, img.naturalHeight);
    if(longSide > maxLong) scale = maxLong / longSide;
    const w = Math.round(img.naturalWidth * scale);
    const h = Math.round(img.naturalHeight * scale);
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0, w, h);
    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => {
        if(!blob) reject(new Error('画像のJPEG変換に失敗'));
        else resolve(blob);
      }, 'image/jpeg', quality);
    });
  }

  /* OCR送信前に5MB以下になるまで段階的に圧縮 */
  async function prepareImageForOcr(file){
    const SIZE_LIMIT = 4_500_000;  // 5MB制限に対して余裕を持たせる
    // 元から小さい JPEG はそのまま
    if(file.size <= SIZE_LIMIT && file.type === 'image/jpeg'){
      return { blob: file, mediaType: 'image/jpeg', resized: false };
    }
    // 段階的リサイズ
    const steps = [
      { maxLong: 1568, quality: 0.85 },
      { maxLong: 1568, quality: 0.7 },
      { maxLong: 1200, quality: 0.75 },
      { maxLong: 1000, quality: 0.7 },
      { maxLong:  800, quality: 0.65 },
    ];
    for(const s of steps){
      const blob = await resizeImageToBlob(file, s.maxLong, s.quality);
      if(blob.size <= SIZE_LIMIT){
        return { blob, mediaType: 'image/jpeg', resized: true, info: s, finalSize: blob.size };
      }
    }
    throw new Error('5MB以下に圧縮できませんでした');
  }

  async function ocrBusinessCard(file){
    let apiKey = getAnthropicKey();
    if(!apiKey){
      apiKey = await promptAnthropicKey();
      if(!apiKey) throw new Error('APIキー未設定');
    }
    if(!['image/jpeg','image/png','image/webp','image/gif'].includes(file.type)){
      throw new Error(`非対応の画像形式: ${file.type}`);
    }

    const prep = await prepareImageForOcr(file);
    if(prep.resized){
      console.log('[OCR] 画像を圧縮:', file.size, '→', prep.finalSize, prep.info);
    }
    const b64 = await fileToBase64(prep.blob);

    const body = {
      model: OCR_MODEL,
      max_tokens: 1024,
      messages: [{
        role: 'user',
        content: [
          { type: 'image', source: { type: 'base64', media_type: prep.mediaType, data: b64 } },
          { type: 'text', text: OCR_PROMPT },
        ],
      }],
    };
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
        'anthropic-dangerous-direct-browser-access': 'true',
      },
      body: JSON.stringify(body),
    });
    if(!res.ok){
      let detail = '';
      try{ detail = (await res.json()).error?.message || ''; }catch(_){}
      throw new Error(`Anthropic API ${res.status}: ${detail || res.statusText}`);
    }
    const data = await res.json();
    const text = data.content?.[0]?.text || '';
    // JSON抽出（モデルが念のため余計な文字を入れた場合に備えて）
    const start = text.indexOf('{');
    const end = text.lastIndexOf('}');
    if(start < 0 || end < 0) throw new Error('OCR応答からJSONを取り出せませんでした');
    const json = text.substring(start, end + 1);
    let parsed;
    try{ parsed = JSON.parse(json); }
    catch(e){ throw new Error('OCR応答のJSONパース失敗: ' + e.message); }
    return parsed;
  }

  /* 既存業者照合: OCR結果 ↔ data.json取引先マスター */
  function findExistingVendorMatches(ocr, vendors){
    const ocrTel = [ocr.tel, ocr.tel_direct, ocr.mobile, ocr.fax].map(normalizeTel).filter(t => t.length >= 7);
    const ocrCompanyN = normalizeCompany(ocr.company || '');
    const ocrMailDomain = (ocr.mail || '').split('@')[1] || '';
    const ocrTouroku = (ocr.touroku || '').replace(/\s/g, '').toUpperCase();

    const hits = [];
    for(const v of (vendors || [])){
      const c = v.contact || v.contacts && v.contact || {};
      const vTel = [c.tel, c.mobile, c.fax].map(normalizeTel).filter(t => t.length >= 7);
      const vName  = v['正式名称'] || v.name || '';
      const vRyaku = v['略称']     || v.ryaku || '';
      const vNameN  = normalizeCompany(vName);
      const vRyakuN = normalizeCompany(vRyaku);
      const vTouroku = (c.touroku || '').replace(/\s/g, '').toUpperCase();
      const vMailDomain = (c.mail || '').split('@')[1] || '';
      const reasons = [];
      let score = 0;

      if(ocrTouroku && vTouroku && ocrTouroku === vTouroku){
        reasons.push('登録番号一致'); score += 20;
      }
      for(const t of ocrTel){
        if(vTel.includes(t)){ reasons.push('TEL一致:' + t); score += 10; break; }
      }
      if(ocrCompanyN && vNameN){
        if(ocrCompanyN === vNameN){ reasons.push('社名完全一致'); score += 8; }
        else if(vNameN.includes(ocrCompanyN) || ocrCompanyN.includes(vNameN)){ reasons.push('社名部分一致'); score += 5; }
        else if(vRyakuN && ocrCompanyN.includes(vRyakuN)){ reasons.push('略称含む'); score += 4; }
      }
      if(ocrMailDomain && vMailDomain && ocrMailDomain === vMailDomain){
        reasons.push('mailドメイン一致'); score += 6;
      }
      if(score >= 4) hits.push({ vendor: v, reasons, score });
    }
    return hits.sort((a, b) => b.score - a.score);
  }

  /* ──────────────────────────────────────────────────────────
     名刺登録モーダル
     ────────────────────────────────────────────────────────── */
  async function openMeishiRegister(vendors){
    injectCss();
    const modal = openModal(`
      <div class="ve-modal">
        <div class="ve-modal-header">
          <h2>📇 名刺登録（画像から自動読み取り）</h2>
          <button class="ve-modal-close" data-action="close">×</button>
        </div>
        <div class="ve-modal-body">
          <div id="ve-meishi-step1">
            <div class="ve-pat-warn" style="margin-bottom:12px;">
              名刺画像を選択 → Anthropic API でテキスト抽出 → 既存業者照合 → 編集モーダルに自動入力<br>
              ※ JPEG/PNG/WebP 対応・1枚ずつ処理
            </div>
            <div id="ve-drop" style="border:2px dashed #c8a96e;border-radius:10px;padding:30px;text-align:center;background:#fffbf0;cursor:pointer;">
              <div style="font-size:36px;margin-bottom:6px;">📷</div>
              <div style="font-weight:700;color:#1e2d40;">クリックして名刺画像を選択</div>
              <div style="font-size:12px;color:#888;margin-top:4px;">またはこのエリアに画像をドロップ</div>
              <input type="file" id="ve-meishi-file" accept="image/jpeg,image/png,image/webp" style="display:none;">
            </div>
            <div id="ve-meishi-preview" style="margin-top:12px;display:none;">
              <img id="ve-meishi-img" style="max-width:100%;max-height:300px;border:1px solid #ccc;border-radius:8px;display:block;margin:0 auto;">
              <div style="text-align:center;margin-top:10px;">
                <button class="ve-btn" data-action="reselect" type="button">画像を選び直す</button>
                <button class="ve-btn ve-btn-primary" data-action="ocr" type="button">✨ 名刺を読み取る</button>
              </div>
            </div>
          </div>
          <div id="ve-meishi-step2" style="display:none;">
            <div style="text-align:center;padding:40px;color:#666;">
              <div style="font-size:40px;margin-bottom:8px;">🔍</div>
              <div style="font-weight:700;">名刺を読み取り中...</div>
              <div style="font-size:12px;color:#888;margin-top:4px;">5〜15秒お待ちください</div>
            </div>
          </div>
          <div id="ve-meishi-step3" style="display:none;">
            <!-- OCR結果プレビューと照合結果が差し込まれる -->
          </div>
        </div>
        <div class="ve-modal-footer" id="ve-meishi-footer">
          <button class="ve-btn ve-btn-ghost" data-action="config-api" type="button">🤖 APIキー設定</button>
          <div style="flex:1;"></div>
          <button class="ve-btn" data-action="cancel" type="button">閉じる</button>
        </div>
      </div>
    `);

    let selectedFile = null;
    let ocrResult = null;
    let matches = [];

    const drop = modal.querySelector('#ve-drop');
    const fileInput = modal.querySelector('#ve-meishi-file');
    const preview = modal.querySelector('#ve-meishi-preview');
    const previewImg = modal.querySelector('#ve-meishi-img');

    function handleFile(file){
      if(!file) return;
      selectedFile = file;
      const url = URL.createObjectURL(file);
      previewImg.src = url;
      preview.style.display = 'block';
      drop.style.display = 'none';
    }
    drop.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', (e) => handleFile(e.target.files?.[0]));
    drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.style.background = '#fff3d4'; });
    drop.addEventListener('dragleave', () => { drop.style.background = '#fffbf0'; });
    drop.addEventListener('drop', (e) => {
      e.preventDefault();
      drop.style.background = '#fffbf0';
      handleFile(e.dataTransfer.files?.[0]);
    });

    modal.addEventListener('click', async (e) => {
      const a = e.target.closest('[data-action]');
      if(!a) return;
      const action = a.dataset.action;
      if(action === 'cancel' || action === 'close'){
        closeModal();
      }else if(action === 'config-api'){
        await promptAnthropicKey();
      }else if(action === 'reselect'){
        selectedFile = null;
        preview.style.display = 'none';
        drop.style.display = 'block';
        fileInput.value = '';
      }else if(action === 'ocr'){
        if(!selectedFile){ toast('画像が選択されていません', true); return; }
        modal.querySelector('#ve-meishi-step1').style.display = 'none';
        modal.querySelector('#ve-meishi-step2').style.display = 'block';
        try{
          ocrResult = await ocrBusinessCard(selectedFile);
          matches = findExistingVendorMatches(ocrResult, vendors || []);
          renderOcrResult(modal, ocrResult, matches, selectedFile);
        }catch(err){
          modal.querySelector('#ve-meishi-step2').style.display = 'none';
          modal.querySelector('#ve-meishi-step1').style.display = 'block';
          toast('読み取り失敗: ' + err.message, true);
          console.error(err);
        }
      }else if(action === 'open-existing'){
        const id = a.dataset.vid;
        const vendor = (vendors || []).find(v => v.id === id);
        if(!vendor){ toast('業者が見つかりません', true); return; }
        const merged = mergeOcrIntoVendor(vendor, ocrResult);
        closeModal();
        openEditModal(merged, 'edit');
      }else if(action === 'open-new'){
        closeModal();
        const blank = ocrToBlankVendor(ocrResult);
        openEditModal(blank, 'new');
      }else if(action === 'save-meishi'){
        if(!ocrResult){ toast('OCR結果がありません', true); return; }
        const btn = a;
        btn.disabled = true;
        const orig = btn.textContent;
        btn.textContent = '保存中...';
        try{
          const saved = await saveMeishiCard(ocrResult);
          toast(`名刺帳に保存しました: ${saved.company || saved.name || '(無名)'}`);
          closeModal();
          if(typeof CONF.onSaved === 'function'){
            try{ CONF.onSaved({ type:'meishi', card: saved }); }catch(_){}
          }
        }catch(err){
          btn.disabled = false;
          btn.textContent = orig;
          toast('保存失敗: ' + err.message, true);
          console.error(err);
        }
      }
    });
  }

  /* OCR結果を data.json["名刺"] 配列に追記コミット
     スキーマ：CSV record と同形（company/dept/role/name/mail/zip/address/tel/telDirect/fax/mobile/url/exchangeDate）
     + touroku / memo / source / createdAt を持つ */
  async function saveMeishiCard(ocr){
    const { sha, data } = await fetchDataJson();
    if(!Array.isArray(data['名刺'])) data['名刺'] = [];
    const fullAddr = `${ocr.zip ? '〒'+ocr.zip+' ' : ''}${ocr.address || ''}`.trim();
    const today = todayYmd();
    const card = {
      company:      ocr.company || '',
      dept:         ocr.dept || '',
      role:         ocr.role || '',
      name:         ocr.name || '',
      mail:         ocr.mail || '',
      zip:          ocr.zip || '',
      address:      ocr.address || fullAddr,
      tel:          ocr.tel || '',
      telDirect:    ocr.tel_direct || '',
      fax:          ocr.fax || '',
      mobile:       ocr.mobile || '',
      url:          ocr.url || '',
      exchangeDate: today,
      touroku:      ocr.touroku || '',
      memo:         ocr.memo || '',
      source:       '名刺OCR',
      createdAt:    today,
    };
    data['名刺'].push(card);
    data['最終更新'] = today;
    const msg = `名刺追加: ${card.company || '(社名なし)'} / ${card.name || '(氏名なし)'}`;
    await commitDataJson(data, msg, sha);
    return card;
  }

  function renderOcrResult(modal, ocr, matches, file){
    modal.querySelector('#ve-meishi-step2').style.display = 'none';
    const step3 = modal.querySelector('#ve-meishi-step3');
    step3.style.display = 'block';

    const previewUrl = URL.createObjectURL(file);
    const ocrFields = [
      ['会社名', ocr.company],
      ['部署', ocr.dept],
      ['役職', ocr.role],
      ['氏名', ocr.name],
      ['mail', ocr.mail],
      ['TEL', ocr.tel],
      ['直通', ocr.tel_direct],
      ['携帯', ocr.mobile],
      ['FAX', ocr.fax],
      ['住所', `${ocr.zip ? '〒'+ocr.zip+' ' : ''}${ocr.address || ''}`.trim()],
      ['URL', ocr.url],
      ['登録番号', ocr.touroku],
    ].filter(([_, v]) => v);

    const ocrHtml = `
      <div class="ve-section-title">📋 OCR結果</div>
      <div style="display:grid;grid-template-columns:120px 1fr;gap:4px 12px;background:#f8f9fb;padding:12px;border-radius:8px;font-size:13px;margin-bottom:12px;">
        ${ocrFields.map(([k,v]) => `<div style="color:#666;font-weight:600;">${k}</div><div>${esc(v)}</div>`).join('')}
        ${ocr.memo ? `<div style="color:#666;font-weight:600;grid-column:1/-1;">メモ</div><div style="grid-column:1/-1;font-size:12px;color:#555;">${esc(ocr.memo)}</div>` : ''}
      </div>
    `;

    let matchHtml = '';
    if(matches.length){
      matchHtml = `
        <div class="ve-section-title">🎯 既存業者に類似 (${matches.length}件)</div>
        ${matches.slice(0,5).map(m => `
          <div class="ve-merge-card">
            <div class="ve-merge-card-head">
              <span class="ve-merge-tag">スコア ${m.score}</span>
              <strong style="color:#1e2d40;">${esc(m.vendor.id)} ${esc(m.vendor['略称'] || m.vendor.ryaku || '')}</strong>
              <span style="font-size:12px;color:#1a7a30;">${esc(m.reasons.join(' / '))}</span>
            </div>
            <div style="font-size:12px;color:#555;margin-bottom:6px;">${esc(m.vendor['正式名称'] || m.vendor.name || '')}</div>
            <button class="ve-btn ve-btn-primary ve-btn-sm" data-action="open-existing" data-vid="${esc(m.vendor.id)}" type="button">この業者にOCR結果をマージして編集 →</button>
          </div>
        `).join('')}
        <div style="text-align:center;margin-top:12px;color:#888;font-size:12px;">— または —</div>
      `;
    }

    step3.innerHTML = `
      <div style="display:grid;grid-template-columns:160px 1fr;gap:14px;margin-bottom:14px;align-items:start;">
        <img src="${previewUrl}" style="width:100%;border:1px solid #ccc;border-radius:8px;">
        <div>${ocrHtml}</div>
      </div>
      ${matchHtml}
      <div style="text-align:center;margin-top:14px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
        <button class="ve-btn" data-action="save-meishi" type="button" style="font-size:14px;padding:12px 20px;background:#1a7a30;color:#fff;border-color:#155a23;">
          📇 名刺として保存（マスター登録なし）
        </button>
        <button class="ve-btn ve-btn-primary" data-action="open-new" type="button" style="font-size:14px;padding:12px 20px;">
          ➕ 新規取引先として登録（採番）
        </button>
      </div>
    `;
  }

  /* OCR結果を空のvendorに反映（新規登録用） */
  function ocrToBlankVendor(ocr){
    const fullAddr = `${ocr.zip ? '〒'+ocr.zip+' ' : ''}${ocr.address || ''}`.trim();
    const roleSfx = ocr.role ? `(${ocr.role.trim()})` : '';
    return {
      id: '',
      '略称': '', // ユーザーが編集モーダルで入力
      '正式名称': ocr.company || '',
      rel: [],
      type: [],
      basic: {
        contact: ocr.name ? `${ocr.name} 様${roleSfx}` : '',
        rep: '',
      },
      contact: {
        tel:      ocr.tel || ocr.tel_direct || '',
        mobile:   ocr.mobile || '',
        fax:      ocr.fax || '',
        mail:     ocr.mail || '',
        address:  fullAddr,
        touroku:  ocr.touroku || '',
        furikomi: '',
      },
      contacts: [],
      memo: ocr.memo || '',
      search: '',
    };
  }

  /* OCR結果を既存業者にマージ（空欄補完優先・contact既値は維持） */
  function mergeOcrIntoVendor(vendor, ocr){
    const out = JSON.parse(JSON.stringify({
      id: vendor.id,
      '略称': vendor['略称'] || vendor.ryaku || '',
      '正式名称': vendor['正式名称'] || vendor.name || '',
      rel: vendor.rel || [],
      type: vendor.type || [],
      basic: vendor.basic || { contact: '', rep: '' },
      contact: vendor.contact || {tel:'',mobile:'',fax:'',mail:'',address:'',touroku:'',furikomi:''},
      contacts: Array.isArray(vendor.contacts) ? vendor.contacts : [],
      memo: vendor.memo || '',
      search: vendor.search || '',
    }));
    // 空欄のみ埋める
    const fill = (obj, k, v) => { if(v && !obj[k]) obj[k] = v; };
    fill(out.contact, 'tel',      ocr.tel || ocr.tel_direct);
    fill(out.contact, 'mobile',   ocr.mobile);
    fill(out.contact, 'fax',      ocr.fax);
    fill(out.contact, 'mail',     ocr.mail);
    fill(out.contact, 'touroku',  ocr.touroku);
    const fullAddr = `${ocr.zip ? '〒'+ocr.zip+' ' : ''}${ocr.address || ''}`.trim();
    fill(out.contact, 'address',  fullAddr);

    // basic.contact が空なら担当者氏名を入れる
    if(!out.basic.contact && ocr.name){
      const roleSfx = ocr.role ? `(${ocr.role.trim()})` : '';
      out.basic.contact = `${ocr.name} 様${roleSfx}`;
    }else if(out.basic.contact && ocr.name && !out.basic.contact.includes(ocr.name)){
      // 別の担当者なら contacts に追加
      out.contacts.push({
        name: ocr.name || '',
        dept: ocr.dept || '',
        role: ocr.role || '',
        tel:  ocr.tel_direct || ocr.tel || '',
        mobile: ocr.mobile || '',
        mail: ocr.mail || '',
        fax: ocr.fax || '',
        exchange_date: '',
        source: '名刺OCR',
      });
    }
    return out;
  }

  /* ──────────────────────────────────────────────────────────
     公開API
     ────────────────────────────────────────────────────────── */
  window.vendorEditor = {
    init(opts){
      Object.assign(CONF, opts || {});
      injectCss();
    },
    openEdit(vendor){ openEditModal(vendor, 'edit'); },
    openNew(prefilled){
      // 任意の初期値を受け取れる（Eight CSV行 / OCR結果からの新規登録などに使う）
      const base = {
        id:'', '略称':'', '正式名称':'',
        rel:[], type:[],
        basic:{contact:'',rep:''},
        contact:{tel:'',mobile:'',fax:'',mail:'',address:'',touroku:'',furikomi:''},
        contacts:[], memo:'', search:'',
      };
      openEditModal(Object.assign(base, prefilled || {}), 'new');
    },
    openMerge(vendor){ openMergeModal(vendor); },
    openMeishiRegister(vendors){ openMeishiRegister(vendors); },
    configPat: promptPat,
    configAnthropicKey: promptAnthropicKey,
    toast,
    // Eight CSV
    loadEight,
    findDuplicateCandidates,
    // OCR
    ocrBusinessCard,
    findExistingVendorMatches,
    // Phase 2+ で外から再利用するため
    _internal: { fetchDataJson, commitDataJson, nextVendorId, getPat, setPat,
      getAnthropicKey, setAnthropicKey,
      normalizeTel, normalizeCompany, parseEightCsv },
  };
})();
