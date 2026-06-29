#!/data/data/com.termux/files/usr/bin/bash
set -u
cd "$(dirname "$0")"
mkdir -p downloads thumbnails database

while true; do
  python main.py
  status=$?
  if [ "$status" -eq 130 ] || [ "$status" -eq 143 ]; then
    exit "$status"
  fi
  echo "Miku stopped with code $status; restarting in 5 seconds..."
  sleep 5
done

