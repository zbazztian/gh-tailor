import com.github.customizations.Customizations

class MySettings extends Settings::CompileTimeSettings {
  override predicate rows(string key, string value) {
    // INSERT YOUR SETTINGS HERE
    key = "java.local_sources" and value = "false"
    or
    key = "java.lenient_taintflow" and value = "false"
  }
}
