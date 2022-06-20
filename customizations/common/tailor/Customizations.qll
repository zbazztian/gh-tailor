import semmle.code.java.dataflow.FlowSources
import semmle.code.java.dataflow.FlowSteps
import tailor.Settings

module TailorCustomizations {

  class Defaults extends Tailor::Settings {
    Defaults() { this = Tailor::minPriority() }

    override predicate assign(string key, string value) {
      key = "java.lenient_taintflow" and value = "false"
      or
      key = "java.local_sources" and value = "false"
    }
  }

  class LocalIsRemote extends RemoteFlowSource {
    LocalIsRemote() {
      Tailor::enabled("java.local_sources") and
      this instanceof LocalUserInput
    }

    override string getSourceType() { result = "local source type" }
  }

}
