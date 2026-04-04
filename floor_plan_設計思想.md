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
- 外壁：内面=座標・外側に厚み／間仕切り：センター=座標・両側50mmずつ
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

**ファイル操作**
- 作業ベース：かめさんがアップロードしたファイルを使う
- GitHubからweb_fetchできない場合もアップロードで対応（「プッシュして確認」は不要）
- `/mnt/project/`は参照禁止（読取専用・古い）
- 複数修正のベースは必ず`/mnt/user-data/outputs/`の最新版

**デプロイフロー**
1. 私がファイル出力（present_files）
2. かめさんがダウンロード→Cowork上書き→push.bat→「プッシュしました」
3. 必要なら30秒後にweb_fetchで確認

**構文チェック（必須）**
```bash
node -e "
const fs=require('fs');
const html=fs.readFileSync('/home/claude/floor_plan.html','utf8');
const start=html.indexOf('<script>')+8;
const end=html.lastIndexOf('</script>');
fs.writeFileSync('/tmp/fp_test.js',html.slice(start,end));
" && node --check /tmp/fp_test.js && echo "構文OK"
```

**設計ルール**
- 角度：0°=右・90°=下・180°=左・270°=上
- 内角表示（外角225°等は絶対に出さない）
- onclick属性にJSONを渡さない→JSでイベントリスナーを直接設定
- 絵文字アイコン使用可（🔒等）

---

## ■ APIリファレンス（GN名前空間）

```javascript
GN.fitView() / GN.addSeg() / GN.tryClose() / GN.undoSeg()
GN.startLockMode(deg) / GN.toggleLockSeg(idx) / GN.cancelSegSelect()
GN.doCloseWithLocks() / GN.gnCanLockMore(idx) / GN.closeDlg()
GN.openPanel(mode) / GN.closePanel() / GN.setMode(m)
GN.startDraw() / GN.gnReset() / GN.backToDraw() / GN.editSkel()
GN.exportJSON()
GN.setName(v) / GN.setStr(v) / GN.setCt(v) / GN.setCh(v)
GN.setGW(v) / GN.setGH(v) / GN.setThr(v)
GN.toggleAddWall() / GN.deleteWall() / GN.deleteWallById(id)
GN.updateRoom(id,k,v) / GN.updateRoomMat(id,k,v) / GN.toggleLayer(key)
```

**状態オブジェクト（S）主要プロパティ**
```javascript
S.phase / S.segs[] / S.pts[] / S.cerr / S.walls[] / S.rooms[]
S.layerVis{} / S.closeAngleDeg / S.lockedSegs[] / S.selectingSegs
S.selectedWall / S.wallDrag / S.addWallMode / S.addWallStep / S.addWallP1
```
