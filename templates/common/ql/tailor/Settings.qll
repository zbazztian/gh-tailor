module Tailor {
  abstract class Settings extends int {
    bindingset[this]
    Settings() { any() }

    Settings getParent() { result = max(Settings p | p < this) }

    predicate rows(string key, string value) {
      if this.assign(key, _) then this.assign(key, value) else getParent().rows(key, value)
    }

    predicate assign(string key, string value) { none() }
  }

  string values(string key) { any(Settings p).rows(key, result) }

  string prioritizedValues(string key) { max(Settings p).rows(key, result) }

  int minPriority(){
    result = -2147483648
  }

  int maxPriority(){
    result = 2147483647
  }

  predicate enabled(string key){
    prioritizedValues(key) = "true"
  }
}
