#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
mkdir -p downloads thumbnails database

# Inside proot Debian on old Android devices, Termux's host PATH can leak in.
# Put Debian system paths first so PyTgCalls uses Debian's node binary.
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"

if command -v node >/dev/null 2>&1; then
  node_path="$(command -v node)"
  case "$node_path" in
    /data/data/com.termux/*)
      echo "Wrong node detected: $node_path"
      echo "Enter the Debian container, install Debian nodejs, then try again:"
      echo "  apt update && apt install -y nodejs npm"
      exit 1
      ;;
  esac
fi

while true; do
  python main.py
  status=$?
  if [ "$status" -eq 130 ] || [ "$status" -eq 143 ]; then
    exit "$status"
  fi
  echo "Miku stopped with code $status; restarting in 5 seconds..."
  sleep 5
done
