# floor_plan.html 設計思想
## 株式会社アート・レイズ

---

## ■ 誕生の経緯

未来システム熊本オフィスのGemini構想（matplotlibワイヤーフレーム→Geminiパース）
→ ウィジェットでインタラクティブ平面図を実験
→ 「ウィジェットでは限界」→ **floor_plan.htmlとして本格実装**

---

## ■ 根本設計思想

**「内法ポリゴンが唯一の真実」**

- 実測した内寸がそのまま座標になる
- 外壁厚は外に向かって膨らむだけ・内法座標は変わらない
- 外壁：内面=座標・外側に厚み／間仕切り：センター=座標・両側にthick/2ずつ
- RC造の柱型も外周に含めて測る（多角形外周）
- コーナーは包絡処理（外面ライン交点）でハッチング表現

---

## ■ 4つの設計軸（機能追加時は必ずこれで判断）

| 軸 | 目的 |
|---|---|
| Gemini構想 | JSON出力がGeminiプロンプトに直接使える形 |
| データ性能 | 面積・壁面積・素材が正確にJSON出力できる |
| 印刷性能 | 包絡・ハッチング・寸法線で提出図面として使える |
| Fold5現場対応 | タップ最小44px・GLM BLE連携・縦使い |

---

## ■ 絶対ルール

### ファイル操作
- 作業ベース：かめさんがアップロードしたファイルを使う
- `/mnt/project/`は参照禁止（読取専用・古い）
- GitHubからweb_fetchできない場合もアップロードで対応

### デプロイフロー
1. 私がファイル出力（present_files）
2. かめさんがダウンロード → Coworkで上書き → push.bat実行
3. 必要なら30秒後にweb_fetchで確認

### 構文チェック（修正後は必須）
```bash
node -e "
const fs=require('fs');
const html=fs.readFileSync('/home/claude/floor_plan.html','utf8');
const start=html.indexOf('<script>')+8;
const end=html.lastIndexOf('</script>');
fs.writeFileSync('/tmp/fp_test.js',html.slice(start,end));
" && node --check /tmp/fp_test.js && echo '構文OK'
```

### 設計ルール
- 角度：0°=右・90°=下・180°=左・270°=上
- 内角表示（外角225°等は絶対に出さない）
- onclick属性にJSONを渡さない → JSでイベントリスナーを直接設定
- 絵文字アイコン使用可（🔒等）
- パネルはキャンバスに被せない（flexの子要素・max-height:288pxでスクロール）

---

## ■ APIリファレンス（GN名前空間）

```javascript
// 外周操作
GN.startDraw() / GN.addSeg() / GN.undoSeg() / GN.tryClose()
GN.gnReset() / GN.backToDraw() / GN.editSkel() / GN.fitView()

// 閉じるフロー
GN.startLockMode(deg) / GN.toggleLockSeg(idx) / GN.gnCanLockMore(idx)
GN.cancelSegSelect() / GN.doCloseWithLocks() / GN.closeDlg()

// パネル・モード
GN.openPanel(mode) / GN.closePanel() / GN.setMode(m)

// 設定セッター
GN.setName(v) / GN.setStr(v) / GN.setCt(v) / GN.setCh(v)
GN.setGW(v) / GN.setGH(v) / GN.setThr(v)
GN.setSkelThick(v) / GN.setPartThick(v)

// 間仕切り
GN.toggleAddWall()       // +モードトグル
GN.toggleAngleWall()     // ／モードトグル
GN.deleteWall() / GN.deleteWallById(id)

// 部屋・レイヤー・出力
GN.updateRoom(id,k,v) / GN.updateRoomMat(id,k,v)
GN.mergeSelectedRooms() / GN.toggleLayer(key) / GN.exportJSON()
```

---

## ■ 状態オブジェクト（S）主要プロパティ

```javascript
// フェーズ・外周
S.phase          // 'setup' | 'drawing' | 'confirmed'
S.segs[]         // 辺データ配列
S.pts[]          // 頂点座標配列
S.cerr           // 閉じた時の誤差記録

// 間仕切り
S.walls[]        // 壁配列（V/H/A）
S.selectedWall   // 選択中の壁ID
S.wallDrag       // ドラッグ中フラグ
S.addWallMode    // false | 'draw'（+モード）
S.addWallAngleMode // false | true（／モード）
S.addWallStep    // 0=1点目待ち 1=2点目待ち
S.addWallP1      // 1点目座標
S.addWallDir     // 'V' | 'H'
S.addWallSnap    // スナップ候補
S.addWallCur     // プレビュー終点
S.skelThick      // 外周壁厚（デフォルト150mm）
S.partThick      // 間仕切り壁厚（デフォルト70mm）

// 部屋・レイヤー
S.rooms[]        // 部屋配列（key,x,y,w,h,area,lx,ly）
S.selectedRooms[]// 選択中部屋のkeyリスト
S.layerVis{}     // レイヤー表示フラグ

// 閉じるフロー
S.closeAngleDeg / S.lockedSegs[] / S.selectingSegs
```
