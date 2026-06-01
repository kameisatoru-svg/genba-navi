@echo off
chcp 65001 >nul
cd /d "C:\Users\user\artrays\claude ai\genba-navi"

REM ============================================================
REM  安全版 auto-push
REM  - pull 前に data.json を退避（data.json.autobak）
REM  - pull で衝突/失敗したら commit せず中断（壊れた data.json を push しない）
REM  - 衝突マーカーが残っていないか確認してから commit
REM  ※ Web側(ダッシュボード/見積請求の保存)が GitHub API で data.json を
REM    直接更新するため、pull で衝突する可能性に備える。
REM ============================================================

echo === data.json をバックアップ (data.json.autobak) ===
if exist data.json copy /Y data.json "data.json.autobak" >nul

echo === git pull origin main ===
git pull --no-edit origin main
if errorlevel 1 goto :conflict

REM 念のため、マージ後の data.json に衝突マーカーが無いか確認
if exist data.json (
  findstr /m /c:"<<<<<<<" data.json >nul 2>&1
  if not errorlevel 1 goto :marker
  findstr /m /c:">>>>>>>" data.json >nul 2>&1
  if not errorlevel 1 goto :marker
)

echo === add / commit / push ===
git update-index --really-refresh
git add -A
git commit -m "update" || echo skip: no changes
git push origin main
echo === 完了 ===
pause
exit /b 0

:conflict
echo.
echo ************************************************************
echo [中断] git pull で衝突またはエラーが発生しました。
echo data.json は data.json.autobak に退避済みです。
echo マージ状態を中止します。手動で解決してから再実行してください。
echo ************************************************************
git merge --abort 2>nul
git rebase --abort 2>nul
pause
exit /b 1

:marker
echo.
echo ************************************************************
echo [中断] data.json に衝突マーカーが残っています。
echo 壊れたファイルを push しないため中断しました。
echo 退避ファイル: data.json.autobak
echo ************************************************************
pause
exit /b 1
