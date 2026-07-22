# Deployment Guide

Linux VPS: install Docker, copy repository, configure `.env`, run `docker compose up -d --build`. Windows VPS: use Docker Desktop/WSL2 or install the backend as an NSSM service with `scripts/windows-nssm-install.ps1`. Nginx routes frontend, API, static/media and WebSocket traffic.
