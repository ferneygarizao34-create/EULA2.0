@echo off
REM Cambia esta ruta por donde tengas la carpeta eula_web en tu PC
cd /d "C:\Users\TU_USUARIO\Documents\eula_web"

REM Cambia estos dos valores por los tuyos reales
set EULA_SERVIDOR_WS=wss://tu-servidor.onrender.com/ws/agente
set EULA_AGENTE_TOKEN=el-token-que-pusiste-en-render

python agente_local.py
pause
