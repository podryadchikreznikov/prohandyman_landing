import 'smart_captcha_service_base.dart';

class SmartCaptchaUnsupportedService implements SmartCaptchaService {
  @override
  bool get isSupported => false;

  @override
  bool get isInitialized => false;

  @override
  Future<void> init({required String siteKey}) async {}

  @override
  Future<String> verify() {
    throw UnsupportedError('SmartCaptcha is only available on web.');
  }

  @override
  void reset() {}

  @override
  void dispose() {}
}

SmartCaptchaService createSmartCaptchaService(_) =>
    SmartCaptchaUnsupportedService();
