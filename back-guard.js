/* =========================================
   現場ナビ 戻るボタンガード  back-guard.js
   作成日：2026/6/25

   目的：Android の「デフォルトの戻るボタン（ハードウェア／ジェスチャー）」を
         1回押しただけでアプリ／ページが閉じてしまうのを防ぐ。
         1回目 … トーストで案内（誤操作防止）
         2回目（2秒以内）… 実行
           ・ホーム（index.html）         → 現場ナビを終了
           ・現場ナビ内の各アプリ          → ホーム（index.html）へ戻る

   使い方：各 HTML の </body> 直前で
           <script src="back-guard.js"></script>
         を読み込むだけ。モードはファイル名から自動判定する。
         （明示したい場合は読み込み前に window.__backGuardMode = 'home' | 'app'）
   ========================================= */
(function () {
  'use strict';
  if (window.__backGuardInstalled) return;       // 二重読み込み防止
  window.__backGuardInstalled = true;

  // ── モード判定 ───────────────────────────
  // index.html もしくはディレクトリ直下（/ で終わる）= ホーム（終了モード）
  var path = location.pathname;
  var file = path.substring(path.lastIndexOf('/') + 1).toLowerCase();
  var isHome = (window.__backGuardMode === 'home') ||
               (window.__backGuardMode !== 'app' &&
                (file === '' || file === 'index.html'));

  // ホームの場所（各アプリは同じディレクトリの index.html へ戻る）
  var HOME_URL = path.substring(0, path.lastIndexOf('/') + 1) + 'index.html';

  var MSG = isHome
    ? 'もう一度戻ると現場ナビを終了します'
    : 'もう一度戻るとホームに戻ります';

  var WINDOW_MS = 2000;   // 2回目を受け付ける猶予

  // ── トースト用スタイルを注入 ──────────────
  var style = document.createElement('style');
  style.textContent =
    '#__bgToast{' +
      'position:fixed;left:50%;bottom:calc(28px + env(safe-area-inset-bottom,0));' +
      'transform:translateX(-50%) translateY(12px);' +
      'background:rgba(20,30,45,0.94);color:#fff;' +
      'font-size:14px;font-weight:600;line-height:1.4;letter-spacing:0.02em;' +
      'padding:12px 20px;border-radius:24px;' +
      'box-shadow:0 6px 20px rgba(0,0,0,0.35);' +
      'max-width:88vw;text-align:center;white-space:nowrap;' +
      'z-index:2147483647;pointer-events:none;' +
      'opacity:0;transition:opacity .18s ease,transform .18s ease;' +
    '}' +
    '#__bgToast.show{opacity:1;transform:translateX(-50%) translateY(0);}';
  (document.head || document.documentElement).appendChild(style);

  var toast = null, hideTimer = null;
  function showToast() {
    if (!toast) {
      toast = document.createElement('div');
      toast.id = '__bgToast';
      toast.setAttribute('role', 'status');
      toast.setAttribute('aria-live', 'polite');
      toast.textContent = MSG;
      (document.body || document.documentElement).appendChild(toast);
    }
    // reflow を挟んで確実にトランジションさせる
    void toast.offsetWidth;
    toast.classList.add('show');
    clearTimeout(hideTimer);
    hideTimer = setTimeout(function () {
      if (toast) toast.classList.remove('show');
    }, WINDOW_MS);
  }
  function hideToast() {
    if (toast) toast.classList.remove('show');
  }

  // ── 戻るガード本体 ───────────────────────
  var armed = false, armTimer = null;

  function pushGuard() {
    try { history.pushState({ __backGuard: true }, ''); } catch (e) {}
  }

  // ページ表示時にガード用の履歴エントリを積む
  pushGuard();
  // bfcache から復帰したときも積み直す
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) { armed = false; pushGuard(); }
  });

  window.addEventListener('popstate', function () {
    if (armed) {
      // ── 2回目：実行 ──
      armed = false;
      clearTimeout(armTimer);
      hideToast();
      if (isHome) {
        // PWA / standalone では履歴を戻ることでアプリが閉じる
        history.back();
      } else {
        location.href = HOME_URL;
      }
      return;
    }
    // ── 1回目：案内して、もう一度ガードを積む ──
    armed = true;
    showToast();
    pushGuard();
    clearTimeout(armTimer);
    armTimer = setTimeout(function () { armed = false; }, WINDOW_MS);
  });
})();
