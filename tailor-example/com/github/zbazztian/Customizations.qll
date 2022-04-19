import com.github.customizations.Customizations

class MyStaticProvider extends Settings::StaticProvider {
  override predicate rows(string key, string value) {
    Settings::parseTuple(["java.local_sources|true"], key, value)
  }
}
