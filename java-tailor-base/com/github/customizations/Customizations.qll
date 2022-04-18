import com.github.customizations.CustomizationSettings
import semmle.code.java.dataflow.FlowSources
import semmle.code.java.dataflow.FlowSteps

// Additional taint step: If an object is tainted, so are its methods' return values
class TaintedObjectMA extends AdditionalTaintStep {
  override predicate step(DataFlow::Node node1, DataFlow::Node node2) {
    if CustomizationSettings::java::lenient_taintflow()
    then node1.asExpr() = node2.asExpr().(MethodAccess).getQualifier()
    else none()
  }
}
