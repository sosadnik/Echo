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

  if find docs/02_plans/verification -maxdepth 1 -type f -name '*.md' -print -quit 2>/dev/null \
    | grep -q .; then
    msg="Uwaga (stan planu): zmieniono kod produkcyjny, gdy istnieje plan w verification/. "
    msg+="Wynik weryfikacji jest nieważny: przenieś właściwy plan do implementation/, "
    msg+="przywróć [ ] dla zależnych kontroli i użyj debug."
  else
    msg="Przypomnienie (proces): zmieniono kod produkcyjny. Dodaj i uruchom testy zakresowe "
    msg+="(\`PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v\`), a po zielonym wyniku odhacz właściwy punkt w "
    msg+="docs/02_plans/implementation/."
  fi
  jq -n --arg m "$msg" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$m}}'
  exit 0
done <<< "$paths"

exit 0
