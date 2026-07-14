#!/usr/bin/env bash
# PostToolUse for Claude Code and Codex: remind about tests and active-plan progress.

input=$(cat)
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
    */src/echo_app/*|src/echo_app/*) ;;
    *) continue ;;
  esac
  case "$fp" in
    */tests/*|tests/*) continue ;;
  esac

  msg="Przypomnienie (proces): zmieniono kod produkcyjny. Napisz i uruchom testy "
  msg+="(\`PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v\`), a po zielonym wyniku odhacz właściwy punkt w "
  msg+="docs/02_plans/active/. Na koniec sesji rozważ skill 'worklog-save'."
  jq -n --arg m "$msg" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$m}}'
  exit 0
done <<< "$paths"

exit 0
