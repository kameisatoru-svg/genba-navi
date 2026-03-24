@echo off
cd /d "C:\Users\user\artrays\genba-navi"
git pull origin main
git add -A
git commit -m "update"
git push origin main
pause