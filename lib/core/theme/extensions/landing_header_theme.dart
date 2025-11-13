import 'dart:ui';

import 'package:flutter/material.dart';

import '../app_theme_tokens.dart';

/// Theme extension exposing landing-header specific styling knobs.
class LandingHeaderTheme extends ThemeExtension<LandingHeaderTheme> {
  const LandingHeaderTheme({
    required this.titleSpacing,
    required this.avatarRadius,
    required this.logoIconSize,
    required this.logoGap,
    required this.logoAspectRatio,
    required this.infoPadding,
    required this.ctaPadding,
    required this.logoBackgroundColor,
    required this.logoIconColor,
    required this.headerInfoIconColor,
    required this.titleTextStyle,
    required this.subtitleTextStyle,
    required this.headerInfoTextStyle,
    required this.callToActionTextStyle,
    required this.callToActionStyle,
    required this.headerBackgroundColor,
    required this.navBackgroundColor,
    required this.navBarHeight,
    required this.navItemTextStyle,
    required this.navItemPadding,
    required this.navItemGap,
    required this.navCallToActionTextStyle,
    required this.navCallToActionStyle,
  });

  factory LandingHeaderTheme.fromScheme({
    required ColorScheme colorScheme,
    required TextTheme textTheme,
  }) {
    final onPrimary = colorScheme.onPrimary;
    final titleStyle = (textTheme.titleLarge ?? const TextStyle()).copyWith(
      color: AppThemeTokens.headerTextColor,
      fontWeight: FontWeight.w700,
      fontSize: AppThemeTokens.headerTitleFontSize,
      letterSpacing: 0.2,
    );
    final subtitleStyle = (textTheme.bodySmall ?? const TextStyle()).copyWith(
      color: AppThemeTokens.headerSubtitleColor,
      fontSize: AppThemeTokens.headerSubtitleFontSize,
      letterSpacing: 0.2,
    );
    final infoStyle = (textTheme.bodyMedium ?? const TextStyle()).copyWith(
      color: AppThemeTokens.headerTextColor,
    );
    final ctaTextStyle = (textTheme.labelLarge ?? const TextStyle()).copyWith(
      color: onPrimary,
      fontWeight: FontWeight.w600,
      letterSpacing: 0.5,
    );

    return LandingHeaderTheme(
      titleSpacing: 12,
      avatarRadius: 34,
      logoIconSize: AppThemeTokens.logoIconSize,
      logoGap: AppThemeTokens.logoTextGap,
      logoAspectRatio: AppThemeTokens.companyLogoAspectRatio,
      infoPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      ctaPadding: const EdgeInsets.symmetric(horizontal: 16),
      logoBackgroundColor: colorScheme.onPrimary,
      logoIconColor: colorScheme.primary,
      headerInfoIconColor: AppThemeTokens.headerIconColor,
      titleTextStyle: titleStyle,
      subtitleTextStyle: subtitleStyle,
      headerInfoTextStyle: infoStyle,
      callToActionTextStyle: ctaTextStyle,
      callToActionStyle: OutlinedButton.styleFrom(
        foregroundColor: onPrimary,
        backgroundColor: colorScheme.primary,
        side: BorderSide(color: onPrimary),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppThemeTokens.appBarRadius),
        ),
      ),
      headerBackgroundColor: AppThemeTokens.backgroundLight,
      navBackgroundColor: colorScheme.primary,
      navBarHeight: 48,
      navItemTextStyle: (textTheme.titleMedium ?? const TextStyle()).copyWith(
        color: onPrimary,
        fontWeight: FontWeight.w500,
      ),
      navItemPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      navItemGap: 8,
      navCallToActionTextStyle: (textTheme.labelLarge ?? const TextStyle())
          .copyWith(
            color: onPrimary,
            fontWeight: FontWeight.w600,
          ),
      navCallToActionStyle: OutlinedButton.styleFrom(
        foregroundColor: onPrimary,
        backgroundColor: Colors.transparent,
        side: BorderSide(color: onPrimary),
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppThemeTokens.appBarRadius),
        ),
      ),
    );
  }

  final double titleSpacing;
  final double avatarRadius;
  final double logoIconSize;
  final double logoGap;
  final double logoAspectRatio;
  final EdgeInsetsGeometry infoPadding;
  final EdgeInsetsGeometry ctaPadding;
  final Color logoBackgroundColor;
  final Color logoIconColor;
  final Color headerInfoIconColor;
  final TextStyle titleTextStyle;
  final TextStyle subtitleTextStyle;
  final TextStyle headerInfoTextStyle;
  final TextStyle callToActionTextStyle;
  final ButtonStyle callToActionStyle;
  final Color headerBackgroundColor;
  final Color navBackgroundColor;
  final double navBarHeight;
  final TextStyle navItemTextStyle;
  final EdgeInsetsGeometry navItemPadding;
  final double navItemGap;
  final TextStyle navCallToActionTextStyle;
  final ButtonStyle navCallToActionStyle;

  @override
  LandingHeaderTheme copyWith({
    double? titleSpacing,
    double? avatarRadius,
    double? logoIconSize,
    double? logoGap,
    double? logoAspectRatio,
    EdgeInsetsGeometry? infoPadding,
    EdgeInsetsGeometry? ctaPadding,
    Color? logoBackgroundColor,
    Color? logoIconColor,
    Color? headerInfoIconColor,
    TextStyle? titleTextStyle,
    TextStyle? subtitleTextStyle,
    TextStyle? headerInfoTextStyle,
    TextStyle? callToActionTextStyle,
    ButtonStyle? callToActionStyle,
    Color? headerBackgroundColor,
    Color? navBackgroundColor,
    double? navBarHeight,
    TextStyle? navItemTextStyle,
    EdgeInsetsGeometry? navItemPadding,
    double? navItemGap,
    TextStyle? navCallToActionTextStyle,
    ButtonStyle? navCallToActionStyle,
  }) {
    return LandingHeaderTheme(
      titleSpacing: titleSpacing ?? this.titleSpacing,
      avatarRadius: avatarRadius ?? this.avatarRadius,
      logoIconSize: logoIconSize ?? this.logoIconSize,
      logoGap: logoGap ?? this.logoGap,
      logoAspectRatio: logoAspectRatio ?? this.logoAspectRatio,
      infoPadding: infoPadding ?? this.infoPadding,
      ctaPadding: ctaPadding ?? this.ctaPadding,
      logoBackgroundColor: logoBackgroundColor ?? this.logoBackgroundColor,
      logoIconColor: logoIconColor ?? this.logoIconColor,
      headerInfoIconColor: headerInfoIconColor ?? this.headerInfoIconColor,
      titleTextStyle: titleTextStyle ?? this.titleTextStyle,
      subtitleTextStyle: subtitleTextStyle ?? this.subtitleTextStyle,
      headerInfoTextStyle: headerInfoTextStyle ?? this.headerInfoTextStyle,
      callToActionTextStyle:
          callToActionTextStyle ?? this.callToActionTextStyle,
      callToActionStyle: callToActionStyle ?? this.callToActionStyle,
      headerBackgroundColor:
          headerBackgroundColor ?? this.headerBackgroundColor,
      navBackgroundColor: navBackgroundColor ?? this.navBackgroundColor,
      navBarHeight: navBarHeight ?? this.navBarHeight,
      navItemTextStyle: navItemTextStyle ?? this.navItemTextStyle,
      navItemPadding: navItemPadding ?? this.navItemPadding,
      navItemGap: navItemGap ?? this.navItemGap,
      navCallToActionTextStyle:
          navCallToActionTextStyle ?? this.navCallToActionTextStyle,
      navCallToActionStyle: navCallToActionStyle ?? this.navCallToActionStyle,
    );
  }

  @override
  ThemeExtension<LandingHeaderTheme> lerp(
    covariant ThemeExtension<LandingHeaderTheme>? other,
    double t,
  ) {
    if (other is! LandingHeaderTheme) {
      return this;
    }

    return LandingHeaderTheme(
      titleSpacing:
          lerpDouble(titleSpacing, other.titleSpacing, t) ?? titleSpacing,
      avatarRadius:
          lerpDouble(avatarRadius, other.avatarRadius, t) ?? avatarRadius,
      logoIconSize:
          lerpDouble(logoIconSize, other.logoIconSize, t) ?? logoIconSize,
      logoGap: lerpDouble(logoGap, other.logoGap, t) ?? logoGap,
      logoAspectRatio:
          lerpDouble(logoAspectRatio, other.logoAspectRatio, t) ??
          logoAspectRatio,
      infoPadding: EdgeInsetsGeometry.lerp(infoPadding, other.infoPadding, t)!,
      ctaPadding: EdgeInsetsGeometry.lerp(ctaPadding, other.ctaPadding, t)!,
      logoBackgroundColor: Color.lerp(
        logoBackgroundColor,
        other.logoBackgroundColor,
        t,
      )!,
      logoIconColor: Color.lerp(logoIconColor, other.logoIconColor, t)!,
      headerInfoIconColor: Color.lerp(
        headerInfoIconColor,
        other.headerInfoIconColor,
        t,
      )!,
      titleTextStyle: TextStyle.lerp(titleTextStyle, other.titleTextStyle, t)!,
      subtitleTextStyle: TextStyle.lerp(
        subtitleTextStyle,
        other.subtitleTextStyle,
        t,
      )!,
      headerInfoTextStyle: TextStyle.lerp(
        headerInfoTextStyle,
        other.headerInfoTextStyle,
        t,
      )!,
      callToActionTextStyle: TextStyle.lerp(
        callToActionTextStyle,
        other.callToActionTextStyle,
        t,
      )!,
      callToActionStyle: ButtonStyle.lerp(
        callToActionStyle,
        other.callToActionStyle,
        t,
      )!,
      headerBackgroundColor: Color.lerp(
        headerBackgroundColor,
        other.headerBackgroundColor,
        t,
      )!,
      navBackgroundColor: Color.lerp(
        navBackgroundColor,
        other.navBackgroundColor,
        t,
      )!,
      navBarHeight:
          lerpDouble(navBarHeight, other.navBarHeight, t) ?? navBarHeight,
      navItemTextStyle: TextStyle.lerp(
        navItemTextStyle,
        other.navItemTextStyle,
        t,
      )!,
      navItemPadding: EdgeInsetsGeometry.lerp(
        navItemPadding,
        other.navItemPadding,
        t,
      )!,
      navItemGap: lerpDouble(navItemGap, other.navItemGap, t) ?? navItemGap,
      navCallToActionTextStyle: TextStyle.lerp(
        navCallToActionTextStyle,
        other.navCallToActionTextStyle,
        t,
      )!,
      navCallToActionStyle: ButtonStyle.lerp(
        navCallToActionStyle,
        other.navCallToActionStyle,
        t,
      )!,
    );
  }
}
