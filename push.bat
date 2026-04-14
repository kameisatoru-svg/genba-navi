@echo off
cd /d "C:\Users\user\artrays\claude ai\genba-navi"
git pull origin main
git update-index --really-refresh
git add -A
git commit -m "update" || echo skip: no changes
git push origin main
pause