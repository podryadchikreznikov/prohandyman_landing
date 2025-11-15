import 'package:talker/talker.dart';

/// Log for SmartCaptcha-related events and diagnostics.
class CaptchaLog extends TalkerLog {
  CaptchaLog(
    String super.message, {
    dynamic error,
    super.stackTrace,
  }) : super(error: error);

  @override
  String get title => 'Captcha';

  @override
  String get key => 'captcha';
}

