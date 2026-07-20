#!/bin/bash

cd "$(dirname "$0")"

echo "Starting Cogitator..."
echo "  Backend:  http://localhost:8000"

# Start backend
python3 backend/main.py &
BACKEND_PID=$!

# Start frontend dev server if npm is available
FRONTEND_PID=""
if command -v npm &>/dev/null && [ -d frontend/node_modules ]; then
    echo "  Frontend: http://localhost:5173 (dev, proxied to backend)"
    cd frontend && npm run dev &
    FRONTEND_PID=$!
    cd "$(dirname "$0")"
fi

cleanup() {
    echo ""
    echo "Shutting down..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    wait 2>/dev/null
}

trap cleanup EXIT INT TERM

wait "$BACKEND_PID" 2>/dev/null
