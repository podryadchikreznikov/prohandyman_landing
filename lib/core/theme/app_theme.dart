import 'package:flutter/material.dart';

import 'app_theme_tokens.dart';
import 'extensions/landing_header_theme.dart';
import 'extensions/landing_carousel_theme.dart';

/// Central point for overriding default Material component styles.
///
/// Widgets across the app rely on the base [ThemeData] defined here instead of
/// applying ad-hoc styling in their build methods.
abstract class AppTheme {
  static ThemeData light() => _baseTheme(brightness: Brightness.light);

  static ThemeData dark() => _baseTheme(brightness: Brightness.dark);

  static ThemeData _baseTheme({required Brightness brightness}) {
    final isLight = brightness == Brightness.light;
    final baseScheme = ColorScheme.fromSeed(
      seedColor: AppThemeTokens.brandPrimary,
      brightness: brightness,
    );
    final colorScheme = baseScheme.copyWith(
      primary: AppThemeTokens.brandPrimary,
      onPrimary: AppThemeTokens.textLight,
      secondary: AppThemeTokens.brandPrimaryDark,
      onSecondary: AppThemeTokens.textLight,
      error: AppThemeTokens.danger,
      onError: AppThemeTokens.textLight,
      surface: isLight
          ? AppThemeTokens.backgroundLight
          : AppThemeTokens.backgroundDark,
      onSurface: isLight ? AppThemeTokens.textDark : AppThemeTokens.textLight,
      surfaceTint: AppThemeTokens.brandPrimary,
    );

    final baseTextTheme = ThemeData(brightness: brightness).textTheme;

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: colorScheme.surface,
      textTheme: baseTextTheme.apply(
        bodyColor: colorScheme.onSurface,
        displayColor: colorScheme.onSurface,
      ),
      appBarTheme: _buildAppBarTheme(colorScheme: colorScheme),
      extensions: [
        LandingHeaderTheme.fromScheme(
          colorScheme: colorScheme,
          textTheme: baseTextTheme,
        ),
        LandingCarouselTheme.fromScheme(
          colorScheme: colorScheme,
          textTheme: baseTextTheme,
        ),
      ],
    );
  }

  static AppBarTheme _buildAppBarTheme({required ColorScheme colorScheme}) {
    return AppBarTheme(
      backgroundColor: colorScheme.primary,
      foregroundColor: colorScheme.onPrimary,
      elevation: 0,
      centerTitle: false,
      toolbarHeight: AppThemeTokens.appBarHeight,
      titleTextStyle: TextStyle(
        color: colorScheme.onPrimary,
        fontSize: 18,
        fontWeight: FontWeight.w600,
        letterSpacing: 0.2,
      ),
      iconTheme: IconThemeData(color: colorScheme.onPrimary),
      actionsIconTheme: IconThemeData(color: colorScheme.onPrimary),
      surfaceTintColor: colorScheme.primary,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(
          bottom: Radius.circular(AppThemeTokens.appBarRadius),
        ),
      ),
    );
  }
}
