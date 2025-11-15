abstract class SmartCaptchaService {
  bool get isSupported;
  bool get isInitialized;

  Future<void> init({required String siteKey});
  Future<String> verify();
  void reset();
  void dispose();
}
