import java
import com.github.customizations.Settings

external predicate external_customization_settings(string key, string value);

private module ExternalSettings {
  final class ExternalUserSettings extends Settings::Provider {
    ExternalUserSettings() { this = 2147483647 }

    override predicate assign(string key, string value) {
      external_customization_settings(key, value)
    }
  }
}
