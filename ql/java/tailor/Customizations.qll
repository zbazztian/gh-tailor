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



  /*
  * INTERNAL use only. This is an experimental API subject to change without notice.
  *
  * Provides classes and predicates for dealing with flow models specified in CSV format.
  *
  * The CSV specification has the following columns:
  * - Sources:
  *   `namespace; type; subtypes; name; signature; ext; output; kind`
  * - Sinks:
  *   `namespace; type; subtypes; name; signature; ext; input; kind`
  * - Summaries:
  *   `namespace; type; subtypes; name; signature; ext; input; output; kind`
  *
  * The interpretation of a row is similar to API-graphs with a left-to-right
  * reading.
  * 1. The `namespace` column selects a package.
  * 2. The `type` column selects a type within that package.
  * 3. The `subtypes` is a boolean that indicates whether to jump to an
  *    arbitrary subtype of that type.
  * 4. The `name` column optionally selects a specific named member of the type.
  * 5. The `signature` column optionally restricts the named member. If
  *    `signature` is blank then no such filtering is done. The format of the
  *    signature is a comma-separated list of types enclosed in parentheses. The
  *    types can be short names or fully qualified names (mixing these two options
  *    is not allowed within a single signature).
  * 6. The `ext` column specifies additional API-graph-like edges. Currently
  *    there are only two valid values: "" and "Annotated". The empty string has no
  *    effect. "Annotated" applies if `name` and `signature` were left blank and
  *    acts by selecting an element that is annotated by the annotation type
  *    selected by the first 4 columns. This can be another member such as a field
  *    or method, or a parameter.
  * 7. The `input` column specifies how data enters the element selected by the
  *    first 6 columns, and the `output` column specifies how data leaves the
  *    element selected by the first 6 columns. An `input` can be either "",
  *    "Argument[n]", "Argument[n1..n2]", "ReturnValue":
  *    - "": Selects a write to the selected element in case this is a field.
  *    - "Argument[n]": Selects an argument in a call to the selected element.
  *      The arguments are zero-indexed, and `-1` specifies the qualifier.
  *    - "Argument[n1..n2]": Similar to "Argument[n]" but select any argument in
  *      the given range. The range is inclusive at both ends.
  *    - "ReturnValue": Selects a value being returned by the selected element.
  *      This requires that the selected element is a method with a body.
  *
  *    An `output` can be either "", "Argument[n]", "Argument[n1..n2]", "Parameter",
  *    "Parameter[n]", "Parameter[n1..n2]", or "ReturnValue":
  *    - "": Selects a read of a selected field, or a selected parameter.
  *    - "Argument[n]": Selects the post-update value of an argument in a call to the
  *      selected element. That is, the value of the argument after the call returns.
  *      The arguments are zero-indexed, and `-1` specifies the qualifier.
  *    - "Argument[n1..n2]": Similar to "Argument[n]" but select any argument in
  *      the given range. The range is inclusive at both ends.
  *    - "Parameter": Selects the value of a parameter of the selected element.
  *      "Parameter" is also allowed in case the selected element is already a
  *      parameter itself.
  *    - "Parameter[n]": Similar to "Parameter" but restricted to a specific
  *      numbered parameter (zero-indexed, and `-1` specifies the value of `this`).
  *    - "Parameter[n1..n2]": Similar to "Parameter[n]" but selects any parameter
  *      in the given range. The range is inclusive at both ends.
  *    - "ReturnValue": Selects the return value of a call to the selected element.
  * 8. The `kind` column is a tag that can be referenced from QL to determine to
  *    which classes the interpreted elements should be added. For example, for
  *    sources "remote" indicates a default remote flow source, and for summaries
  *    "taint" indicates a default additional taint step and "value" indicates a
  *    globally applicable value-preserving step.
  */
  class RemoteSources extends SourceModelCsv {
    override predicate row(string r){
      r = Tailor::prioritizedValues("java.remote.sources")
    }
  }


}
