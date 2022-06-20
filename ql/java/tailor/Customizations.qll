module TailorCustomizations {
  import tailor.Settings
  import semmle.code.java.dataflow.FlowSources
  import semmle.code.java.dataflow.FlowSteps
  import semmle.code.java.dataflow.ExternalFlow

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

  class SourcesCsv extends SourceModelCsv {
    override predicate row(string r){
      r = Tailor::prioritizedValues("java.sources")
    }
  }

  class SinksCsv extends SinkModelCsv {
    override predicate row(string r){
      r = Tailor::prioritizedValues("java.sinks")
    }
  }

  class SummariesCsv extends SummaryModelCsv {
    override predicate row(string r){
      r = Tailor::prioritizedValues("java.summaries")
    }
  }
}
