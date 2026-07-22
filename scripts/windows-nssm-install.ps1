param([string]$ServiceName="InstitutionalTradingBackend",[string]$ProjectPath="C:\trading-platform\backend")
nssm install $ServiceName "$ProjectPath\.venv\Scripts\python.exe"
nssm set $ServiceName AppDirectory $ProjectPath
nssm set $ServiceName AppParameters "-m gunicorn backend.config.asgi:application -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000"
nssm set $ServiceName Start SERVICE_AUTO_START
nssm start $ServiceName
