import com.github.customizations.CustomizationSettings
import semmle.code.java.dataflow.FlowSources
import semmle.code.java.dataflow.FlowSteps

class LocalIsRemote extends RemoteFlowSource {
  LocalIsRemote() {
    CustomizationSettings::java::local_sources_enabled() and
    this instanceof LocalUserInput
  }

  override string getSourceType() { result = "local source type" }
}
