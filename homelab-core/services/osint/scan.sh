#!/bin/bash

# Check if username is provided
if [ -z "$1" ]; then
    echo "Usage: ./scan.sh <username>"
    exit 1
fi

TARGET=$1
TIMESTAMP=$(date +%Y-%m-%d_%H-%M)
REPORT_DIR="reports/${TARGET}_${TIMESTAMP}"

echo "=================================================="
echo "   STARTING OSINT SCAN FOR: $TARGET"
echo "=================================================="

# 1. WARM UP: Create directory inside the container volume
echo "[*] Creating report directory..."
docker exec osint-runner mkdir -p /app/$REPORT_DIR

# 2. PHASE 1: MAIGRET (Surface Web Identity)
echo "[*] Phase 1: Running Maigret (Username Enumeration)..."
# Using --no-recursion to speed up initial scan, remove if deep scan is needed
docker exec osint-runner maigret $TARGET --html --pdf --output /app/$REPORT_DIR/maigret_report.html

# 3. PHASE 2: ONIONSEARCH (Dark Web)
echo "[*] Phase 2: Running OnionSearch (Dark Web)..."
docker exec osint-runner onionsearch "$TARGET" --proxy http://tor-proxy:9050 --output /app/$REPORT_DIR/darkweb_hits.txt

# 4. NOTIFICATION
echo "=================================================="
echo "   SCAN COMPLETE"
echo "=================================================="
echo "View your reports at: http://localhost:${FILEBROWSER_PORT:-8080}"
echo "Folder: $REPORT_DIR"
