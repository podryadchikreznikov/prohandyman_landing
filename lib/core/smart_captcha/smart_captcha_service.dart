import 'package:talker/talker.dart';

import 'smart_captcha_service_base.dart';
import 'smart_captcha_service_stub.dart'
    if (dart.library.html) 'smart_captcha_service_web.dart' as impl;

export 'smart_captcha_service_base.dart';

SmartCaptchaService createSmartCaptchaService(Talker talker) =>
    impl.createSmartCaptchaService(talker);
