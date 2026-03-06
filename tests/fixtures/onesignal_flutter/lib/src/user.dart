/// OneSignal User namespace.
///
/// Manages user identity, tags, and subscriptions.
class OneSignalUser {
  OneSignalUser._();

  /// Get the OneSignal ID.
  Future<String?> getOnesignalId() async {
    return null;
  }

  /// Get the external ID.
  Future<String?> getExternalId() async {
    return null;
  }

  /// Add a tag with key and value.
  Future<void> addTagWithKey(String key, String value) async {}

  /// Add multiple tags.
  Future<void> addTags(Map<String, String> tags) async {}

  /// Remove a tag by key.
  Future<void> removeTag(String key) async {}

  /// Remove multiple tags.
  Future<void> removeTags(List<String> keys) async {}

  /// Get all tags.
  Future<Map<String, String>> getTags() async {
    return {};
  }

  /// Add a single alias.
  Future<void> addAlias(String label, String id) async {}

  /// Add multiple aliases.
  Future<void> addAliases(Map<String, String> aliases) async {}

  /// Remove a single alias.
  Future<void> removeAlias(String label) async {}

  /// Remove multiple aliases.
  Future<void> removeAliases(List<String> labels) async {}

  /// Add an email.
  Future<void> addEmail(String email) async {}

  /// Remove an email.
  Future<void> removeEmail(String email) async {}

  /// Add SMS number.
  Future<void> addSms(String phone) async {}

  /// Remove SMS number.
  Future<void> removeSms(String phone) async {}

  /// Set user language.
  Future<void> setLanguage(String language) async {}

  /// Add user change observer.
  void addObserver(Function(dynamic state) callback) {}
}
