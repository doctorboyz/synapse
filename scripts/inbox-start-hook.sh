#!/usr/bin/env zsh
# inbox-start-hook.sh v2 — CSV-based inbox display (no auto-ack)
# SessionStart hook — read-only display of pending/accepted messages
# Output goes to stdout → Claude Code sees it in session context

set -euo pipefail

INBOX_DIR="${1:-$(pwd)/ψ/inbox}"
CSV_FILE="$INBOX_DIR/messages.csv"

if [ ! -f "$CSV_FILE" ]; then
  exit 0
fi

# ── Parse CSV into temp file (skip header) ──
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT

# Read all rows, skip header
tail -n +2 "$CSV_FILE" > "$TMP" 2>/dev/null || exit 0

# Get latest status per msg_id (last row wins)
typeset -A MAP_FROM MAP_TO MAP_TYPE MAP_ST MAP_SENT MAP_ACCEPTED MAP_COMPLETED MAP_REPLY MAP_BODYFILE
ORDER=()
ORDER_COUNT=0

while IFS= read -r line; do
  # Parse CSV with basic quoting support
  IFS=',' read -r msg_id from to type st sent accepted_at completed_at reply_to body_file <<< "$line"

  # Strip quotes for each field
  msg_id=$(echo "$msg_id" | sed 's/^"//;s/"$//')
  from=$(echo "$from" | sed 's/^"//;s/"$//')
  to=$(echo "$to" | sed 's/^"//;s/"$//')
  type=$(echo "$type" | sed 's/^"//;s/"$//')
  st=$(echo "$st" | sed 's/^"//;s/"$//')
  reply_to=$(echo "$reply_to" | sed 's/^"//;s/"$//')
  body_file=$(echo "$body_file" | sed 's/^"//;s/"$//')

  # Track first occurrence order
  if [ -z "${MAP_ST["$msg_id"]+x}" ]; then
    ORDER+=("$msg_id")
    ORDER_COUNT=$((ORDER_COUNT + 1))
  fi

  # Last write wins for status
  MAP_FROM["$msg_id"]="$from"
  MAP_TO["$msg_id"]="$to"
  MAP_TYPE["$msg_id"]="$type"
  MAP_ST["$msg_id"]="$st"
  MAP_REPLY["$msg_id"]="$reply_to"
  MAP_BODYFILE["$msg_id"]="$body_file"
done < "$TMP"

# ── Filter: pending + accepted only ──
PENDING=()
ACCEPTED=()
PENDING_COUNT=0
ACCEPTED_COUNT=0

for msg_id in "${ORDER[@]}"; do
  s="${MAP_ST["$msg_id"]}"
  if [ "$s" = "pending" ]; then
    PENDING+=("$msg_id")
    PENDING_COUNT=$((PENDING_COUNT + 1))
  elif [ "$s" = "accepted" ]; then
    ACCEPTED+=("$msg_id")
    ACCEPTED_COUNT=$((ACCEPTED_COUNT + 1))
  fi
done

if [ "$PENDING_COUNT" -eq 0 ] && [ "$ACCEPTED_COUNT" -eq 0 ]; then
  exit 0
fi

# ── Display ──
echo ""
echo -e "\xf0\x9f\x93\xa5  **Inbox** — $PENDING_COUNT pending, $ACCEPTED_COUNT accepted"
echo ""

# Helper: read body preview
body_preview() {
  local bf="$1"
  if [ -n "$bf" ] && [ -f "$INBOX_DIR/$bf" ]; then
    head -1 "$INBOX_DIR/$bf" 2>/dev/null | cut -c1-80 || echo "(no preview)"
  else
    echo "(no body)"
  fi
}

# Status icon
status_icon() {
  case "$1" in
    pending) echo -n "●" ;;
    accepted) echo -n "◐" ;;
  esac
}

if [ "$PENDING_COUNT" -gt 0 ]; then
  echo "---"
  echo "**Pending** (requires action)"
  echo ""
  for msg_id in "${PENDING[@]}"; do
    from="${MAP_FROM["$msg_id"]}"
    type="${MAP_TYPE["$msg_id"]}"
    reply="${MAP_REPLY["$msg_id"]}"
    preview=$(body_preview "${MAP_BODYFILE["$msg_id"]}")

    if [ "$reply" != "-" ]; then
      echo "  \x1b[33m●\x1b[0m **$msg_id** ← \`$from\` ($type) ↳ \`$reply\`"
    else
      echo "  \x1b[33m●\x1b[0m **$msg_id** ← \`$from\` ($type)"
    fi
    echo "  $preview"
    echo ""
  done
fi

if [ "$ACCEPTED_COUNT" -gt 0 ]; then
  echo "---"
  echo "**Accepted** (in progress)"
  echo ""
  for msg_id in "${ACCEPTED[@]}"; do
    from="${MAP_FROM["$msg_id"]}"
    type="${MAP_TYPE["$msg_id"]}"
    preview=$(body_preview "${MAP_BODYFILE["$msg_id"]}")

    echo "  \x1b[36m◐\x1b[0m **$msg_id** ← \`$from\` ($type)"
    echo "  $preview"
    echo ""
  done
fi

echo "---"
echo "_($PENDING_COUNT pending, $ACCEPTED_COUNT accepted — no auto-ack. Use \\\`maw vault accept <id>\\\` or \\\`/inbox\\\`)_"
echo ""
