@echo off
cd /d "C:\Users\user\artrays\claude ai\genba-navi"

:loop
git pull --no-edit origin main
if errorlevel 1 (
  git merge --abort 2>nul
  echo PULL CONFLICT - skip push this time
  goto wait
)
git add -A
git commit -m "auto-push" >nul 2>&1
git push origin main >nul 2>&1

:wait
timeout /t 15 /nobreak >nul
goto loop
