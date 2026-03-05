#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

print_usage() {
    echo "Usage: ./run_lan_server.sh [port]"
    echo "Default port: 8000"
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    print_usage
    exit 0
fi

PORT="${1:-8000}"
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "Invalid port: $PORT"
    print_usage
    exit 1
fi

PY_BIN="python3"
if [[ -x ".venv/bin/python" ]]; then
    PY_BIN=".venv/bin/python"
fi

get_lan_ip() {
    local ip

    for iface in en0 en1; do
        ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
        if [[ -n "${ip:-}" ]]; then
            echo "$ip"
            return 0
        fi
    done

    ip="$(ifconfig | awk '/inet / && $2 != "127.0.0.1" {print $2; exit}' || true)"
    echo "${ip:-}"
}

LAN_IP="$(get_lan_ip)"

echo "Starting AkmalExpress in LAN mode..."
echo "Local URL:   http://127.0.0.1:${PORT}"
if [[ -n "$LAN_IP" ]]; then
    echo "LAN URL:     http://${LAN_IP}:${PORT}"
    echo "Open LAN URL from phone/tablet on the same Wi-Fi."
else
    echo "LAN IP not detected automatically."
fi
echo

exec "$PY_BIN" manage.py runserver "0.0.0.0:${PORT}"
