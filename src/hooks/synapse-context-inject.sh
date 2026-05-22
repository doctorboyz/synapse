#!/usr/bin/env bash
# Synapse context injection hook — PreToolUse on Read|Glob|Grep
# Injects a reminder to search synapse when local knowledge is insufficient.
# Silent exit (no output) when synapse is not available.

SYNAPSE_DIR="$HOME/.synapse"
PID_FILE="$SYNAPSE_DIR/synapse.pid"

# Check if daemon is running (PID file exists and process is alive)
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE" 2>/dev/null)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        cat <<'EOF'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"Synapse vault is available and running. When local files do not contain sufficient context, use the synapse_search MCP tool to search the knowledge vault (Stage 2). Priority: read local files first (Stage 1), then search synapse if needed."}}
EOF
        exit 0
    fi
fi

# Fallback: synapse configured but daemon not running
if [ -d "$SYNAPSE_DIR" ]; then
    cat <<'EOF'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"Synapse vault exists but daemon may not be running. Start with `synapse serve` if needed. Use synapse_search MCP tool when local knowledge is insufficient."}}
EOF
    exit 0
fi

# No synapse available — silent exit
exit 0