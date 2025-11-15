import 'package:talker/talker.dart';

/// Log entry for JavaScript / frontend runtime errors
/// forwarded from the web layer via postMessage.
class FrontendErrorLog extends TalkerLog {
  FrontendErrorLog(
    String super.message, {
    dynamic error,
    super.stackTrace,
  }) : super(error: error);

  @override
  String get title => 'JS';

  @override
  String get key => 'frontend-js';
}

