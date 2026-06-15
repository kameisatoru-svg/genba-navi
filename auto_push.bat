@echo off
cd /d "C:\Users\user\artrays\claude ai\genba-navi"

:loop
rem commit local changes first so they do not block the pull/merge
git add -A
git commit -m "auto-push" >nul 2>&1
rem then integrate remote (skip only on a real conflict)
git pull --no-edit origin main
if errorlevel 1 (
  git merge --abort 2>nul
  echo PULL CONFLICT - skip push this time
  goto wait
)
git push origin main >nul 2>&1

:wait
timeout /t 15 /nobreak >nul
goto loop
