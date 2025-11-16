/// Application level constants and configuration switches.
class AppConfig {
  /// Base URL for all REST calls - replace with environment specific hosts.
  static const String apiBaseUrl = 'https://api.your-backend.dev';

  /// Public endpoint for the callback request gateway API.
  static const String callbackRequestApiBaseUrl =
      'https://d5dii40lrt3h821egn3i.fary004x.apigw.yandexcloud.net';

  /// Absolute path for the callback request submission.
  static const String callbackRequestPath = '/callback/request';

  /// Client key for Yandex SmartCaptcha. Keep in sync with Yandex Cloud.
  static const String smartCaptchaSiteKey =
      'ysc1_JMJcAAfPce436nv20qcDpdMChASo4m5y2phUgeFLbfc3400a';

  /// Generic timeout applied to HTTP clients.
  static const Duration defaultTimeout = Duration(seconds: 30);
}

/// Shared preferences keys live here to keep naming consistent.
class StorageKeys {
  static const String accessToken = 'auth_access_token';
  static const String refreshToken = 'auth_refresh_token';
  static const String onboardingPassed = 'onboarding_passed';
}

/// High level route names to avoid scattering string literals.
class RoutePaths {
  static const String root = '/';
  static const String welcome = '/welcome';
  static const String placeholder = '/placeholder';
  static const String auth = '/auth';
  static const String widgetsShowcase = '/widgets-showcase';
  static const String sampleDetail = '/sample-detail';
  static const String support = '/support';
  static const String notifications = '/notifications';
  static const String settings = '/settings';
  static const String tests = '/tests';
  static const String contacts = '/contacts';
}
