#!/bin/bash

echo "🌱 Starting KisanMitra AI..."
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
pkill -f "python src/agent.py" 2>/dev/null || true

# Start backend voice agent and frontend
(cd backend && uv run python src/agent.py dev) &
(cd frontend && pnpm dev) &

# Wait for all background jobs
wait
