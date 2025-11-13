import 'package:talker/talker.dart';

/// Unified log message used for app wide diagnostics.
class AppLog extends TalkerLog {
  AppLog(
    String super.message, {
    dynamic error,
    super.stackTrace,
  }) : super(error: error);

  @override
  String get title => 'App';

  @override
  String get key => 'app';
}

/// Error log wrapper to highlight failures in Talker UI.
class AppErrorLog extends AppLog {
  AppErrorLog(
    String message, {
    dynamic error,
    StackTrace? stackTrace,
  }) : super('! $message', error: error, stackTrace: stackTrace);
}

