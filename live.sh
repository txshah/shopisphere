#!/usr/bin/env bash
# Start or stop the whole live demo: backend + BAND agents + BAND bridge + ZooWork bridge.
#   ./live.sh          start everything (LIVE=band,zoowork by default; override with LIVE=...)
#   ./live.sh stop     stop everything this script started
# Logs go to logs/<name>.log. Needs: `claude login` (BAND agents), uv, node, and a one-time
# `cd Zooworks && node merchant/setup.mjs`.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p logs

# The BAND agent runtime traps SIGTERM, and a leftover agent keeps BAND's one-connection-per-agent
# lock, so stop by name and force-kill whatever is still alive after a short grace period.
PATTERNS=("[D]ata/server.py" "[s]hopisphere/agents.py" "[s]hopisphere/bridge.py" "[m]erchant/bridge.mjs")
stop() {
  rm -f logs/*.pid
  for p in "${PATTERNS[@]}"; do pkill -f "$p" 2>/dev/null || true; done
  sleep 3
  for p in "${PATTERNS[@]}"; do pkill -9 -f "$p" 2>/dev/null || true; done
  echo "stopped"
}

start() {
  local name=$1; shift
  nohup "$@" > "logs/$name.log" 2>&1 &
  echo $! > "logs/$name.pid"
  echo "started $name (pid $!)"
}

if [ "${1:-}" = "stop" ]; then stop; exit 0; fi
stop >/dev/null

export LIVE="${LIVE:-band,zoowork}"
start backend env LIVE="$LIVE" python3 Data/server.py
sleep 2
start band-agents uv run --project Band/tom-jerry-agents python Band/shopisphere/agents.py
start band-bridge uv run --project Band/tom-jerry-agents python Band/shopisphere/bridge.py
start zoowork-bridge node Zooworks/merchant/bridge.mjs
echo "waiting for agents to connect..."
sleep 15
curl -s localhost:8787/api/state | python3 -c "import json,sys; print('modes:', json.load(sys.stdin)['modes'])"
echo "Dashboard: http://localhost:8787   ·   logs in logs/   ·   ./live.sh stop"
