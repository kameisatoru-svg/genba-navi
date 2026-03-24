@echo off
copy /Y "C:\Users\user\Downloads\index.html" "G:\マイドライブ\00亀井悟\claude ai\genba-navi\index.html"
cd /d "G:\マイドライブ\00亀井悟\claude ai\genba-navi"
git pull origin main
git add -A
git commit -m "update"
git push origin main
pause
