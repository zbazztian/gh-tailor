#!/bin/sh
set -eu

here="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
lang="$1"
n="$2"

current="v$(gh tailor actions-cli-version)"
topn="$(gh codeql list-versions | (head -n "$n"; echo "$current") | sort -u)"

for v in $(printf "$topn"); do
  echo "Testing with version ${v}..."
  # introduce random wait time to make sure parallel tests
  # are not all downloading the cli at the same time
  sleep "$(shuf -i 0-60 -n 1)"
  gh codeql set-version "$v"
  "${here}/roundtrip.sh" "$lang"
done
