/// OneSignal Notifications namespace.
///
/// Manages push notification permissions and display.
class OneSignalNotifications {
  OneSignalNotifications._();

  /// Request notification permission.
  Future<bool> requestPermission(bool fallbackToSettings) async {
    return false;
  }

  /// Check if can request permission.
  Future<bool> canRequest() async {
    return false;
  }

  /// Get current permission status.
  bool get permission => false;

  /// Clear all notifications.
  Future<void> clearAll() async {}

  /// Remove a notification.
  Future<void> removeNotification(int notificationId) async {}

  /// Remove grouped notifications.
  Future<void> removeGroupedNotifications(String group) async {}

  /// Prevent default display.
  void preventDefault(String notificationId) {}

  /// Display a notification.
  void displayNotification(String notificationId) {}

  /// Add click listener.
  void addClickListener(Function(dynamic event) callback) {}

  /// Add foreground will display listener.
  void addForegroundWillDisplayListener(Function(dynamic event) callback) {}

  /// Add permission observer.
  void addPermissionObserver(Function(bool permission) callback) {}
}
