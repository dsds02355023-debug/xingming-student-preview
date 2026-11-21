#!/usr/bin/env bash
set -Eeuo pipefail
cd "${GITHUB_WORKSPACE:?}"
if [ "${1:-}" != prepare ]; then
  echo 'Use student-ci.sh for staged acceptance; this entry prepares preview repairs.' >&2
  exit 2
fi
python3 .github/scripts/repair-student-preview.py
