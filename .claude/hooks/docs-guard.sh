#!/usr/bin/env bash
# PostToolUse for Claude Code and Codex: warn about Markdown placed in docs/ root.

input=$(cat)

# Claude Write/Edit exposes file_path. Codex apply_patch exposes one or more paths in patch.
paths=$(printf '%s' "$input" | jq -r '
  [(.tool_input.file_path // empty)] +
  [(.tool_input.patch // "" | split("\n")[]
    | select(test("^\\*\\*\\* (Add|Update|Delete) File: "))
    | sub("^\\*\\*\\* (Add|Update|Delete) File: "; ""))]
  | .[] | select(length > 0)
' 2>/dev/null)
[ -z "$paths" ] && exit 0

while IFS= read -r fp; do
  case "$fp" in
    */docs/*.md) rel=${fp##*/docs/} ;;
    docs/*.md) rel=${fp#docs/} ;;
    *) continue ;;
  esac

  [ "$rel" = "README.md" ] && continue
  case "$rel" in
    00_*/*|01_*/*|02_*/*|03_*/*|04_*/*|05_*/*|06_*/*|99_*/*) continue ;;
  esac

  msg="Uwaga (docs-organizer): plik 'docs/${rel}' zapisano bezpośrednio w docs/ poza kategoriami. "
  msg+="Przypisz go według RODZAJU do 00_specification, 01_architecture, 02_plans, 03_reports, "
  msg+="04_guides, 05_worklog, 06_decisions albo 99_archive. Szczegóły: docs/README.md."
  jq -n --arg m "$msg" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$m}}'
  exit 0
done <<< "$paths"

exit 0
