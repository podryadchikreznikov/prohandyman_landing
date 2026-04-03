import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_web_plugins/url_strategy.dart';
import 'package:talker/talker.dart';

import 'core/constants/constants.dart';
import 'core/frontend_error/frontend_error_service.dart';
import 'core/smart_captcha/smart_captcha_service.dart';
import 'injection_container.dart';
import 'presentation/widgets/app_content.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  _enableTimelineProfilingFlags();
  await setupLocator();

  if (kIsWeb) {
    usePathUrlStrategy();

    final captchaService = sl<SmartCaptchaService>();
    if (captchaService.isSupported && !captchaService.isInitialized) {
      await captchaService.init(siteKey: AppConfig.smartCaptchaSiteKey);
    }

    final frontendErrorService = sl<FrontendErrorService>();
    if (frontendErrorService.isSupported) {
      frontendErrorService.start();
    }
  }

  FlutterError.onError = (details) {
    sl<Talker>().handle(details.exception, details.stack);
  };

  PlatformDispatcher.instance.onError = (error, stackTrace) {
    sl<Talker>().handle(error, stackTrace);
    return true;
  };

  runApp(const MainApp());
}

/// Профилирующие флаги намеренно отключены по умолчанию,
/// так как на Flutter Web debug они сильно просаживают FPS.
/// Если нужно собрать детальный трейс, можно временно вернуть
/// включение debugProfile* флагов только на время диагностики.
void _enableTimelineProfilingFlags() {
  if (kReleaseMode) {
    return;
  }

  // Оставлено пустым умышленно.
  // Для точечной диагностики можно временно раскомментировать
  // соответствующие флаги, но это не должно быть включено всегда.
}

/// Lightweight app wrapper used as an explicit entry point.
class MainApp extends StatelessWidget {
  const MainApp({super.key});

  @override
  Widget build(BuildContext context) => const AppContent();
}
