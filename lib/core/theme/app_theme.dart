import 'package:flutter/material.dart';

import 'app_theme_tokens.dart';
import 'extensions/landing_benefits_theme.dart';
import 'extensions/landing_carousel_theme.dart';
import 'extensions/landing_header_theme.dart';
import 'extensions/landing_service_center_theme.dart';

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
    final appliedTextTheme = baseTextTheme.apply(
      bodyColor: colorScheme.onSurface,
      displayColor: colorScheme.onSurface,
    );
    final headingColor = AppThemeTokens.headerTextColor;
    final textTheme = appliedTextTheme.copyWith(
      bodyMedium: (appliedTextTheme.bodyMedium ?? const TextStyle()).copyWith(
        fontSize: AppThemeTokens.textBodySize,
        fontWeight: FontWeight.w400,
        height: 1.5,
        color: colorScheme.onSurface,
      ),
      bodySmall: (appliedTextTheme.bodySmall ?? const TextStyle()).copyWith(
        fontSize: AppThemeTokens.textBodyLongSize,
        fontWeight: FontWeight.w400,
        height: 1.5,
        color: colorScheme.onSurface,
      ),
      titleMedium: (appliedTextTheme.titleMedium ?? const TextStyle()).copyWith(
        fontSize: AppThemeTokens.textHeadingMediumSize,
        fontWeight: FontWeight.w600,
        color: headingColor,
      ),
      headlineSmall: (appliedTextTheme.headlineSmall ?? const TextStyle())
          .copyWith(
            fontSize: AppThemeTokens.textHeadingMediumSize,
            fontWeight: FontWeight.w600,
            color: headingColor,
          ),
      headlineMedium: (appliedTextTheme.headlineMedium ?? const TextStyle())
          .copyWith(
            fontSize: AppThemeTokens.textHeadingHeroSize,
            fontWeight: FontWeight.w300,
            color: headingColor,
            height: 1.15,
          ),
      displaySmall: (appliedTextTheme.displaySmall ?? const TextStyle())
          .copyWith(
            fontSize: AppThemeTokens.textHeadingHeroSize,
            fontWeight: FontWeight.w300,
            color: headingColor,
          ),
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: colorScheme.surface,
      textTheme: textTheme,
      appBarTheme: _buildAppBarTheme(colorScheme: colorScheme),
      outlinedButtonTheme: _buildOutlinedButtonTheme(
        colorScheme: colorScheme,
        textTheme: baseTextTheme,
      ),
      extensions: [
        LandingServiceCenterTheme.fromScheme(
          colorScheme: colorScheme,
          textTheme: textTheme,
        ),
        LandingBenefitsTheme.fromScheme(
          colorScheme: colorScheme,
          textTheme: textTheme,
        ),
        LandingHeaderTheme.fromScheme(
          colorScheme: colorScheme,
          textTheme: textTheme,
        ),
        LandingCarouselTheme.fromScheme(
          colorScheme: colorScheme,
          textTheme: textTheme,
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

  static OutlinedButtonThemeData _buildOutlinedButtonTheme({
    required ColorScheme colorScheme,
    required TextTheme textTheme,
  }) {
    final textStyle = (textTheme.labelLarge ?? const TextStyle()).copyWith(
      color: colorScheme.primary,
      fontWeight: FontWeight.w600,
      letterSpacing: 0.5,
    );

    return OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: colorScheme.primary,
        textStyle: textStyle,
        side: BorderSide(color: colorScheme.primary),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppThemeTokens.appBarRadius),
        ),
      ),
    );
  }
}
