// ignore_for_file: avoid_web_libraries_in_flutter

import 'dart:async';
import 'dart:convert';
import 'dart:html' as html;

import 'package:talker/talker.dart';

import '../logging/frontend_error_logger.dart';
import 'frontend_error_service_base.dart';

class FrontendErrorServiceWeb implements FrontendErrorService {
  FrontendErrorServiceWeb(this._talker);

  final Talker _talker;

  StreamSubscription<html.MessageEvent>? _subscription;
  bool _started = false;

  @override
  bool get isSupported => true;

  @override
  void start() {
    if (_started) return;
    _started = true;

    _subscription = html.window.onMessage.listen((event) {
      final rawData = event.data;
      Map? decoded;
      if (rawData is String) {
        try {
          final decodedRaw = jsonDecode(rawData);
          if (decodedRaw is Map) {
            decoded = decodedRaw;
          }
        } on FormatException {
          return;
        }
      } else if (rawData is Map) {
        decoded = rawData;
      }
      if (decoded == null) return;
      if (decoded['channel']?.toString() != 'FRONTEND_ERROR_BRIDGE') {
        return;
      }

      final type = decoded['type']?.toString();
      if (type != 'FRONTEND_JS_ERROR') {
        return;
      }

      final message = decoded['message']?.toString() ?? 'JS error';
      final source = decoded['source']?.toString();
      final filename = decoded['filename']?.toString();
      final lineno = decoded['lineno']?.toString();
      final colno = decoded['colno']?.toString();

      final buffer = StringBuffer(message);
      if (source != null && source.isNotEmpty) {
        buffer.write(' [source: $source]');
      }
      if (filename != null && filename.isNotEmpty) {
        buffer.write(' at $filename');
      }
      if (lineno != null || colno != null) {
        buffer.write(' ($lineno:$colno)');
      }

      _talker.logCustom(
        FrontendErrorLog(buffer.toString()),
      );
    });
  }

  @override
  void dispose() {
    _subscription?.cancel();
    _subscription = null;
    _started = false;
  }
}

FrontendErrorService createFrontendErrorService(Talker talker) =>
    FrontendErrorServiceWeb(talker);
