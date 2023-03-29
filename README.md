# Tailor #

A tool for customizing CodeQL packs.

This is similar in spirit to https://github.com/advanced-security/codeql-bundle-action but differs in a variety of ways:

1. It only creates customized CodeQL packs as opposed to an entire CodeQL distribution.
2. On average, compile times are significantly faster, since most users will only customize a small subset of a pack's queries. The bundle action compiles all queries and libraries unconditionally.
3. It supports C/C++. The bundle action does not, since it relies on a language's `Customizations.qll` file, which does not exist for said language.
4. It is fully-automated in the sense that it tests, compiles, versions and publishes your CodeQL query packs. Specifically, the versioning aspect is different from the bundle approach.
5. It includes various small command line utilities which can be used for pack customization and other tasks.

https://github.com/ghas-trials/debug-queries/ is an end-to-end example which uses this tool to create CodeQL debug queries.

### Installation ###

```sh
gh extensions install "advanced-security/gh-tailor"

# optional but recommended:
gh extensions install "github/gh-codeql"
```

The `github/gh-codeql` extension is optional, but makes using Tailor more convenient. Without it one will either have to supply a valid CodeQL CLI distribution via the `--dist` argument or by making it available via `${PATH}`.

### Usage ###

```sh
gh tailor init \
  -b "codeql/java-queries" \
  -n "advanced-security/customized-java-queries" \
  customized-java-queries
```

The above will create a project with several files, among which:
* The `Makefile` contains various targets, such as `clean`, `download`, `compile`, `unit-test`, `integration-test`, `test` and `publish`,
* `customize` contains all the modifications one wants to make to the original pack,
* `Customizations.qll` holds some of the modifications you want to inject into selected queries and
* the `unit-tests` directory holds stub test cases that you can extend.

You can add your customization code to any of the scripts. Most likely, however, you will only need to modify the `create` script.
