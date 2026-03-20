@echo off
cd /d "G:\マイドライブ\現場ナビPRO"
git rm --cached 顧客台帳_アートレイズ.html
del 顧客台帳_アートレイズ.html
git add -A
git commit -m "Remove deprecated customer ledger (merged into torihikisaki ledger)"
git push origin main
pause
