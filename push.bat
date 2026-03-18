@echo off
G:
cd "マイドライブ\00亀井悟\claude ai\genba-navi"
git pull origin main
git add -A
git commit -m "update"
git push origin main
pause
