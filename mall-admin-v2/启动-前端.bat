@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   启动 mall-admin-v2 管理后台前端 (5173)
echo   浏览器打开: http://localhost:5173
echo   关闭本窗口 = 停止前端服务
echo ============================================
"C:\Users\29154\.workbuddy\binaries\node\versions\22.22.2-2\npm.cmd" run dev
pause
