@echo off
rem ===== data.json doctor (manual one-shot) =====
rem Validate data.json; if broken, restore the last-known-good copy that
rem auto_push keeps at .git\data.json.goodbak. Safe to double-click anytime.
cd /d "C:\Users\user\artrays\claude ai\genba-navi"
echo Checking data.json ...
python -c "import json; json.load(open('data.json',encoding='utf-8'))" 2>nul
if errorlevel 1 (
  echo.
  echo  [!] data.json is BROKEN.
  if exist ".git\data.json.goodbak" (
    copy /y ".git\data.json.goodbak" "data.json" >nul
    python -c "import json; json.load(open('data.json',encoding='utf-8'))" 2>nul
    if errorlevel 1 (
      echo  [x] Restore FAILED - the backup is also bad. Pick a data.json.* backup by hand.
    ) else (
      echo  [o] Restored from .git\data.json.goodbak - data.json is VALID again.
    )
  ) else (
    echo  [x] No goodbak found yet. Pick the newest valid data.json.* backup by hand.
  )
) else (
  echo  [o] data.json is VALID. Nothing to do.
)
echo.
pause
