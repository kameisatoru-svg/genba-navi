# floor_plan.html 引き継ぎ手順書
## 更新：2026/4/7 セッション

---

## ■ 2026/4/5 セッションの作業内容

### 1. 角度壁モード（／ボタン）のバグ修正・機能改善

**修正内容：**
- `#angle-wall-overlay`にCSS追加（`position:absolute;bottom:60px;z-index:20`）
- `toggleAngleWall()`：ON時はパネルを`hidden`にしてオーバーレイを表示、OFF時はオーバーレイを閉じてパネルを再表示
- `setMode()`：partition以外に切替時に`addWallAngleMode`・`AWState`・オーバーレイもリセット
- `awOnTap()`：始点・終点ともに`snapToSkeleton`を通す（スナップ優先、フォールバックは10mmグリッド）
- `awOnTap()`step1：タップ位置をホイール角度方向に射影（`proj=dx*cosA+dy*sinA`）して終点を算出
- `awOnTap()`：始点・終点を`skelBounds()`の範囲内にクリップ（外周を突き抜けない）
- `onCVMove()`：角度壁モード中も`S.addWallSnap=snapToSkeleton()`を更新してrepaint
- プレビュー描画：カーソル位置を角度方向に射影した点へ破線＋終点マーカー＋距離ラベル表示

### 2. 斜め壁の描画方式

センター線から法線方向にthick/2ずつ振り分けた2本平行線＋端部キャップ方式。

```
STEP1: fill（V/H壁：矩形fillRect / A壁：法線オフセット4角形path fill）
STEP2: V/H壁のstroke（subtractRangeで他V/H壁との交差部をカット）
STEP3: A壁のstroke（センター振り分け4辺・V/H壁矩形との交差部はclip('evenodd')で除外）
```

---

## ■ 2026/4/7 セッションの作業内容

### 1. GLM BLE連携（zumen_app.htmlと完全同一実装）

**実装内容：**
- ボトムバー右端にGLMボタン常時表示（接続中は緑色に変化）
- モーダル：接続状態表示・最後の受信値表示・ヘッダードラッグ移動対応
- 接続フロー：`GLM`プレフィックスでスキャン → SvcA全Char自動検出 → SvcB F1〜F4 → ロギング開始コマンド送信（`C0 55 02 01 00 1A`）
- パケット解析：C0 11ハートビートスキップ・C0 55測定値パケット→IEEE-754 float LE→mm変換
- **外周作図中（`S.phase==='drawing'`）：`addSeg(mm)`に直接mm値を渡して自動確定**
- 作図中以外：len-valに値を入れるだけ
- 受信時にボトムバーGLMボタンが緑フラッシュ

**トースト分類：**
- `gnToast(msg)`：BLE成功通知（緑背景）
- `gnErr(msg)`：エラー・切断通知（赤背景）

**重要：** `addSeg(forceMm)`として引数追加済み。BLE受信時はlen-valを経由せず直接mmを渡す（経由するとaddSeg内のクリア処理で消えてしまうため）。

### 2. 斜め壁の終点スナップ修正

**修正前の問題：** step1（始点確定後）のスナップ判定がマウスカーソル位置基準だったため、角度方向に伸びる先端点が壁に近づいても吸着しなかった。

**修正内容：**
- `onCVMove`のstep1で**先端点(tipX, tipY)**を計算してから`snapToSkeleton`を呼ぶ
- `AWState.snapTip`フィールドを追加（先端スナップ結果を保持）
- 描画時：`snapTip`が有効なとき先端を吸着位置に移動＋大きい塗りつぶし円で視覚的に明示
- `awOnTap`終点確定時：`snapTip`が有効なら射影計算を省略してスナップ座標をそのまま使用
- リセット箇所全3箇所に`AWState.snapTip=null`追加

### 3. BLEモーダルのスマホドラッグ対応

- `.ble-head`に`touch-action:none`追加
- `setPointerCapture`を`try/catch`で保護
- `onpointermove`内でも`ev.preventDefault()`追加
- `onpointercancel`ハンドラを追加

### 4. UI高さ調整

**パネル（ボトムバーアイコンから展開）：**
- `max-height:210px`

**ホイールオーバーレイ・角度壁オーバーレイ：**
- `height:210px;overflow:hidden`
- オーバーレイ表示中は`#canvas-area`に`padding-bottom:210px`を追加してキャンバスが隠れないよう対策
- 開閉を`showOverlay(id)` / `hideOverlay(id)`ヘルパー関数に一元化

**ホイールcanvas：** 180×180px（中心90、外半径62、内半径23）

**各要素サイズ：**
| 要素 | サイズ |
|------|--------|
| ホイールcanvas | 180×180px |
| len-val 高さ/フォント | 48px / 20px |
| 確定ボタン | 48px |
| `.wbtn`高さ | 40px |
| `#angle-disp` | 24px |

---

## ■ 壁データ構造

### V/H壁（直交壁）
```javascript
{id:'w1', type:'V', coord:3000, from:0, to:6000, thick:70}
// type:'V' → 縦壁（x=coord固定、y方向にfrom〜to）
// type:'H' → 横壁（y=coord固定、x方向にfrom〜to）
```

### A壁（斜め壁）
```javascript
{id:'w2', type:'A', x1:1000, y1:2000, x2:4000, y2:5000, angle:45, len:4243, thick:70}
// x1,y1=始点、x2,y2=終点（センター線）
// angle=ホイールで選んだ角度（15°ステップ）
// thick=壁厚（壁追加時のS.partThickを保存）
```

---

## ■ 角度壁モードの操作フロー

1. 間仕切りパネルの「／」ボタンタップ → `toggleAngleWall()`
2. パネルが閉じて角度壁オーバーレイ表示（ホイール＋案内テキスト）
3. ホイールで角度選択（15°ステップ、ドラッグ操作）
4. キャンバスで1点目タップ → スナップ吸着 → `AWState.step=1`
5. キャンバスで2点目タップ → **先端点スナップ優先** → 角度方向に射影 → 壁生成
6. step=0に戻り次の壁を連続で引ける
7. 「✕終了」ボタンで／モードOFF → パネル再表示

---

## ■ 現在の実装状況

### 実装済み
- 外周入力・閉じるフロー
- 間仕切り直交壁（+ボタン）：2タップ追加・外壁スナップ・壁厚選択・包絡処理
- 間仕切り斜め壁（／ボタン）：角度ホイール・先端点スナップ・角度拘束・外周クリップ・センター振り分け壁厚描画・V/H壁との包絡
- フラッドフィル部屋自動生成（L字3部屋対応）
- 部屋タップ選択・面積合算表示・部屋名・天井高・床材の編集
- 壁ドラッグ移動（10mmグリッドスナップ）
- レイヤーON/OFF・JSON出力
- **GLM BLE連携（外周作図中に測定値自動確定）**

### 次の実装予定
- 開口部（ドア・窓）
- 数値直接入力
- 印刷出力

---

## ■ 既知の制限事項

- 斜め壁同士の包絡は未対応（斜め壁⇔直交壁のみ対応）
- 斜め壁はフラッドフィル部屋生成に参加しない（V/H壁のみでグリッド分割）
- 斜め壁のドラッグ移動は未実装（V/H壁のみ対応）

---

## ■ 注意点（次セッション向け）

- `angle-wall-overlay`はパネル（z-index:30）より下（z-index:20）なので、／モードON時は必ずパネルをhiddenにすること
- `S.addWallMode`（+）と`S.addWallAngleMode`（／）は排他。片方ONで他方OFF
- A壁の`thick`は壁追加時の`S.partThick`を保存。描画時は`w.thick||S.partThick||70`でフォールバック
- スナップ距離は`SNAP_PX=40`px、グリッドは`snap10`（10mm単位）
- オーバーレイ開閉は必ず`showOverlay(id)` / `hideOverlay(id)`を使うこと（直接classList操作禁止）
- `addSeg(forceMm)`：BLE受信時は引数にmmを直接渡す。len-val経由は使わない
- 作業ベースは必ずアップロードされたファイルまたはGitHubからのweb_fetch。`/mnt/project/`は古い可能性あり
