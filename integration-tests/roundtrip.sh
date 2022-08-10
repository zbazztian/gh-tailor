#!/bin/sh
set -eu

lang="$1"
project="project"

rm -rf "$project"

# vanilla test
gh tailor \
  init \
  -l "$1" \
  -b "codeql/${lang}-queries" \
  -n "zbazztian/gh-tailor-integration-test-${lang}" \
  "$project"

cd "$project"

make download
make download

make compile
make pack

make integration-test
make unit-test
make test

make publish

# The following autoversion should fail. If it
# doesn't it is a bug and will fail the script.
( \
  gh \
  tailor autoversion \
  --mode new-on-collision \
  --fail pack \
  && \
  exit -1
) || true
