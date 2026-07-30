/**
 * 原価管理Sheets API（Apps Script ウェブアプリ）
 *
 * artrays-genka MCP サーバーの接続先。スプレッドシートに束縛された
 * コンテナバインド スクリプトとして貼り付け、ウェブアプリとしてデプロイする。
 * 手順は mcp/README_genka.md を参照。
 *
 * 設計
 *  - RC-26-NNN の採番は LockService で排他する（二重採番を構造的に防ぐ）
 *  - 追記は 日付|店舗名|金額|品目 の重複キーで弾く（貼り直しの二重計上を防ぐ）
 *  - トークンが一致しないリクエストは一切処理しない
 */

var SHEET_NAME = '原価管理';
var HEADER_ROWS = 1;          // 1行目はヘッダー
var COL_COUNT = 13;           // A〜M
var RC_PREFIX = 'RC-26-';
var LOCK_WAIT_MS = 30000;

// ---------------------------------------------------------------- entry

function doGet(e) {
  return handle(e, (e && e.parameter) || {});
}

function doPost(e) {
  var params = (e && e.parameter) || {};
  if (e && e.postData && e.postData.contents) {
    try {
      var body = JSON.parse(e.postData.contents);
      for (var k in body) params[k] = body[k];
    } catch (err) {
      return json({ ok: false, error: 'リクエストボディがJSONとして読めません: ' + err });
    }
  }
  return handle(e, params);
}

function handle(e, params) {
  try {
    var expected = PropertiesService.getScriptProperties().getProperty('API_TOKEN');
    if (!expected) {
      return json({ ok: false, error: 'スクリプトプロパティ API_TOKEN が未設定です' });
    }
    if (params.token !== expected) {
      return json({ ok: false, error: '認証に失敗しました' });
    }
    switch (params.action) {
      case 'ping':     return json(actionPing());
      case 'read':     return json(actionRead(params));
      case 'next_rc':  return json(actionNextRc());
      case 'append':   return json(actionAppend(params));
      default:
        return json({ ok: false, error: '未知の action: ' + params.action });
    }
  } catch (err) {
    return json({ ok: false, error: String(err && err.stack ? err.stack : err) });
  }
}

function json(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// ---------------------------------------------------------------- helpers

function getSheet() {
  var sh = SpreadsheetApp.getActive().getSheetByName(SHEET_NAME);
  if (!sh) throw new Error('シート『' + SHEET_NAME + '』が見つかりません');
  return sh;
}

function readAll(sh) {
  var last = sh.getLastRow();
  if (last <= HEADER_ROWS) return [];
  return sh.getRange(HEADER_ROWS + 1, 1, last - HEADER_ROWS, COL_COUNT).getDisplayValues();
}

function rcNumber(id) {
  var m = String(id || '').match(/^RC-26-(\d+)$/);
  return m ? parseInt(m[1], 10) : 0;
}

function maxRc(rows) {
  var max = 0;
  for (var i = 0; i < rows.length; i++) max = Math.max(max, rcNumber(rows[i][0]));
  return max;
}

/** 二重計上の判定キー: 日付|店舗名|金額|品目 */
function dupKey(date, shop, amount, item) {
  var n = String(amount).replace(/[^0-9.-]/g, '');
  return [String(date).trim(), String(shop).trim(), n, String(item).trim()].join('|');
}

// ---------------------------------------------------------------- actions

function actionPing() {
  var sh = getSheet();
  var rows = readAll(sh);
  return {
    ok: true,
    sheet: SHEET_NAME,
    spreadsheet: SpreadsheetApp.getActive().getName(),
    rows: rows.length,
    lastRC: rows.length ? RC_PREFIX + ('000' + maxRc(rows)).slice(-3) : null,
    nextRC: RC_PREFIX + ('000' + (maxRc(rows) + 1)).slice(-3)
  };
}

function actionNextRc() {
  var rows = readAll(getSheet());
  return { ok: true, nextRC: RC_PREFIX + ('000' + (maxRc(rows) + 1)).slice(-3) };
}

/**
 * 明細を返す。params で絞り込める:
 *   anken  … B列（案件番号）の完全一致
 *   month  … D列（日付）が YYYY-MM で始まる行
 *   kamoku … H列（勘定科目）の完全一致
 */
function actionRead(params) {
  var rows = readAll(getSheet());
  var out = [];
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    if (params.anken && String(r[1]).trim() !== String(params.anken).trim()) continue;
    if (params.month && String(r[3]).indexOf(String(params.month)) !== 0) continue;
    if (params.kamoku && String(r[7]).trim() !== String(params.kamoku).trim()) continue;
    out.push(r);
  }
  return { ok: true, count: out.length, total: rows.length, rows: out };
}

/**
 * 行を追記する。A列(RC)は渡さない — ここで採番する。
 * params.rows … [[案件番号,現場名,日付,店舗名,品目,金額,勘定科目,原価区分,
 *                 支払方法,ソース,備考,登録日], ...]（12列・B〜M相当）
 * params.dryRun … true なら採番結果だけ返して書き込まない
 */
function actionAppend(params) {
  var incoming = params.rows;
  if (!incoming || !incoming.length) return { ok: false, error: 'rows が空です' };

  var lock = LockService.getScriptLock();
  if (!lock.tryLock(LOCK_WAIT_MS)) {
    return { ok: false, error: '他の処理が書き込み中のためロックを取得できませんでした' };
  }
  try {
    var sh = getSheet();
    var existing = readAll(sh);
    var seen = {};
    for (var i = 0; i < existing.length; i++) {
      var e = existing[i];
      seen[dupKey(e[3], e[4], e[6], e[5])] = e[0];
    }

    var next = maxRc(existing) + 1;
    var toWrite = [], assigned = [], skipped = [];

    for (var j = 0; j < incoming.length; j++) {
      var r = incoming[j];
      if (r.length !== COL_COUNT - 1) {
        return { ok: false, error: '行 ' + (j + 1) + ' の列数が ' + (COL_COUNT - 1) + ' ではありません（' + r.length + '）' };
      }
      var key = dupKey(r[2], r[3], r[5], r[4]);
      if (seen[key]) {
        skipped.push({ index: j, reason: '既存行と重複', 既存RC: seen[key],
                       日付: r[2], 店舗名: r[3], 金額: r[5] });
        continue;
      }
      var rc = RC_PREFIX + ('000' + next).slice(-3);
      next++;
      seen[key] = rc;
      assigned.push({ index: j, RC: rc, 案件番号: r[0], 日付: r[2],
                      店舗名: r[3], 金額: r[5] });
      toWrite.push([rc].concat(r));
    }

    if (!params.dryRun && toWrite.length) {
      sh.getRange(sh.getLastRow() + 1, 1, toWrite.length, COL_COUNT).setValues(toWrite);
      SpreadsheetApp.flush();
    }

    return {
      ok: true,
      dryRun: !!params.dryRun,
      appended: params.dryRun ? 0 : toWrite.length,
      assigned: assigned,
      skipped: skipped,
      rowsAfter: params.dryRun ? existing.length : existing.length + toWrite.length
    };
  } finally {
    lock.releaseLock();
  }
}
