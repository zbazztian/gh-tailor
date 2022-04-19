import java

//external predicate external_customization_settings(string key, string value);
predicate external_customization_settings(string key, string value){ none() }

module Settings {
  bindingset[description]
  predicate parseTuple(string description, string key, string value) {
    key = description.splitAt("|", 0) and
    value = description.splitAt("|", 1)
  }

  abstract class Provider extends string {
    bindingset[this]
    Provider() { any() }

    abstract predicate rows(string key, string value);
  }

  class DefaultsProvider extends Provider {
    DefaultsProvider() { this = "defaults" }

    abstract override predicate rows(string key, string value);
  }

  class StaticProvider extends Provider {
    StaticProvider() { this = "static" }

    abstract override predicate rows(string key, string value);
  }

  final class ExternalProvider extends Provider {
    ExternalProvider() { this = "external" }

    override predicate rows(string key, string value) {
      external_customization_settings(key, value)
    }
  }

  string values(string key) { any(Provider p).rows(key, result) }

  string prioritizedValues(string key) {
    if exists(ExternalProvider p | p.rows(key, _))
    then any(ExternalProvider p).rows(key, result)
    else (
      if exists(StaticProvider p | p.rows(key, _))
      then any(StaticProvider p).rows(key, result)
      else any(DefaultsProvider p).rows(key, result)
    )
  }
}
