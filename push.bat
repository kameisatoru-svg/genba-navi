@echo off
cd /d "C:\Users\user\artrays\claude ai\genba-navi"
git pull origin main
git add -A
git commit -m "update"
git push origin main
pause