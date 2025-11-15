import 'dart:ui';

import 'package:flutter/material.dart';

import '../app_theme_tokens.dart';

/// Theme extension that describes styling for the service center section.
class LandingServiceCenterTheme
    extends ThemeExtension<LandingServiceCenterTheme> {
  const LandingServiceCenterTheme({
    required this.sectionPadding,
    required this.maxContentWidth,
    required this.compactBreakpoint,
    required this.headingTextStyle,
    required this.quoteTextStyle,
    required this.compactQuotePadding,
    required this.wideImageBorderRadius,
    required this.compactImageBorderRadius,
    required this.compactOverlayGradient,
  });

  factory LandingServiceCenterTheme.fromScheme({
    required ColorScheme colorScheme,
    required TextTheme textTheme,
  }) {
    return LandingServiceCenterTheme(
      sectionPadding: const EdgeInsets.symmetric(horizontal: 16),
      maxContentWidth: AppThemeTokens.contentMaxWidth,
      compactBreakpoint: 900,
      headingTextStyle:
          (textTheme.displaySmall ?? const TextStyle()).copyWith(
        color: AppThemeTokens.headerTextColor,
      ),
      quoteTextStyle:
          (textTheme.bodyMedium ?? const TextStyle()).copyWith(
        color: AppThemeTokens.textLight,
        fontWeight: FontWeight.w400,
      ),
      compactQuotePadding: const EdgeInsets.all(20),
      wideImageBorderRadius: BorderRadius.zero,
      compactImageBorderRadius: BorderRadius.zero,
      compactOverlayGradient: const LinearGradient(
        begin: Alignment.bottomCenter,
        end: Alignment.topCenter,
        colors: [
          AppThemeTokens.carouselOverlayStart,
          AppThemeTokens.carouselOverlayEnd,
        ],
      ),
    );
  }

  final EdgeInsetsGeometry sectionPadding;
  final double maxContentWidth;
  final double compactBreakpoint;
  final TextStyle headingTextStyle;
  final TextStyle quoteTextStyle;
  final EdgeInsetsGeometry compactQuotePadding;
  final BorderRadiusGeometry wideImageBorderRadius;
  final BorderRadiusGeometry compactImageBorderRadius;
  final Gradient compactOverlayGradient;

  @override
  LandingServiceCenterTheme copyWith({
    EdgeInsetsGeometry? sectionPadding,
    double? maxContentWidth,
    double? compactBreakpoint,
    TextStyle? headingTextStyle,
    TextStyle? quoteTextStyle,
    EdgeInsetsGeometry? compactQuotePadding,
    BorderRadiusGeometry? wideImageBorderRadius,
    BorderRadiusGeometry? compactImageBorderRadius,
    Gradient? compactOverlayGradient,
  }) {
    return LandingServiceCenterTheme(
      sectionPadding: sectionPadding ?? this.sectionPadding,
      maxContentWidth: maxContentWidth ?? this.maxContentWidth,
      compactBreakpoint: compactBreakpoint ?? this.compactBreakpoint,
      headingTextStyle: headingTextStyle ?? this.headingTextStyle,
      quoteTextStyle: quoteTextStyle ?? this.quoteTextStyle,
      compactQuotePadding: compactQuotePadding ?? this.compactQuotePadding,
      wideImageBorderRadius: wideImageBorderRadius ?? this.wideImageBorderRadius,
      compactImageBorderRadius:
          compactImageBorderRadius ?? this.compactImageBorderRadius,
      compactOverlayGradient:
          compactOverlayGradient ?? this.compactOverlayGradient,
    );
  }

  @override
  LandingServiceCenterTheme lerp(
    covariant ThemeExtension<LandingServiceCenterTheme>? other,
    double t,
  ) {
    if (other is! LandingServiceCenterTheme) {
      return this;
    }

    return LandingServiceCenterTheme(
      sectionPadding: EdgeInsetsGeometry.lerp(
            sectionPadding,
            other.sectionPadding,
            t,
          ) ??
          sectionPadding,
      maxContentWidth:
          lerpDouble(maxContentWidth, other.maxContentWidth, t) ??
          maxContentWidth,
      compactBreakpoint:
          lerpDouble(compactBreakpoint, other.compactBreakpoint, t) ??
          compactBreakpoint,
      headingTextStyle: TextStyle.lerp(
            headingTextStyle,
            other.headingTextStyle,
            t,
          ) ??
          headingTextStyle,
      quoteTextStyle: TextStyle.lerp(
            quoteTextStyle,
            other.quoteTextStyle,
            t,
          ) ??
          quoteTextStyle,
      compactQuotePadding: EdgeInsetsGeometry.lerp(
            compactQuotePadding,
            other.compactQuotePadding,
            t,
          ) ??
          compactQuotePadding,
      wideImageBorderRadius: BorderRadiusGeometry.lerp(
            wideImageBorderRadius,
            other.wideImageBorderRadius,
            t,
          ) ??
          wideImageBorderRadius,
      compactImageBorderRadius: BorderRadiusGeometry.lerp(
            compactImageBorderRadius,
            other.compactImageBorderRadius,
            t,
          ) ??
          compactImageBorderRadius,
      compactOverlayGradient: Gradient.lerp(
            compactOverlayGradient,
            other.compactOverlayGradient,
            t,
          ) ??
          compactOverlayGradient,
    );
  }
}
