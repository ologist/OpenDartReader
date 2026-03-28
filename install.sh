#!/usr/bin/env bash
# opendartreader — Claude Desktop 플러그인 설치 스크립트
# 사용법: ./install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
PLIST_ID="com.opendartreader-mcp"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_ID}.plist"
MCP_URL="http://localhost:8020/mcp"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " OpenDartReader MCP Installer"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 0. 필수 확인 ────────────────────────────────────────────
echo ""
echo "🔍 필수 환경 확인 중..."

if ! command -v docker &>/dev/null; then
  echo "❌ Docker가 설치되어 있지 않습니다."
  exit 1
fi
echo "   ✓ Docker"

if ! command -v npx &>/dev/null; then
  echo "❌ npx (Node.js)가 필요합니다."
  exit 1
fi
echo "   ✓ npx"

if [ ! -f "$SCRIPT_DIR/.env" ]; then
  echo "❌ .env 파일이 없습니다. .env.example을 복사하여 설정하세요:"
  echo "   cp .env.example .env"
  exit 1
fi
echo "   ✓ .env"

# ── 1. Docker 이미지 빌드 ────────────────────────────────────
echo ""
echo "🐳 Docker 이미지 빌드 중..."
cd "$SCRIPT_DIR"
docker compose build --no-cache -q
echo "   → 빌드 완료"

# ── 2. LaunchAgent 등록 (로그인 시 자동 시작) ────────────────
echo ""
echo "⚙️  LaunchAgent 등록 중..."

if launchctl list "$PLIST_ID" &>/dev/null 2>&1; then
  launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

DOCKER_PATH="$(command -v docker)"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${PLIST_ID}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${DOCKER_PATH}</string>
    <string>compose</string>
    <string>-f</string>
    <string>${SCRIPT_DIR}/docker-compose.yml</string>
    <string>up</string>
    <string>--remove-orphans</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${SCRIPT_DIR}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <false/>
  <key>StandardOutPath</key>
  <string>/tmp/opendartreader-mcp.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/opendartreader-mcp.err</string>
</dict>
</plist>
EOF

launchctl load "$PLIST_PATH"
echo "   → $PLIST_PATH (로그인 시 자동 시작 등록)"

# ── 3. 컨테이너 즉시 시작 ────────────────────────────────────
echo ""
echo "🚀 컨테이너 시작 중..."
cd "$SCRIPT_DIR"
docker compose up -d
echo "   → 실행 중 (http://localhost:8020)"

# 헬스체크 (최대 20초 대기)
echo "   헬스체크 중..."
for i in $(seq 1 20); do
  if curl -s "http://localhost:8020/health" 2>/dev/null | grep -q '"ok"'; then
    echo "   ✓ 서버 응답 확인 (${i}초)"
    break
  fi
  if [ "$i" -eq 20 ]; then
    echo "   ⚠️  서버 응답 없음 — 로그 확인: docker compose -f $SCRIPT_DIR/docker-compose.yml logs"
  fi
  sleep 1
done

# ── 4. Claude Desktop MCP 등록 ──────────────────────────────
echo ""
echo "🖥️  Claude Desktop MCP 등록 중..."

python3 - <<PYEOF
import json, os

path = "$CLAUDE_CONFIG"
try:
    with open(path) as f:
        data = json.load(f)
except FileNotFoundError:
    data = {}

servers = data.setdefault("mcpServers", {})
servers["opendartreader"] = {
    "command": "npx",
    "args": ["-y", "mcp-remote", "$MCP_URL"]
}

with open(path, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")

print(f"   → {path}")
print(f"   → mcpServers.opendartreader 등록 완료")
PYEOF

# ── 완료 ────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 설치 완료!"
echo ""
echo "   MCP 서버:   $MCP_URL"
echo "   REST API:   http://localhost:8020/docs"
echo "   로그:       /tmp/opendartreader-mcp.log"
echo ""
echo "   Claude Desktop을 재시작하면 opendartreader MCP가 활성화됩니다."
echo ""
echo "   ── 관리 명령어 ─────────────────────────"
echo "   시작:  docker compose -f $SCRIPT_DIR/docker-compose.yml up -d"
echo "   중지:  docker compose -f $SCRIPT_DIR/docker-compose.yml down"
echo "   로그:  docker compose -f $SCRIPT_DIR/docker-compose.yml logs -f"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
