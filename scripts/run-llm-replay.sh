#!/usr/bin/env bash
# Run every blinded replay packet through a FRESH LLM session, one per packet.
#
# The predictor session must be fresh (no repo context) and tool-less: its
# entire view of the world is the packet text. Default runner is Claude Code
# headless; point LLM_CMD at any other model's CLI to benchmark it on the
# identical packets, e.g.:
#   LLM_CMD="claude -p --model claude-opus-5 --disallowedTools $TOOLS" ...
#   LLM_CMD="qwen-cli --no-tools" scripts/run-llm-replay.sh
#
# Usage: scripts/run-llm-replay.sh [parallelism]   (default 5)
set -euo pipefail
cd "$(dirname "$0")/.."
TOOLS="Bash,Read,Write,Edit,Glob,Grep,WebFetch,WebSearch,Task,Agent,NotebookEdit,Skill"
LLM_CMD="${LLM_CMD:-claude -p --model claude-fable-5 --disallowedTools $TOOLS}"
PAR="${1:-5}"
export LLM_CMD
run_one() {
  packet="$1"
  id="$(basename "$packet" .txt)"
  out="research/llm-replay/responses/$id.json"
  if [ -s "$out" ]; then echo "skip $id (response exists)"; return 0; fi
  echo "run  $id"
  # shellcheck disable=SC2086
  $LLM_CMD < "$packet" > "$out.tmp" 2>"research/llm-replay/responses/$id.err" \
    && mv "$out.tmp" "$out" && echo "done $id" \
    || { echo "FAIL $id (see responses/$id.err)"; rm -f "$out.tmp"; }
}
export -f run_one
ls research/llm-replay/packets/*.txt | xargs -P "$PAR" -I{} bash -c 'run_one "$@"' _ {}
echo "scoring..."
.venv/bin/python -m forecast.llm_replay score
