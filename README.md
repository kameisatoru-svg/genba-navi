# 現場ナビPRO

株式会社アート・レイズ（大分県別府市）の建設・内装リフォーム業向け業務管理Webアプリ。
案件・取引先・原価・書類を一元管理するシングルページアプリケーション。

## 主要ファイル

| ファイル | 役割 |
|---|---|
| `index.html` | ダッシュボード本体（案件一覧・取引先・書類リンク） |
| `data.json` | 全データのソース（案件・取引先マスター・単価マスタ等） |
| `zumen_app.html` | 図面管理アプリ |
| `floor_plan.html` | 平面図エディタ（ワイヤーフレーム自動生成） |
| `材料割付_app_.html` | 床材・壁材の材料割付計算ツール |
| `mitsumori_preview.html` | 見積書プレビュー・PDF出力 |

## data.json の構造

トップレベルキー：
- `最終更新`：YYYY-MM-DD
- `命名ルール`：案件キー・ファイル名・書類番号の規則
- `取引先マスター`：顧客・業者の一覧（T-001〜）
- `案件`：進行中・完了案件
- `中止案件`：参考保管
- `単価マスタ`：天井・壁・床の材料単価（材料割付_app_/floor_plan用）

## ホスティング

GitHub Pages：https://kameisatoru-svg.github.io/genba-navi/

## 開発

ローカル編集 → `auto_push.bat` でGitHubに自動push → GitHub Pagesに数分で反映。
data.jsonの単価マスタを書き換えると、現場ナビPRO側のヘッダーバッジ「🔗 単価マスタ連携中」経由で
最大6時間以内（バッジタップで即時）にアプリへ反映される。

## ライセンス

Private repository - All rights reserved.
