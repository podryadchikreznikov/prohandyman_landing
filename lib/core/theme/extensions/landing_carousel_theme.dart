import 'dart:ui';

import 'package:flutter/material.dart';

import '../app_theme_tokens.dart';

/// Theme extension that describes the hero carousel styling.
class LandingCarouselTheme extends ThemeExtension<LandingCarouselTheme> {
  const LandingCarouselTheme({
    required this.height,
    required this.maxWidth,
    required this.borderRadius,
    required this.overlayGradient,
    required this.titleTextStyle,
    required this.subtitleTextStyle,
    required this.contentPadding,
    required this.indicatorActiveColor,
    required this.indicatorInactiveColor,
    required this.indicatorSize,
    required this.indicatorSpacing,
    required this.arrowBackgroundColor,
    required this.arrowIconColor,
    required this.arrowButtonSize,
    required this.autoPlayInterval,
    required this.slideAnimationDuration,
  });

  factory LandingCarouselTheme.fromScheme({
    required ColorScheme colorScheme,
    required TextTheme textTheme,
  }) {
    return LandingCarouselTheme(
      height: AppThemeTokens.carouselHeight,
      maxWidth: AppThemeTokens.carouselMaxWidth,
      borderRadius: BorderRadius.circular(AppThemeTokens.carouselBorderRadius),
      overlayGradient: const LinearGradient(
        begin: Alignment.bottomCenter,
        end: Alignment.topCenter,
        colors: [
          AppThemeTokens.carouselOverlayStart,
          AppThemeTokens.carouselOverlayEnd,
        ],
      ),
      titleTextStyle: (textTheme.headlineSmall ?? const TextStyle()).copyWith(
        color: AppThemeTokens.textLight,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.6,
      ),
      subtitleTextStyle: (textTheme.titleMedium ?? const TextStyle()).copyWith(
        color: AppThemeTokens.textLightMuted,
        fontWeight: FontWeight.w500,
      ),
      contentPadding: const EdgeInsets.fromLTRB(32, 32, 32, 40),
      indicatorActiveColor: AppThemeTokens.textLight,
      indicatorInactiveColor: AppThemeTokens.textLightMuted,
      indicatorSize: 10,
      indicatorSpacing: 8,
      arrowBackgroundColor: AppThemeTokens.carouselArrowBackground,
      arrowIconColor: AppThemeTokens.textLight,
      arrowButtonSize: 44,
      autoPlayInterval: const Duration(seconds: 10),
      slideAnimationDuration: const Duration(milliseconds: 600),
    );
  }

  final double height;
  final double maxWidth;
  final BorderRadiusGeometry borderRadius;
  final Gradient overlayGradient;
  final TextStyle titleTextStyle;
  final TextStyle subtitleTextStyle;
  final EdgeInsetsGeometry contentPadding;
  final Color indicatorActiveColor;
  final Color indicatorInactiveColor;
  final double indicatorSize;
  final double indicatorSpacing;
  final Color arrowBackgroundColor;
  final Color arrowIconColor;
  final double arrowButtonSize;
  final Duration autoPlayInterval;
  final Duration slideAnimationDuration;

  @override
  ThemeExtension<LandingCarouselTheme> copyWith({
    double? height,
    double? maxWidth,
    BorderRadiusGeometry? borderRadius,
    Gradient? overlayGradient,
    TextStyle? titleTextStyle,
    TextStyle? subtitleTextStyle,
    EdgeInsetsGeometry? contentPadding,
    Color? indicatorActiveColor,
    Color? indicatorInactiveColor,
    double? indicatorSize,
    double? indicatorSpacing,
    Color? arrowBackgroundColor,
    Color? arrowIconColor,
    double? arrowButtonSize,
    Duration? autoPlayInterval,
    Duration? slideAnimationDuration,
  }) {
    return LandingCarouselTheme(
      height: height ?? this.height,
      maxWidth: maxWidth ?? this.maxWidth,
      borderRadius: borderRadius ?? this.borderRadius,
      overlayGradient: overlayGradient ?? this.overlayGradient,
      titleTextStyle: titleTextStyle ?? this.titleTextStyle,
      subtitleTextStyle: subtitleTextStyle ?? this.subtitleTextStyle,
      contentPadding: contentPadding ?? this.contentPadding,
      indicatorActiveColor: indicatorActiveColor ?? this.indicatorActiveColor,
      indicatorInactiveColor:
          indicatorInactiveColor ?? this.indicatorInactiveColor,
      indicatorSize: indicatorSize ?? this.indicatorSize,
      indicatorSpacing: indicatorSpacing ?? this.indicatorSpacing,
      arrowBackgroundColor: arrowBackgroundColor ?? this.arrowBackgroundColor,
      arrowIconColor: arrowIconColor ?? this.arrowIconColor,
      arrowButtonSize: arrowButtonSize ?? this.arrowButtonSize,
      autoPlayInterval: autoPlayInterval ?? this.autoPlayInterval,
      slideAnimationDuration:
          slideAnimationDuration ?? this.slideAnimationDuration,
    );
  }

  @override
  ThemeExtension<LandingCarouselTheme> lerp(
    covariant ThemeExtension<LandingCarouselTheme>? other,
    double t,
  ) {
    if (other is! LandingCarouselTheme) {
      return this;
    }

    return LandingCarouselTheme(
      height: lerpDouble(height, other.height, t) ?? height,
      maxWidth: lerpDouble(maxWidth, other.maxWidth, t) ?? maxWidth,
      borderRadius: BorderRadiusGeometry.lerp(
        borderRadius,
        other.borderRadius,
        t,
      )!,
      overlayGradient: Gradient.lerp(
        overlayGradient,
        other.overlayGradient,
        t,
      )!,
      titleTextStyle: TextStyle.lerp(titleTextStyle, other.titleTextStyle, t)!,
      subtitleTextStyle: TextStyle.lerp(
        subtitleTextStyle,
        other.subtitleTextStyle,
        t,
      )!,
      contentPadding: EdgeInsetsGeometry.lerp(
        contentPadding,
        other.contentPadding,
        t,
      )!,
      indicatorActiveColor: Color.lerp(
        indicatorActiveColor,
        other.indicatorActiveColor,
        t,
      )!,
      indicatorInactiveColor: Color.lerp(
        indicatorInactiveColor,
        other.indicatorInactiveColor,
        t,
      )!,
      indicatorSize:
          lerpDouble(indicatorSize, other.indicatorSize, t) ?? indicatorSize,
      indicatorSpacing:
          lerpDouble(indicatorSpacing, other.indicatorSpacing, t) ??
          indicatorSpacing,
      arrowBackgroundColor: Color.lerp(
        arrowBackgroundColor,
        other.arrowBackgroundColor,
        t,
      )!,
      arrowIconColor: Color.lerp(arrowIconColor, other.arrowIconColor, t)!,
      arrowButtonSize:
          lerpDouble(arrowButtonSize, other.arrowButtonSize, t) ??
          arrowButtonSize,
      autoPlayInterval: _lerpDuration(
        autoPlayInterval,
        other.autoPlayInterval,
        t,
      ),
      slideAnimationDuration: _lerpDuration(
        slideAnimationDuration,
        other.slideAnimationDuration,
        t,
      ),
    );
  }

  static Duration _lerpDuration(Duration a, Duration b, double t) {
    return Duration(
      microseconds: lerpDouble(
        a.inMicroseconds.toDouble(),
        b.inMicroseconds.toDouble(),
        t,
      )!.round(),
    );
  }
}
