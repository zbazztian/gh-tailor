import java

module Settings {
  bindingset[description]
  predicate parse(string description, string key, string value) {
    exists(int i | i = description.indexOf("=", 0, 0) |
      key = description.prefix(i).trim() and
      value = description.suffix(i + 1).trim()
    )
  }

  abstract class Provider extends string {
    bindingset[this]
    Provider() { any() }

    abstract predicate rows(string key, string value);
  }

  class DefaultSettings extends Provider {
    DefaultSettings() { this = "default-settings" }

    abstract override predicate rows(string key, string value);
  }

  class ExternalSettings extends Provider {
    ExternalSettings() { this = "external-settings" }

    abstract override predicate rows(string key, string value);
  }

  class CompileTimeSettings extends Provider {
    CompileTimeSettings() { this = "compile-time-settings" }

    abstract override predicate rows(string key, string value);
  }

  string values(string key) { any(Provider p).rows(key, result) }

  string prioritizedValues(string key) {
    if exists(ExternalSettings s | s.rows(key, _))
    then any(ExternalSettings s).rows(key, result)
    else (
      if exists(CompileTimeSettings s | s.rows(key, _))
      then any(CompileTimeSettings s).rows(key, result)
      else any(DefaultSettings s).rows(key, result)
    )
  }
}
