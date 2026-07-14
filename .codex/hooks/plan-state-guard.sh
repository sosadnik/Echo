#!/usr/bin/env bash
# PostToolUse: report inconsistent lifecycle state without modifying project files.

root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
checker="$root/.codex/hooks/workflow-check.py"
[ -x "$checker" ] || exit 0

output=$(python3 "$checker" --project-root "$root" 2>&1) && exit 0
msg="Uwaga (workflow-check): ${output}"
jq -n --arg m "$msg" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$m}}'
exit 0
