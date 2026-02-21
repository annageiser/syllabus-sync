#The terminal command for starting the app is `./dev.sh` from the repo root. This script will start both the backend and frontend servers, and also handle cleanup on exit.
#The repo and app startup is executed by running `./dev.sh` from the terminal. This script will start both the backend and frontend servers, and also handle cleanup on exit. Make sure you have the necessary dependencies installed and environment variables configured before running the script.

#!/bin/bash

# Kill any existing processes on ports 3000 and 8000
echo "Cleaning up existing processes..."
lsof -ti:3000 | xargs kill -9 2>/dev/null || true
lsof -ti:8000 | xargs kill -9 2>/dev/null || true

# Function to handle shutdown
cleanup() {
    echo "Stopping servers..."
    kill $BACKEND_PID $FRONTEND_PID
    exit
}

trap cleanup SIGINT

echo "Starting Backend..."
cd backend
if [ -f "../.venv/bin/activate" ]; then
    source ../.venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "Virtualenv not found. Please run 'python -m venv .venv' at repo root."
    exit 1
fi

export PYTHONPATH=..
python3 main.py &
BACKEND_PID=$!

echo "Starting Frontend..."
cd ../frontend
npm run dev &
FRONTEND_PID=$!

wait