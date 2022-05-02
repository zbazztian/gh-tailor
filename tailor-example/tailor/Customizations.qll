import com.github.customizations.Customizations

class MySettings extends Settings::Provider {
  MySettings(){
    this = 0
  }

  override predicate assign(string key, string value) {
    key = "java.local_sources" and value = "true"
    or
    key = "java.lenient_taintflow" and value = "false"
  }
}
