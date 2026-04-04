# floor_plan.html 引き継ぎ手順書
## 株式会社アート・レイズ（作成：2026/4/4）

---

## ■ 基本情報

| 項目 | 内容 |
|------|------|
| ファイル名 | floor_plan.html |
| GitHub Pages URL | https://kameisatoru-svg.github.io/genba-navi/floor_plan.html |
| ローカルパス | C:\Users\user\artrays\claude ai\genba-navi\floor_plan.html |
| 現在の行数 | 約1413行（修正途中のため注意） |

---

## ■ 絶対ルール（作業前に必ず確認）

1. **作業ベースは必ずGitHubからweb_fetchして取得すること**
   - `/mnt/project/` は読取専用・古い可能性あり・参照禁止
   - 作業前に `web_fetch` で以下URLから取得：
     `https://kameisatoru-svg.github.io/genba-navi/floor_plan.html`

2. **修正後は必ず構文チェック**
```bash
node -e "
const fs=require('fs');
const html=fs.readFileSync('/home/claude/floor_plan.html','utf8');
const start=html.indexOf('<script>')+8;
const end=html.lastIndexOf('</script>');
fs.writeFileSync('/tmp/fp_test.js',html.slice(start,end));
" && node --check /tmp/fp_test.js && echo "構文OK"
```

3. **デプロイフロー**
   - 私がファイル出力（present_files）
   - 亀井さんがダウンロード → Coworkで上書き → push.bat実行 → 「プッシュしました」と報告
   - 私がweb_fetchで確認（30秒待ってからフェッチ）

---

## ■ 現在の実装状況

### ✅ 実装済み

| 機能 | 状態 |
|------|------|
| 外周入力（角度ホイール・仮スケルトン） | ✅ |
| ピンチズーム・パン・全体表示 | ✅ |
| 閉じる誤差処理（許容値変更可） | ✅ |
| 間仕切り追加・移動・削除 | ✅ |
| 部屋自動生成（面積・名前・天井高・床材） | ✅ |
| レイヤーON/OFF | ✅ |
| JSON出力（ダウンロード） | ✅ |
| 確定後に作図編集に戻れる | ✅ |
| 基準点廃止（シンプル化済み） | ✅ |

### ❌ 未完成（次チャットで実装）

**「閉じる」フローの完成が最優先**

---

## ■ 「閉じる」フロー設計（未完成・次チャットで実装）

### 確定した設計

```
Step1：「閉じる」ボタンを押す
　↓
Step2：角度選択ダイアログ
　・最後の角の内角を表示（例：90°、89.3°）
　・X方向残差・Y方向残差を別々に表示
　・[90°に補正して閉じる] [89.3°このまま] [作図に戻る]
　↓
Step3：守りたい寸法をキャンバス上でタップ
　・ホイールが消える
　・各辺の寸法ラベルを直接タップ（パネルリスト表示ではない）
　・タップした辺が金色に光る（守る辺）
　・「これ以上選択できません」の判定：
　　 X残差がある → X方向の未選択辺が最低1本残ること
　　 Y残差がある → Y方向の未選択辺が最低1本残ること
　・「確定して閉じる」ボタン（キャンバス下部に表示）
　↓
Step4：残差を調整可能辺に分散吸収してぴったり閉じる
　・守らない辺 = 調整可能辺
　・X残差 → X方向（横）の調整可能辺に均等分配
　・Y残差 → Y方向（縦）の調整可能辺に均等分配
　・最終辺を始点にぴったり届く長さで追加
　・残差ゼロで外周確定
```

### 重要な設計原則

```
・閉じる時は必ず残差ゼロで閉じる（残差を残したまま閉じない）
・ユーザーが選ぶのは「角度」と「守りたい辺」だけ
・長さの調整はシステムが自動計算
・守りたい辺 = その寸法を変えない
・守らない辺 = 残差を吸収するために長さが変わる
・角度が90°の場合と非直角の場合でロジックが異なる
　（90°：X/Yに分解して吸収、非直角：別途ロジック必要）
```

### 前回の問題点（修正中にエラーが発生した箇所）

- `closeDlg` 関数が重複していた
- `selectAngle` 関数のクォートネスト問題（onclick属性にJSONを渡せない）
  → **解決策：イベントリスナーをJSで直接設定する**
- 括弧のバランスが1つ合わなかった
- `gnCanLockMore(-1)` の呼び出し方（引数-1で「追加なし」チェック）

---

## ■ 設計ルール（絶対遵守）

### 角度・方向の定義
```
0°  = 右方向（東）
90° = 下方向（南）
180° = 左方向（西）
270° = 上方向（北）
```

### 内角の定義
```
最後の辺と閉じる辺がなす建物内側の角
長方形なら90°、三角形なら60°
ユーザーには必ず「内角」で表示する
外角（225°等）は表示しない
```

### 残差の表示
```
X方向（横）とY方向（縦）を必ず分けて表示
合計距離（斜め距離）では表示しない
例：X方向：-50mm　Y方向：-50mm
```

### UIルール
```
・Fold5対応：タップボタン最小44px・推奨52px
・絵文字アイコン使用可（🔒等）
・パネルリスト表示より直接タップを優先
```

---

## ■ 今後の実装予定

| 優先度 | 機能 |
|------|------|
| 🔴 最優先 | 「閉じる」フロー完成（上記設計通り） |
| 高 | 開口部（ドア・窓）の配置 |
| 高 | GLM BLE連携（zumen_app.htmlから移植） |
| 中 | 壁厚・包絡処理・ハッチング |
| 中 | 印刷出力 |
| 中 | localStorage保存・現場一覧 |
| 低 | Gemini用データ出力 |
| 低 | Claude用JSON（面積・数量自動計算） |

---

## ■ GN名前空間 公開API一覧

```javascript
GN.fitView()          // 全体表示
GN.addSeg()           // 辺を追加
GN.tryClose()         // 閉じる（フロー開始）
GN.undoSeg()          // 1辺戻す
GN.selectAngle(obj)   // 角度選択（objは{deg,e}）
GN.toggleLockSeg(idx) // 辺のロック切替
GN.cancelSegSelect()  // 辺選択キャンセル
GN.doCloseWithLocks() // 確定して閉じる
GN.closeDlg()         // ダイアログを閉じる
GN.confirmClose(e)    // 閉じる確定
GN.forceClose()       // 強制クローズ
GN.forceCloseDirect() // 強制クローズ（直接）
GN.closeWithSnap(j)   // スナップ角度で閉じる
GN.closeWithActual(j) // 実角度で閉じる
GN.openPanel(mode)    // パネルを開く
GN.closePanel()       // パネルを閉じる
GN.setMode(m)         // モード切替
GN.startDraw()        // 作図開始
GN.gnReset()          // リセット
GN.backToDraw()       // 作図に戻る
GN.editSkel()         // 外周編集
GN.exportJSON()       // JSON出力
GN.setName(v)         // 現場名セット
GN.setStr(v)          // 構造種別セット
GN.setCt(v)           // 天井タイプセット
GN.setCh(v)           // 天井高セット
GN.setGW(v)           // 最大幅セット
GN.setGH(v)           // 最大奥行セット
GN.setThr(v)          // 許容誤差セット
GN.toggleAddWall()    // 壁追加モード切替
GN.deleteWall()       // 選択壁削除
GN.deleteWallById(id) // ID指定で壁削除
GN.updateRoom(id,k,v) // 部屋情報更新
GN.updateRoomMat(id,k,v) // 部屋床材更新
GN.toggleLayer(key)   // レイヤー切替
```

---

## ■ 状態オブジェクト（S）の主要プロパティ

```javascript
S.phase        // 'setup' | 'drawing' | 'confirmed'
S.segs[]       // 辺データ配列（angle,len,dx,dy,isFinal）
S.pts[]        // 頂点座標配列（x,y）
S.cerr         // 閉じた時の誤差記録
S.walls[]      // 間仕切り壁配列
S.rooms[]      // 部屋配列
S.layerVis{}   // レイヤー表示フラグ
S.closePhase   // '' | 'angle' | 'lock'
S.closeAngleDeg // 確定した閉じる角度
S.lockedSegs[] // 守る辺のインデックス
S.selectingSegs // 辺選択モード中フラグ
```

---

## ■ 更新履歴

| 日付 | 内容 |
|------|------|
| 2026/4/4 | 引き継ぎ手順書作成。「閉じる」フロー設計確定。基準点廃止。内角表示・残差X/Y分離表示の設計確定。 |
