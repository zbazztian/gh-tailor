# Tailor #

A tool for customizing CodeQL packs.

This is similar in spirit to advanced-security/codeql-bundle-action but differs in a variety of ways:

1. It only creates customized CodeQL packs as opposed to an entire CodeQL distribution.
2. On average, compile times are significantly faster, since most users will only customize a small subset of all queries. This is in contrast to the aforementioned bundle action, which compiles all queries and libraries everytime.
3. It supports C/C++. The bundle action does not, since it relies on a language's `Customizations.qll` file, which does not exist for said language.
4. It is fully-automated in the sense that it tests, compiles, versions and publishes your CodeQL query packs. Specifically, the versioning aspect is different from the bundle approach.
5. It includes various small command line utilities which can be used for pack customization and other tasks.

ghas-trials/debug-queries is an end-to-end example which uses this tool to create CodeQL debug queries.

### Installation ###

```sh
gh extensions install "zbazztian/gh-tailor"

# optional but recommended:
gh extensions install "github/gh-codeql"
```

The `github/gh-codeql` extension is optional, but makes using Tailor more convenient. Without it one will either have to supply a valid CodeQL CLI distribution via the `--dist` argument or by making it available via `${PATH}`.

### Usage ###

```sh
gh tailor init \
  -b "codeql/java-queries" \
  -n "zbazztian/customized-java-queries" \
  customized-java-queries
```

The above will create a project with four scripts:
* `create` will create a new pack with the name given.
* `unit-test` will run the unit tests for this pack.
* `integration-test` will run the integration tests for this pack.
* `publish` will publish the pack (and optionally bump its version number).

You can add your customization code to any of the scripts. Most likely, however, you will only need to modify the `create` script.
