#!/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
bash "$ROOT/packaging/build_app.sh"
open "$ROOT/dist" || true
read -n1 -s -r -p "按任意鍵結束"
echo
