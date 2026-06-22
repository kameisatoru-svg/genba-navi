@echo off
cd /d "C:\Users\user\artrays\claude ai\genba-navi"

:loop
rem self-heal an orphaned git lock. A real git op here finishes in well under a second,
rem so an index.lock still present at the top of the loop (after the 15s wait) is stale.
rem Two-pass guard: only delete when the lock was already seen on the previous iteration,
rem so we never race a live manual git op (which would clear its lock within one pass).
if exist ".git\index.lock" (
  if exist ".git\.lock_seen" (
    del /f /q ".git\index.lock" >nul 2>&1
    del /f /q ".git\.lock_seen" >nul 2>&1
    echo removed stale index.lock
  ) else (
    echo seen> ".git\.lock_seen"
  )
) else (
  if exist ".git\.lock_seen" del /f /q ".git\.lock_seen" >nul 2>&1
)

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
