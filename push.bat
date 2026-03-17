@echo off
chcp 65001 > nul
echo ================================
echo  アート・レイズ GitHub 自動アップ
echo ================================
echo.

:: Gドライブのgenba-naviフォルダに移動
G:
cd "マイドライブ\00亀井悟\claude ai\genba-navi"

:: 変更ファイルを確認
echo 変更ファイルを確認中...
git status --short
echo.

:: 全ファイルをステージ
git add -A

:: 日時をコミットメッセージに
for /f "tokens=1-3 delims=/" %%a in ('echo %date%') do set MYDATE=%%c%%b%%a
for /f "tokens=1-2 delims=: " %%a in ('echo %time%') do set MYTIME=%%a%%b
set MYTIME=%MYTIME: =0%
git commit -m "更新 %MYDATE%-%MYTIME%"

:: GitHubへプッシュ
echo.
echo GitHubにアップロード中...
git push origin main

echo.
echo ================================
echo  完了！1〜2分でPagesに反映されます
echo  https://kameisatoru-svg.github.io/genba-navi/
echo ================================
pause
