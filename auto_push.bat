@echo off
rem ===== single-instance guard (added 2026-06-22) =====
rem Hold an exclusive write handle (9) on a lock file for the whole run.
rem cmd opens a redirection target without write-sharing, so a second
rem instance cannot open the same file: its redirection fails, the ( )
rem block is skipped, and that instance exits via the || branch below.
rem The lock lives in TEMP (not the Drive-synced repo) so sync never
rem touches it, and the OS releases the handle on process exit/reboot, so
rem the lock is self-cleaning: a fresh instance after reboot always wins it.
set "AUTOPUSH_LOCK=%TEMP%\artrays_autopush.lock"
9>>"%AUTOPUSH_LOCK%" (
  call :run
) || (
  echo auto_push is already running in another window - this instance exits.
  exit /b
)
exit /b

:run
title genba-navi auto-push
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

rem ===== data.json integrity gate (added 2026-06-25) =====
rem Never publish a truncated/partial data.json: GitHub Pages serves it as the
rem source of truth for every app, so a half-written file becomes everyone's
rem corruption. Validate it as JSON first. Two-pass guard mirrors the index.lock
rem logic above: a normal in-flight write is invalid for only milliseconds and is
rem valid again by the next 15s pass (so it never triggers a restore), while
rem corruption that survives two passes is healed from the last-known-good copy.
python -c "import json; json.load(open('data.json',encoding='utf-8'))" >nul 2>&1
if errorlevel 1 (
  if exist ".git\data.json.goodbak" (
    if exist ".git\.json_bad_seen" (
      copy /y ".git\data.json.goodbak" "data.json" >nul 2>&1
      del /f /q ".git\.json_bad_seen" >nul 2>&1
      echo data.json was CORRUPT - restored from last-known-good backup
    ) else (
      echo seen> ".git\.json_bad_seen"
      echo data.json invalid this pass - waiting one cycle before healing
      goto wait
    )
  ) else (
    echo data.json invalid and no goodbak yet - skipping commit/push this cycle
    goto wait
  )
) else (
  copy /y "data.json" ".git\data.json.goodbak" >nul 2>&1
  if exist ".git\.json_bad_seen" del /f /q ".git\.json_bad_seen" >nul 2>&1
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
