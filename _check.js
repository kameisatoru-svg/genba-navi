
const LOGO_B64 = 'data:image/png;base64,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';
const DATA_JSON_URL = 'https://kameisatoru-svg.github.io/genba-navi/data.json';

// ── 状態 ──
let workItems = ['', '', ''];
let photos = [
  {label:'【施工前】', data:''},
  {label:'【施工後】', data:''}
];
let pickTargetIdx = -1;
let ankenData = null;
let ankenDataLoaded = false;

function escH(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function escAttr(s){return String(s||'').replace(/'/g,"\\'").replace(/"/g,'&quot;');}

function fmtDateJP(iso){
  if(!iso) return '';
  const d = new Date(iso+'T00:00:00');
  if(isNaN(d)) return iso;
  return `${d.getFullYear()}年${d.getMonth()+1}月${d.getDate()}日`;
}

// ── タイトル（PDFファイル名）更新 ──
function updateDocTitle(){
  const ankenKey = (document.getElementById('ankenKey').value||'').trim();
  const suffix = (document.getElementById('fileSuffix').value||'').trim();
  let fname;
  if(ankenKey){
    fname = suffix ? `完_${suffix}_${ankenKey}` : `完_${ankenKey}`;
  } else {
    fname = '工事完了報告書';
  }
  document.title = fname;
}

// ── 工事内容エディタ描画 ──
function renderWorkEditor(){
  const el = document.getElementById('work-editor');
  el.innerHTML = workItems.map((w,i)=>`
    <div class="work-row">
      <span class="wnum">${i+1}.</span>
      <input type="text" value="${escH(w)}" placeholder="工事内容を入力" oninput="workItems[${i}]=this.value;render()">
      <button class="del-btn" onclick="removeWorkRow(${i})" title="削除">✕</button>
    </div>`).join('');
}
function addWorkRow(){ workItems.push(''); renderWorkEditor(); render(); }
function removeWorkRow(i){ workItems.splice(i,1); if(workItems.length===0) workItems.push(''); renderWorkEditor(); render(); }

// ── 写真エディタ描画 ──
function renderPhotoEditor(){
  const el = document.getElementById('photo-editor');
  el.innerHTML = photos.map((p,i)=>`
    <div class="photo-edit">
      <div class="photo-edit-head">
        <input type="text" value="${escH(p.label)}" placeholder="ラベル（例：【施工前】）" oninput="photos[${i}].label=this.value;render()">
        <button class="del-btn" onclick="removePhotoBlock(${i})" title="この写真枠を削除">✕</button>
      </div>
      <div class="photo-drop" onclick="pickPhoto(${i})">
        ${p.data
          ? `<img src="${p.data}" alt=""><button class="photo-clear" onclick="event.stopPropagation();clearPhoto(${i})" title="写真を消す">✕</button>`
          : '📷 タップして写真を選択<br>（撮影・ライブラリ）'}
      </div>
    </div>`).join('');
}
function addPhotoBlock(){ photos.push({label:'【施工写真】', data:''}); renderPhotoEditor(); render(); }
function removePhotoBlock(i){ photos.splice(i,1); renderPhotoEditor(); render(); }
function clearPhoto(i){ photos[i].data=''; renderPhotoEditor(); render(); }
function pickPhoto(i){ pickTargetIdx=i; document.getElementById('photo-file-input').click(); }

function handlePhotoPick(event){
  const file = event.target.files[0];
  event.target.value = '';
  if(!file || pickTargetIdx<0) return;
  const reader = new FileReader();
  reader.onload = e=>{
    const img = new Image();
    img.onload = ()=>{
      const MAX = 1200;
      let w = img.width, h = img.height;
      if(w>MAX || h>MAX){ const s=Math.min(MAX/w, MAX/h); w=Math.round(w*s); h=Math.round(h*s); }
      const canvas = document.createElement('canvas');
      canvas.width=w; canvas.height=h;
      canvas.getContext('2d').drawImage(img,0,0,w,h);
      photos[pickTargetIdx].data = canvas.toDataURL('image/jpeg', 0.78);
      renderPhotoEditor();
      render();
    };
    img.src = e.target.result;
  };
  reader.readAsDataURL(file);
}

// ── プレビュー描画 ──
function render(){
  const atena = document.getElementById('atena').value;
  const dateStr = fmtDateJP(document.getElementById('hakkoDate').value);
  const kojimei = document.getElementById('kojimei').value;
  const kojiloc = document.getElementById('kojiloc').value;
  const kojiperiod = document.getElementById('kojiperiod').value;
  const greeting = document.getElementById('greeting').value;
  const tantou = (document.getElementById('tantou').value||'').trim();

  const workHTML = workItems
    .map(w=>w.trim()).filter(Boolean)
    .map((w,i)=>`<li data-n="${i+1}">${escH(w)}</li>`).join('') || '<li data-n="1" style="color:#aaa;">（工事内容を入力してください）</li>';

  const photoHTML = photos.map(p=>{
    const inner = p.data
      ? `<img src="${p.data}" alt="">`
      : '<span class="kh-ph-empty">写真未選択</span>';
    return `<div class="kh-photo-block">
      <div class="kh-photo-lbl">${escH(p.label)}</div>
      <div class="kh-photo-frame">${inner}</div>
    </div>`;
  }).join('');

  const footerInfo = `株式会社アート・レイズ　〒874-0829　大分県別府市上原町13番25号${tantou?`　担当：${escH(tantou)}`:''}`;

  document.getElementById('doc-page').innerHTML = `
    <div class="kh-header">
      <h1>工事完了報告書</h1>
      <span class="kh-date">${escH(dateStr)}</span>
    </div>
    <div class="kh-divider"></div>
    <div class="kh-addressee-block">
      <div class="kh-addressee">${escH(atena)||'&nbsp;'}</div>
      <p class="kh-greeting">${escH(greeting).replace(/\n/g,'<br>')}</p>
    </div>
    <table class="kh-overview">
      <tr><td class="lbl">工 事 名</td><td>${escH(kojimei)}</td></tr>
      <tr><td class="lbl">工事場所</td><td>${escH(kojiloc)}</td></tr>
      <tr><td class="lbl">工事期間</td><td>${escH(kojiperiod)}</td></tr>
    </table>
    <div class="kh-sec">■ 工事内容</div>
    <ul class="kh-work-list">${workHTML}</ul>
    <div class="kh-photo-sec">
      <div class="kh-sec">■ 施工写真</div>
      <div style="height:8px"></div>
      <div class="kh-photos">${photoHTML}</div>
    </div>
    <div class="kh-footer">
      <img src="${LOGO_B64}" alt="Art-rays">
      <div class="kh-footer-info">${footerInfo}</div>
    </div>`;
  scalePreview();
}

function clearAllData(){
  if(!confirm('入力内容をすべてクリアしますか？')) return;
  document.getElementById('ankenKey').value='';
  document.getElementById('fileSuffix').value='';
  document.getElementById('atena').value='';
  document.getElementById('kojimei').value='';
  document.getElementById('kojiloc').value='';
  document.getElementById('kojiperiod').value='';
  document.getElementById('greeting').value='下記の工事が完了いたしましたのでご報告申し上げます。';
  document.getElementById('tantou').value='';
  workItems = ['', '', ''];
  photos = [{label:'【施工前】',data:''},{label:'【施工後】',data:''}];
  renderWorkEditor(); renderPhotoEditor(); updateDocTitle(); render();
}

// ── プレビュー スケーリング ──
function scalePreview(){
  const area=document.getElementById('preview-area');
  const inner=document.getElementById('preview-inner');
  const page=document.getElementById('doc-page');
  if(!page)return;
  const PAD=20;
  const available=area.clientWidth-PAD*2;
  if(available<=0)return;
  const scale=Math.min(1,available/794);
  inner.style.transform=`scale(${scale})`;
  inner.style.width=(794*scale)+'px';
  inner.style.marginBottom=`-${(1-scale)*page.offsetHeight}px`;
}

// ── ⋮メニュー ──
function toggleTopMenu(e){
  e.stopPropagation();
  const m=document.getElementById('top-menu');
  m.style.display = m.style.display==='none' ? 'block' : 'none';
}
function closeTopMenu(){ document.getElementById('top-menu').style.display='none'; }
document.addEventListener('click', e=>{
  const m=document.getElementById('top-menu'), b=document.getElementById('tb-menu-btn');
  if(m.style.display==='block' && !m.contains(e.target) && !b.contains(e.target)) closeTopMenu();
});

// ── PDF保存 ──
function loadHtml2Pdf(){
  return new Promise((resolve,reject)=>{
    if(window.html2pdf){ resolve(window.html2pdf); return; }
    const s=document.createElement('script');
    s.src='https://cdn.jsdelivr.net/npm/html2pdf.js@0.10.1/dist/html2pdf.bundle.min.js';
    s.onload=()=>resolve(window.html2pdf);
    s.onerror=()=>reject(new Error('html2pdf.js の読み込みに失敗しました'));
    document.head.appendChild(s);
  });
}
async function savePDF(){
  const btn=document.getElementById('tb-savepdf-btn');
  const label=btn?btn.querySelector('.tb-label'):null;
  const labelText=label?label.textContent:'';
  if(label) label.textContent='生成中…';
  if(btn) btn.disabled=true;
  try{
    const html2pdfFn=await loadHtml2Pdf();
    const previewInner=document.getElementById('preview-inner');
    const clone=previewInner.cloneNode(true);
    clone.style.transform='none';
    clone.style.width='auto';
    clone.style.marginBottom='0';
    clone.querySelectorAll('.doc-page').forEach(pg=>{
      pg.style.boxShadow='none';
      pg.style.margin='0 auto';
    });
    const fileBase=(document.title||'工事完了報告書').replace(/[\\\/:*?"<>|]/g,'_');
    const opt={
      margin:0,
      filename:fileBase+'.pdf',
      image:{type:'jpeg',quality:0.78},
      html2canvas:{scale:1.5,useCORS:true,backgroundColor:'#ffffff',logging:false},
      jsPDF:{unit:'mm',format:'a4',orientation:'portrait',compress:true},
      pagebreak:{mode:['css','legacy']}
    };
    await html2pdfFn().set(opt).from(clone).save();
  }catch(err){
    console.error(err);
    alert('PDF保存に失敗しました：'+(err.message||err));
  }finally{
    if(label) label.textContent=labelText;
    if(btn) btn.disabled=false;
  }
}

// 標準出力HTML（プレビューDOM＋スタイル＋再編集用の埋め込みデータ）を生成
function buildExportHTML(forPrint){
  const previewInner=document.getElementById('preview-inner');
  const styles=Array.from(document.querySelectorAll('style')).map(s=>s.outerHTML).join('\n');
  // 埋め込みJSON：'<' をエスケープして 