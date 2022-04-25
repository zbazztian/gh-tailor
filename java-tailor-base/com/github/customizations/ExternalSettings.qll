import java
import com.github.customizations.Settings

external predicate external_customization_settings(string key, string value);

private module ExternalSettings {
  final class ExternalUserSettings extends Settings::ExternalSettings {
    override predicate rows(string key, string value) {
      external_customization_settings(key, value)
    }
  }
}
