import 'dart:ui';

import 'package:flutter/material.dart';
import 'package:talker/talker.dart';

import 'injection_container.dart';
import 'presentation/widgets/app_content.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await setupLocator();

  FlutterError.onError = (details) {
    sl<Talker>().handle(details.exception, details.stack);
  };

  PlatformDispatcher.instance.onError = (error, stackTrace) {
    sl<Talker>().handle(error, stackTrace);
    return true;
  };

  runApp(const MainApp());
}

/// Lightweight app wrapper used as an explicit entry point.
class MainApp extends StatelessWidget {
  const MainApp({super.key});

  @override
  Widget build(BuildContext context) => const AppContent();
}
