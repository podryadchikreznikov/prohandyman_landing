import 'package:flutter/material.dart';

/// Shared design tokens describing the brand palette and reusable metrics.
///
/// Palette ratio: 70% white, 20% black, 10% accent (#6B2C41).
abstract class AppThemeTokens {
  static const Color brandPrimary = Color(0xFF6B2C41);
  static const Color brandPrimaryDark = Color(0xFF511F30);
  static const Color landingNavBlue = Color(0xFF0D47A1); // Material blue[900]

  static const Color backgroundLight = Color(0xFFFFFFFF);
  static const Color backgroundSurface = Color(0xFFF7F5F6);
  static const Color backgroundDark = Color(0xFF0A0A0A);

  static const Color textLight = Color(0xFFFFFFFF);
  static const Color textLightMuted = Color(0xD9FFFFFF); // ~85% opacity
  static const Color textDark = Color(0xFF111111);

  static const Color danger = Color(0xFFB3261E);

  static const double appBarHeight = 64;
  static const double appBarRadius = 8;
  static const double logoIconSize = 32;
  static const double logoTextGap = 16;
  static const double contentMaxWidth = 1200;
  static const double pageTopPadding = 0;
  static const double landingHeaderHeight = 144;
  static const double landingHeaderCompactHeightBreakpoint = 760;
  static const double landingHeaderCompactExtraHeight = 32;
  static const double companyLogoAspectRatio = 1.2;
  static const double carouselHeight = 420;
  static const double carouselBorderRadius = 18;
  static const double carouselMaxWidth = 1200;
  static const Color headerTextColor = Color(0xFF111111);
  static const Color headerIconColor = Color(0xFF1B1B1B);
  static const Color headerSubtitleColor = Color(0xFF6A6A6A);
  static const double headerTitleFontSize = 20;
  static const double headerSubtitleFontSize = 12;
  static const double headerColumnsGap = 32;
  static const Color carouselOverlayStart = Color(0xCC000000);
  static const Color carouselOverlayEnd = Color(0x00000000);
  static const Color carouselArrowBackground = Color(0x33000000);
}
