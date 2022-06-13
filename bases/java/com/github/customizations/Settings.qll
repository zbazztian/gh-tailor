import java

module Settings {
  bindingset[description]
  predicate parse(string description, string key, string value) {
    exists(int i | i = description.indexOf("=", 0, 0) |
      key = description.prefix(i).trim() and
      value = description.suffix(i + 1).trim()
    )
  }

  abstract class Provider extends int {
    bindingset[this]
    Provider() { any() }

    Provider getParent() { result = max(Provider p | p < this) }

    predicate rows(string key, string value) {
      if this.assign(key, _) then this.assign(key, value) else getParent().rows(key, value)
    }

    predicate assign(string key, string value) { none() }
  }

  string values(string key) { any(Provider p).rows(key, result) }

  string prioritizedValues(string key) { max(Provider p).rows(key, result) }
}
