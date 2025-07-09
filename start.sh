#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# Start the Selenium server in the background
# The '&' is crucial to run it as a background process
/opt/bin/entry_point.sh &

# Wait for the server to be ready before starting the Python script.
# We'll poll the server's status endpoint until it's ready.
echo "Waiting for Selenium Hub to be ready..."
while ! curl -sSL "http://localhost:4444/wd/hub/status" 2>&1 | jq -r '.value.ready' 2>&1 | grep "true" >/dev/null; do
    echo -n "."
    sleep 1
done
echo "Selenium Hub is ready!"

# Execute the Python script
echo "Starting Python application..."
exec python3 -u main.py 