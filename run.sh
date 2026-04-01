#!/bin/bash
# Adiciona deno ao PATH (necessário para yt-dlp resolver JS challenges do YouTube)
export PATH="$HOME/.deno/bin:$PATH"

# Configura autenticação via cookies do Firefox (browser deve estar FECHADO ao rodar)
# Para usar arquivo de cookies: export YT_COOKIES_FILE=/home/$USER/cookies.txt
export YT_COOKIES_FROM_BROWSER=firefox

uv run python -m uvicorn app.uwtv.main:app --reload --host 0.0.0.0 --port 8000
