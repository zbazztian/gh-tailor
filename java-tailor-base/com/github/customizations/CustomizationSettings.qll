import com.github.customizations.Settings

module CustomizationSettings {
  class Defaults extends Settings::Provider {
    Defaults() { this = -2147483648 }

    override predicate assign(string key, string value) {
      key = "java.lenient_taintflow" and value = "false"
      or
      key = "java.local_sources" and value = "false"
    }
  }

  module java {
    predicate lenient_taintflow_enabled() {
      Settings::prioritizedValues("java.lenient_taintflow") = "true"
    }

    predicate local_sources_enabled() { Settings::prioritizedValues("java.local_sources") = "true" }

    predicate taint_through_collections_enabled() {
      Settings::prioritizedValues("java.taint_through_collections") = "true"
    }

    int min_hash_iterations() {
      result = max(Settings::prioritizedValues("java.min_hash_iterations").toInt())
    }
  }
}
