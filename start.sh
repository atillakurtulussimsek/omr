#!/bin/bash
# Yerel geliştirme: backend (8000) + arayüz (5173) tek komutla. Ctrl+C ikisini de kapatır.
cd "$(dirname "$0")"

if [ ! -x .venv/bin/uvicorn ]; then
  echo "Python ortamı kuruluyor..."
  python3 -m venv .venv && .venv/bin/pip install -q -r backend/requirements-dev.txt
fi
if [ ! -d frontend/node_modules ]; then
  echo "Arayüz paketleri kuruluyor..."
  npm --prefix frontend install --no-audit --no-fund
fi

# önceki oturumdan kalan backend'i kapat (eski süreç dosya izinlerini kaybedebiliyor)
pkill -f "uvicorn --app-dir backend api.main:app" 2>/dev/null
sleep 1

.venv/bin/uvicorn --app-dir backend api.main:app --port 8000 &
BACKEND=$!
trap 'kill $BACKEND 2>/dev/null' EXIT

echo
echo "Arayüz: http://localhost:5173"
echo
npm --prefix frontend run dev
