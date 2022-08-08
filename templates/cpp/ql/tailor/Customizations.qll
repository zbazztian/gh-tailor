module TailorCustomizations {
  import tailor.Settings

  class Defaults extends Tailor::Settings {
    Defaults() { this = Tailor::minPriority() }

    override predicate assign(string key, string value) {
      key = "cpp.lenient_taintflow" and value = "false"
      or
      key = "cpp.local_sources" and value = "false"
    }
  }
}
