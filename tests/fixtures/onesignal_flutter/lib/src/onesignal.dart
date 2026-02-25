/// OneSignal main class.
///
/// The main entry point for the OneSignal SDK.
class OneSignal {
  /// Initialize OneSignal with the given app ID.
  static void initialize(String appId) {}

  /// Login with an external user ID.
  static Future<void> login(String externalId) async {}

  /// Logout the current user.
  static Future<void> logout() async {}

  /// Set consent given status.
  static Future<void> consentGiven(bool given) async {}

  /// Set consent required.
  static void consentRequired(bool required) {}

  static OneSignalDebug get Debug => OneSignalDebug._();
  static OneSignalUser get User => OneSignalUser._();
  static OneSignalNotifications get Notifications => OneSignalNotifications._();
}
