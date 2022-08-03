# Tailor #

A tool for customizing CodeQL packs.

### Installation ###

```sh
gh extensions install "zbazztian/gh-tailor"

# optional:
gh extensions install "github/gh-codeql"
```

The `github/gh-codeql` extension is optional, but makes using Tailor more convenient. Without it one will either have to supply a valid CodeQL CLI distribution via the `--dist` argument or by puttin it on `${PATH}`.

### Usage ###

```sh
gh tailor init \
  -l java \
  -b "codeql/java-queries" \
  -n "zbazztian/customized-java-queries" \
  customized-java-queries
```

The above will create a template project with four scripts:
* `create` will create a new pack with the name given.
* `test` will run the unit tests for this pack.
* `integration-test` will run the integration tests for this pack.
* `publish` will publish the pack (and optionally bump its version number).
