/// Application level constants and configuration switches.
class AppConfig {
  /// Base URL for all REST calls - replace with environment specific hosts.
  static const String apiBaseUrl = 'https://api.your-backend.dev';

  /// Public endpoint for the callback request gateway API.
  static const String callbackRequestApiBaseUrl =
      'https://d5dii40lrt3h821egn3i.fary004x.apigw.yandexcloud.net';

  /// Absolute path for the callback request submission.
  static const String callbackRequestPath = '/callback/request';

  /// Contract hash for the callback request payload schema.
  static const String callbackRequestSchemaHash =
      '81a26973e17bc344098ca06efc0fd2495d8bd846ea7979e9c74a989f143fa819';

  /// Contract hash for the callback request response schema.
  static const String callbackResponseSchemaHash =
      '2d9389fd413dd30152e0e565cdc0b9fedbba342f7b5983973d572fcef4cb7871';

  /// Client key for Yandex SmartCaptcha. Keep in sync with Yandex Cloud.
  static const String smartCaptchaSiteKey =
      'ysc1_JMJcAAfPce436nv20qcDpdMChASo4m5y2phUgeFLbfc3400a';

  /// Generic timeout applied to HTTP clients.
  static const Duration defaultTimeout = Duration(seconds: 120);
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
  static const String services = '/services';
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
  static const String about = '/about';
  static const String partners = '/partners';
}
