abstract class FrontendErrorService {
  bool get isSupported;

  /// Starts listening for frontend JS error events (web only).
  void start();

  void dispose();
}

