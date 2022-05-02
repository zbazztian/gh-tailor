import com.github.customizations.Customizations

class MyTailorSettings extends Settings::Provider {
  override predicate rows(string key, string value) {
    // INSERT YOUR SETTINGS HERE //
    // For example:
    //
    // key = "java.local_sources" and value = "false"
    // or
    // key = "java.lenient_taintflow" and value = "false"
  }
}
