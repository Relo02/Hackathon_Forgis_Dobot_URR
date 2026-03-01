#!/usr/bin/env bash
set -euo pipefail

VERSION="0-9-2"

URL="https://github.com/TimSchneider42/franky/releases/latest/download/libfranka_${VERSION}_wheels.zip"
ZIP="libfranka_${VERSION}_wheels.zip"

# Basic tool checks
command -v wget >/dev/null 2>&1 || { echo "ERROR: wget not found"; exit 1; }
command -v unzip >/dev/null 2>&1 || { echo "ERROR: unzip not found"; exit 1; }
command -v pip >/dev/null 2>&1 || { echo "ERROR: pip not found"; exit 1; }

wget -O "${ZIP}" "${URL}"
unzip -o "${ZIP}"

pip install -U numpy
pip install --no-index --find-links=./dist franky-control