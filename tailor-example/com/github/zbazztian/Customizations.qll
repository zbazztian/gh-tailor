import com.github.customizations.Customizations

class MyStaticProvider extends Settings::StaticProvider {
  override predicate rows(string key, string value) {
    Settings::parseTuple(["coalesced|custom-static-1", "java.lenient_taintflow|true"], key, value)
  }
}

class OtherStaticProvider extends Settings::StaticProvider {
  override predicate rows(string key, string value) {
    Settings::parseTuple(["java.lenient_taintflow|false", "coalesced|custom-static-2"], key, value)
  }
}
