#!/bin/bash
# 法硕真题刷题台 · 本地启动
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=8765
URL="http://127.0.0.1:${PORT}/"

if curl -s --max-time 1 "$URL" | grep -q "法硕真题"; then
  open "$URL" || true
  exit 0
fi

cd "$DIR/app"
python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null' EXIT
sleep 0.8
open "$URL" || true
echo "法硕真题刷题台已启动：$URL"
echo "关闭此终端窗口即可停止本地服务。"
wait $SERVER_PID
