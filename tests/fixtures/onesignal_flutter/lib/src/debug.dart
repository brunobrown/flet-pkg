/// Debug log levels.
enum OSLogLevel {
  none,
  fatal,
  error,
  warn,
  info,
  debug,
  verbose,
}

/// OneSignal Debug namespace.
class OneSignalDebug {
  OneSignalDebug._();

  /// Set the log level.
  void setLogLevel(OSLogLevel level) {}

  /// Set the alert level.
  void setAlertLevel(OSLogLevel level) {}
}
