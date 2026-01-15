@echo off
chcp 65001 > nul
echo.
echo ========================================================
echo        GitHub 上傳小幫手 (Push Helper)
echo ========================================================
echo.
echo 您的程式碼已經準備好上傳了！
echo.
echo 請先依照以下步驟取得「Repository URL」：
echo 1. 登入 GitHub (https://github.com/new)
echo 2. 建立一個新的 Repository (名稱例如 etf-monitor)
echo 3. 複製畫面上的 https 網址 (例如 https://github.com/yourname/etf-monitor.git)
echo.

set /p repo_url="請貼上您的 GitHub Repository 網址: "

if "%repo_url%"=="" (
    echo [ERROR] 未輸入網址，程式結束。
    pause
    exit
)

echo.
echo 正在設定遠端位址...
git branch -M main
git remote remove origin 2>nul
git remote add origin %repo_url%

echo.
echo 正在上傳至 GitHub...
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 上傳失敗。
    echo 可能原因：
    echo 1. 網址錯誤。
    echo 2. 權限不足 (可能需要登入)。
    echo.
    echo 若是第一次使用，Git 視窗可能會跳出來要求您登入 GitHub，請依照指示登入。
    pause
) else (
    echo.
    echo [SUCCESS] 上傳成功！
    echo 請回到 GitHub 頁面開啟 Settings -> Pages 設定網頁顯示。
    pause
)
