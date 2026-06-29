#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ "$(uname -m)" != "armv7l" ]; then
  echo "This helper is only for 32-bit ARMv7 Termux."
  exit 1
fi

echo "Installing the ARMv7 Debian container runtime..."
pkg update -y
pkg install -y proot-distro
proot-distro install --architecture arm --name miku-debian debian:bookworm

echo
echo "Debian Bookworm is installed. Enter it with:"
echo "  proot-distro login miku-debian"
echo "Then follow the ARMv7 steps in README.md."
