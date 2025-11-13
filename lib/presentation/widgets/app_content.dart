import 'package:flutter/material.dart';

import 'package:prohandyman_landing/core/theme/app_theme.dart';
import 'package:prohandyman_landing/injection_container.dart';
import 'package:prohandyman_landing/router.dart';

/// Central MaterialApp configuration for the project.
class AppContent extends StatelessWidget {
  const AppContent({super.key});

  @override
  Widget build(BuildContext context) {
    final router = sl<AppRouter>();

    return MaterialApp.router(
      debugShowCheckedModeBanner: false,
      title: 'Renzikov Hub',
      themeMode: ThemeMode.system,
      // Global theme overrides: tweak default Material widgets (AppBar, etc.)
      // instead of styling each feature manually.
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      routerConfig: router.config(),
    );
  }
}
