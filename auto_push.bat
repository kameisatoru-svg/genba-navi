@echo off
chcp 65001 >nul
REM ============================================================
REM  安全版 auto_push.bat（常駐ループ・衝突対策つき）
REM  配置先: C:\Users\user\artrays\claude ai\auto_push.bat
REM          （genba-navi リポジトリの「親フォルダ」に置く）
REM
REM  目的: Web側(ダッシュボード/見積請求の保存)が GitHub API で
REM        data.json を直接更新するため、ローカルとの pull で衝突した
REM        場合に「壊れた data.json をそのまま commit/push しない」。
REM
REM  挙動:
REM   - 約15秒ごとにローカル変更を検出した時だけ commit/push
REM   - pull 前に data.json を data.json.autobak へ退避
REM   - git pull が衝突/失敗したら push せず中断してループ継続
REM   - マージ後に衝突マーカーが残っていたら push せず中断
REM  ※ data.json.autobak は .gitignore 済み（コミットされない）
REM ============================================================
setlocal EnableDelayedExpansion
set "REPO=C:\Users\user\artrays\claude ai\genba-navi"
set "INTERVAL=15"

:loop
cd /d "%REPO%"

REM --- ローカル変更が無ければ何もしない（不要コミット防止） ---
set "DIRTY="
for /f "delims=" %%i in ('git status --porcelain 2^>nul') do set "DIRTY=1"
if not defined DIRTY goto :wait

REM --- data.json を退避 ---
if exist data.json copy /Y data.json "data.json.autobak" >nul

REM --- 最新を取り込み（衝突/失敗したら push せず継続） ---
git pull --no-edit origin main
if errorlevel 1 (
  echo [%TIME%] 中断: git pull 衝突/失敗。退避: data.json.autobak
  git merge --abort 2>nul
  git rebase --abort 2>nul
  goto :wait
)

REM --- マージ後に衝突マーカーが残っていないか確認 ---
findstr /m /c:"<<<<<<<" data.json >nul 2>&1 && (
  echo [%TIME%] 中断: data.json に衝突マーカー残存。push中止。退避: data.json.autobak
  goto :wait
)

REM --- タイムスタンプ付きで commit / push ---
for /f "delims=" %%t in ('powershell -NoProfile -Command "Get-Date -Format \"yyyy-MM-dd HH:mm:ss\""') do set "TS=%%t"
git add -A
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "auto-push: !TS!"
  git push origin main
  echo [!TS!] pushed
)

:wait
timeout /t %INTERVAL% /nobreak >nul
goto :loop
