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

// タブ名。スクリプトプロパティ SHEET_NAME があればそちらが優先される
// （タブ名を変えるときに、コードを直して再デプロイする必要がなくなる）
// 注意: ファイル名は「原価管理」だが、タブ名は既定の「シート1」のまま運用されている
var SHEET_NAME_DEFAULT = 'シート1';
var HEADER_ROWS = 1;          // 1行目はヘッダー
var COL_COUNT = 13;           // A〜M
var RC_PREFIX = 'RC-26-';
var LOCK_WAIT_MS = 30000;

// A〜M の論理名（クライアント側の COLUMNS と一致させること）
var COL_NAMES = ['レコードID', '案件番号', '現場名', '日付', '店舗名・業者名', '品目・内容',
                 '金額', '勘定科目', '原価区分', '支払方法', 'ソース', '備考', '登録日'];

// 変更前スナップショット（隠しタブ）
var SNAP_PREFIX = '_bak_';
var SNAP_KEEP = 10;

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
    // 前後の空白・改行は無視する（貼り付け時に紛れ込みやすいため）
    if (String(params.token || '').trim() !== String(expected).trim()) {
      return json({
        ok: false,
        error: '認証に失敗しました（スクリプトプロパティ API_TOKEN と、' +
               'mcp/.genka_config.json の token が一致していません）',
        受け取ったトークンの長さ: String(params.token || '').trim().length,
        設定されているトークンの長さ: String(expected).trim().length
      });
    }
    switch (params.action) {
      case 'ping':      return json(actionPing());
      case 'read':      return json(actionRead(params));
      case 'next_rc':   return json(actionNextRc());
      case 'append':    return json(actionAppend(params));
      case 'update':    return json(actionUpdate(params));
      case 'delete':    return json(actionDelete(params));
      case 'snapshot':  return json(actionSnapshot(params));
      case 'snapshots': return json(actionSnapshots());
      case 'restore':   return json(actionRestore(params));
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

function sheetName() {
  return PropertiesService.getScriptProperties().getProperty('SHEET_NAME')
      || SHEET_NAME_DEFAULT;
}

function tabNames() {
  return SpreadsheetApp.getActive().getSheets().map(function (s) { return s.getName(); });
}

function getSheet() {
  var name = sheetName();
  var sh = SpreadsheetApp.getActive().getSheetByName(name);
  if (!sh) {
    throw new Error(
      'シート『' + name + '』が見つかりません。' +
      'このスプレッドシートのタブ: ' + tabNames().join(' / ') + ' ／ ' +
      '正しいタブ名をスクリプトプロパティ SHEET_NAME に設定してください' +
      '（設定すれば再デプロイは不要です）');
  }
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

// ---------------------------------------------------------- スナップショット

function stamp() {
  return Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyyMMdd_HHmmss');
}

function snapshotSheets() {
  return SpreadsheetApp.getActive().getSheets().filter(function (s) {
    return s.getName().indexOf(SNAP_PREFIX) === 0;
  });
}

/**
 * 変更前の状態を隠しタブへ丸ごと複製する。
 * 削除・更新・復元の直前に必ず呼ぶ（間違えても戻せるようにするため）。
 */
function takeSnapshot(label) {
  var ss = SpreadsheetApp.getActive();
  var src = getSheet();
  var name = SNAP_PREFIX + stamp() + (label ? '_' + String(label).slice(0, 40) : '');
  name = name.replace(/[\[\]\*\/\\\?:]/g, '_').slice(0, 95);
  var copy = src.copyTo(ss).setName(name);
  copy.hideSheet();

  var olds = snapshotSheets().sort(function (a, b) {
    return a.getName() < b.getName() ? -1 : 1;
  });
  while (olds.length > SNAP_KEEP) {
    ss.deleteSheet(olds.shift());
  }
  return name;
}

function actionSnapshot(params) {
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(LOCK_WAIT_MS)) return { ok: false, error: 'ロックを取得できませんでした' };
  try {
    var name = takeSnapshot(params.label || 'manual');
    return { ok: true, snapshot: name, rows: readAll(getSheet()).length };
  } finally {
    lock.releaseLock();
  }
}

function actionSnapshots() {
  var out = snapshotSheets().map(function (s) {
    return { name: s.getName(), rows: Math.max(0, s.getLastRow() - HEADER_ROWS) };
  });
  out.sort(function (a, b) { return a.name < b.name ? 1 : -1; });   // 新しい順
  return { ok: true, count: out.length, snapshots: out };
}

function actionRestore(params) {
  var name = params.name;
  if (!name) return { ok: false, error: 'name（スナップショット名）を指定してください' };
  var ss = SpreadsheetApp.getActive();
  var snap = ss.getSheetByName(name);
  if (!snap) {
    return { ok: false, error: 'スナップショット『' + name + '』がありません',
             利用可能: snapshotSheets().map(function (s) { return s.getName(); }) };
  }
  var lock = LockService.getScriptLock();
  if (!lock.tryLock(LOCK_WAIT_MS)) return { ok: false, error: 'ロックを取得できませんでした' };
  try {
    var sh = getSheet();
    var before = readAll(sh).length;
    var pre = takeSnapshot('before_restore');       // 復元自体も取り消せるように

    var lastRow = snap.getLastRow();
    var values = lastRow ? snap.getRange(1, 1, lastRow, COL_COUNT).getValues() : [];
    sh.clearContents();
    if (values.length) sh.getRange(1, 1, values.length, COL_COUNT).setValues(values);
    SpreadsheetApp.flush();

    return { ok: true, restoredFrom: name, 復元前の行数: before,
             復元後の行数: Math.max(0, values.length - HEADER_ROWS),
             復元前のスナップショット: pre };
  } finally {
    lock.releaseLock();
  }
}

// ---------------------------------------------------------------- actions

function actionPing() {
  var sh = getSheet();
  var rows = readAll(sh);
  return {
    ok: true,
    sheet: sheetName(),
    tabs: tabNames(),
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

/**
 * 指定した RC の行を削除する。
 * params.rcs    … ['RC-26-043', ...]
 * params.dryRun … true なら対象を返すだけ
 * 実行前に必ずスナップショットを取る（actionSnapshot と同じ隠しタブ）。
 */
function actionDelete(params) {
  var rcs = params.rcs;
  if (!rcs || !rcs.length) return { ok: false, error: 'rcs が空です' };

  var lock = LockService.getScriptLock();
  if (!lock.tryLock(LOCK_WAIT_MS)) {
    return { ok: false, error: '他の処理が書き込み中のためロックを取得できませんでした' };
  }
  try {
    var sh = getSheet();
    var rows = readAll(sh);
    var byRc = {};
    for (var i = 0; i < rows.length; i++) {
      byRc[String(rows[i][0]).trim()] = { row: i + HEADER_ROWS + 1, data: rows[i] };
    }

    var targets = [], missing = [];
    for (var j = 0; j < rcs.length; j++) {
      var rc = String(rcs[j]).trim();
      if (byRc[rc]) {
        targets.push({ RC: rc, 行番号: byRc[rc].row, 日付: byRc[rc].data[3],
                       店舗名: byRc[rc].data[4], 金額: byRc[rc].data[6],
                       案件番号: byRc[rc].data[1] });
      } else {
        missing.push(rc);
      }
    }
    if (missing.length) {
      return { ok: false, error: '見つからないRCがあるため中止しました: ' + missing.join(', '),
               対象: targets };
    }

    if (params.dryRun) {
      return { ok: true, dryRun: true, 削除予定: targets, deleted: 0,
               rowsAfter: rows.length };
    }

    var snap = takeSnapshot('before_delete');
    targets.sort(function (a, b) { return b.行番号 - a.行番号; });   // 下から消す
    for (var k = 0; k < targets.length; k++) sh.deleteRow(targets[k].行番号);
    SpreadsheetApp.flush();

    return { ok: true, dryRun: false, 削除: targets, deleted: targets.length,
             rowsAfter: rows.length - targets.length, snapshot: snap };
  } finally {
    lock.releaseLock();
  }
}

/**
 * 指定した RC の行のセルを更新する。
 * params.updates … [{ rc: 'RC-26-071', fields: { '勘定科目': '消耗品費',
 *                                                '原価区分': '一般経費' } }, ...]
 * params.dryRun  … true なら変更前後を返すだけ
 */
function actionUpdate(params) {
  var updates = params.updates;
  if (!updates || !updates.length) return { ok: false, error: 'updates が空です' };

  var lock = LockService.getScriptLock();
  if (!lock.tryLock(LOCK_WAIT_MS)) {
    return { ok: false, error: '他の処理が書き込み中のためロックを取得できませんでした' };
  }
  try {
    var sh = getSheet();
    var rows = readAll(sh);
    var byRc = {};
    for (var i = 0; i < rows.length; i++) {
      byRc[String(rows[i][0]).trim()] = { row: i + HEADER_ROWS + 1, data: rows[i] };
    }

    var planned = [], missing = [], badCols = [];
    for (var j = 0; j < updates.length; j++) {
      var u = updates[j] || {};
      var rc = String(u.rc || '').trim();
      if (!byRc[rc]) { missing.push(rc || '(空)'); continue; }
      var changes = [];
      for (var col in (u.fields || {})) {
        var idx = COL_NAMES.indexOf(col);
        if (idx < 0) { badCols.push(col); continue; }
        if (idx === 0) { badCols.push(col + '（レコードIDは変更不可）'); continue; }
        changes.push({ 列: col, 列番号: idx + 1,
                       変更前: byRc[rc].data[idx], 変更後: u.fields[col] });
      }
      if (changes.length) planned.push({ RC: rc, 行番号: byRc[rc].row, 変更: changes });
    }
    if (missing.length || badCols.length) {
      return { ok: false,
               error: '中止しました。' +
                      (missing.length ? '見つからないRC: ' + missing.join(', ') + '。' : '') +
                      (badCols.length ? '不正な列名: ' + badCols.join(', ') +
                       '（使える列: ' + COL_NAMES.slice(1).join(' / ') + '）' : '') };
    }
    if (!planned.length) return { ok: false, error: '変更対象がありません' };

    if (params.dryRun) {
      return { ok: true, dryRun: true, 変更予定: planned, updated: 0 };
    }

    var snap = takeSnapshot('before_update');
    for (var m = 0; m < planned.length; m++) {
      var p = planned[m];
      for (var n = 0; n < p.変更.length; n++) {
        sh.getRange(p.行番号, p.変更[n].列番号).setValue(p.変更[n].変更後);
      }
    }
    SpreadsheetApp.flush();

    return { ok: true, dryRun: false, 変更: planned, updated: planned.length,
             snapshot: snap };
  } finally {
    lock.releaseLock();
  }
}
