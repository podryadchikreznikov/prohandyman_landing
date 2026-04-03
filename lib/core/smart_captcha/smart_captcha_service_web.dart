// ignore_for_file: avoid_web_libraries_in_flutter, deprecated_member_use

import 'dart:async';
import 'dart:convert';
import 'dart:html' as html;
import 'dart:js_util' as js_util;

import 'package:talker/talker.dart';

import '../logging/captcha_logger.dart';
import 'smart_captcha_service_base.dart';

class SmartCaptchaWebService implements SmartCaptchaService {
  Completer<String>? _currentCompleter;
  StreamSubscription<html.MessageEvent>? _messageSub;
  bool _initialized = false;
  final Talker _talker;

  SmartCaptchaWebService(this._talker);

  Future<void> _waitForJsBridge() async {
    const timeout = Duration(seconds: 5);
    const interval = Duration(milliseconds: 50);
    final start = DateTime.now();

    while (true) {
      final hasInit = js_util.hasProperty(html.window, 'initSmartCaptcha');
      if (hasInit) {
        return;
      }

      if (DateTime.now().difference(start) > timeout) {
        _talker.logCustom(
          CaptchaLog('SmartCaptcha bridge not loaded within timeout'),
        );
        throw const SmartCaptchaException(
          'SmartCaptcha bridge script not loaded',
        );
      }

      await Future.delayed(interval);
    }
  }

  @override
  bool get isSupported => true;

  @override
  bool get isInitialized => _initialized;

  @override
  Future<void> init({required String siteKey}) async {
    if (_initialized) return;
    if (siteKey.isEmpty) {
      throw ArgumentError('SmartCaptcha siteKey cannot be empty');
    }

    _talker.logCustom(
      CaptchaLog('Init SmartCaptcha (invisible mode)'),
    );

    await _waitForJsBridge();
    js_util.callMethod(html.window, 'initSmartCaptcha', [siteKey]);
    _messageSub = html.window.onMessage.listen(_handleMessage);
    _initialized = true;
  }

  void _handleMessage(html.MessageEvent event) {
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
    if (decoded == null) {
      return;
    }
    if (decoded['channel']?.toString() != 'SMARTCAPTCHA_BRIDGE') {
      return;
    }

    final type = decoded['type']?.toString();
    switch (type) {
      case 'SMARTCAPTCHA_TOKEN':
        final token = decoded['token']?.toString();
        if (token != null &&
            _currentCompleter != null &&
            !_currentCompleter!.isCompleted) {
          _talker.logCustom(
            CaptchaLog('SmartCaptcha success, token received'),
          );
          _currentCompleter!.complete(token);
          _currentCompleter = null;
        }
        break;
      case 'SMARTCAPTCHA_ERROR':
        _talker.logCustom(
          CaptchaLog('SmartCaptcha error'),
        );
        _completeWithError(
          const SmartCaptchaException('SmartCaptcha error'),
        );
        break;
      case 'SMARTCAPTCHA_EXPIRED':
        _talker.logCustom(
          CaptchaLog('SmartCaptcha expired'),
        );
        _completeWithError(
          const SmartCaptchaException('SmartCaptcha expired'),
        );
        break;
    }
  }

  void _completeWithError(Object error) {
    final completer = _currentCompleter;
    if (completer != null && !completer.isCompleted) {
      completer.completeError(error);
    }
    _currentCompleter = null;
    reset();
  }

  @override
  Future<String> verify() {
    if (!_initialized) {
      return Future.error(
        StateError('SmartCaptcha must be initialized before verification'),
      );
    }
    final completer = _currentCompleter;
    if (completer != null && !completer.isCompleted) {
      return completer.future;
    }

    final nextCompleter = Completer<String>();
    _currentCompleter = nextCompleter;
    _talker.logCustom(
      CaptchaLog('Executing SmartCaptcha challenge'),
    );
    js_util.callMethod(html.window, 'showSmartCaptcha', []);

    return nextCompleter.future;
  }

  @override
  void reset() {
    _talker.logCustom(
      CaptchaLog('Reset SmartCaptcha instance'),
    );
    js_util.callMethod(html.window, 'resetSmartCaptcha', []);
  }

  @override
  void dispose() {
    _messageSub?.cancel();
    _messageSub = null;
    _currentCompleter = null;
  }
}

class SmartCaptchaException implements Exception {
  const SmartCaptchaException(this.message);

  final String message;

  @override
  String toString() => 'SmartCaptchaException: $message';
}

SmartCaptchaService createSmartCaptchaService(Talker talker) =>
    SmartCaptchaWebService(talker);
