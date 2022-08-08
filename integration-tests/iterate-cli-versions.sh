#!/bin/sh
set -eu

here="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
lang="$1"
n="$2"

current="v$(gh tailor actions-cli-version)"
topn="$(gh codeql list-versions | head -n "$n"; echo "$current")"
topn="$(printf "$topn" | sort -u)"

for v in $(printf "$topn"); do
  echo "Testing with version ${v}..."
  gh codeql set-version "$v"
  "${here}/roundtrip.sh" "$lang"
done
