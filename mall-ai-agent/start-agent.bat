@echo off
chcp 65001 >nul
title mall-ai-agent (:8090)
cd /d "%~dp0"
.venv\Scripts\python -m uvicorn app.main:app --port 8090 >> C:\Users\29154\tools\agent.log 2>&1
