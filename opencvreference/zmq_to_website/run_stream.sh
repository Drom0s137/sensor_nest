#!/bin/bash
# launch_all.sh
# This script launches the ZeroMQ publisher, the WebSocket bridge, and an HTTP server concurrently.

# Function to clean up all processes on exit.
cleanup() {
    echo "Terminating all processes..."
    kill $PUB_PID $BRIDGE_PID $HTTP_PID
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM to run cleanup.
trap cleanup SIGINT SIGTERM

# Launch the ZeroMQ publisher.
#echo "Starting ZeroMQ publisher..."
#python3 zmq_publisher.py &
#PUB_PID=$!
#echo "Publisher PID: $PUB_PID"

# Launch the WebSocket bridge.
echo "Starting WebSocket bridge..."
python3 bridge.py &
BRIDGE_PID=$!
echo "Bridge PID: $BRIDGE_PID"

# Launch a simple HTTP server (serving files from the current directory) on port 8081.
echo "Starting HTTP server on port 8081..."
python3 -m http.server 8081 &
HTTP_PID=$!
echo "HTTP Server PID: $HTTP_PID"

echo "All programs launched. Press Ctrl+C to stop."
# Wait indefinitely; when you press Ctrl+C, the trap will call cleanup.
wait
