import com.github.customizations.Settings

module CustomizationSettings {
  class Defaults extends Settings::DefaultsProvider {
    override predicate rows(string key, string value) {
      Settings::parseTuple([
          "java.lenient_taintflow|false", "java.local_sources|false", "coalesced|default",
          "coalesced2|default"
        ], key, value)
    }
  }

  module java {
    predicate lenient_taintflow() { Settings::prioritizedValues("java.lenient_taintflow") = "true" }

    predicate local_sources() { Settings::prioritizedValues("java.local_sources") = "true" }

    predicate taint_through_collections() {
      Settings::prioritizedValues("java.taint_through_collections") = "true"
    }

    int min_hash_iterations() {
      result = max(Settings::prioritizedValues("java.min_hash_iterations").toInt())
    }
  }
}
