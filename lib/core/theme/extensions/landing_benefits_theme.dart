import 'dart:ui';

import 'package:flutter/material.dart';

import '../app_theme_tokens.dart';

/// Theme extension describing the "why us" benefits section.
class LandingBenefitsTheme extends ThemeExtension<LandingBenefitsTheme> {
  const LandingBenefitsTheme({
    required this.sectionPadding,
    required this.maxContentWidth,
    required this.compactBreakpoint,
    required this.headingTextStyle,
    required this.itemTitleTextStyle,
    required this.itemDescriptionTextStyle,
    required this.compactTitleTextStyle,
    required this.iconColor,
    required this.iconSize,
    required this.itemsHorizontalGap,
    required this.itemsVerticalGap,
    required this.compactItemsHorizontalGap,
    required this.compactItemsVerticalGap,
    required this.compactMinTileWidth,
    required this.headerBodySpacing,
    required this.itemInnerSpacing,
  });

  factory LandingBenefitsTheme.fromScheme({
    required ColorScheme colorScheme,
    required TextTheme textTheme,
  }) {
    return LandingBenefitsTheme(
      sectionPadding: const EdgeInsets.symmetric(horizontal: 16),
      maxContentWidth: AppThemeTokens.contentMaxWidth,
      compactBreakpoint: 900,
      headingTextStyle:
          (textTheme.displaySmall ?? const TextStyle()).copyWith(
        fontWeight: FontWeight.w500,
      ),
      itemTitleTextStyle:
          (textTheme.titleMedium ?? const TextStyle()).copyWith(
        fontWeight: FontWeight.w600,
        color: AppThemeTokens.headerTextColor,
      ),
      itemDescriptionTextStyle:
          (textTheme.bodySmall ?? const TextStyle()).copyWith(
        color: colorScheme.onSurface.withOpacity(0.8),
      ),
      compactTitleTextStyle: textTheme.titleMedium ?? const TextStyle(),
      iconColor: AppThemeTokens.landingNavBlue,
      iconSize: 42,
      itemsHorizontalGap: 48,
      itemsVerticalGap: 32,
      compactItemsHorizontalGap: 24,
      compactItemsVerticalGap: 28,
      compactMinTileWidth: 140,
      headerBodySpacing: 40,
      itemInnerSpacing: 12,
    );
  }

  final EdgeInsetsGeometry sectionPadding;
  final double maxContentWidth;
  final double compactBreakpoint;
  final TextStyle headingTextStyle;
  final TextStyle itemTitleTextStyle;
  final TextStyle itemDescriptionTextStyle;
  final TextStyle compactTitleTextStyle;
  final Color iconColor;
  final double iconSize;
  final double itemsHorizontalGap;
  final double itemsVerticalGap;
  final double compactItemsHorizontalGap;
  final double compactItemsVerticalGap;
  final double compactMinTileWidth;
  final double headerBodySpacing;
  final double itemInnerSpacing;

  @override
  LandingBenefitsTheme copyWith({
    EdgeInsetsGeometry? sectionPadding,
    double? maxContentWidth,
    double? compactBreakpoint,
    TextStyle? headingTextStyle,
    TextStyle? itemTitleTextStyle,
    TextStyle? itemDescriptionTextStyle,
    TextStyle? compactTitleTextStyle,
    Color? iconColor,
    double? iconSize,
    double? itemsHorizontalGap,
    double? itemsVerticalGap,
    double? compactItemsHorizontalGap,
    double? compactItemsVerticalGap,
    double? compactMinTileWidth,
    double? headerBodySpacing,
    double? itemInnerSpacing,
  }) {
    return LandingBenefitsTheme(
      sectionPadding: sectionPadding ?? this.sectionPadding,
      maxContentWidth: maxContentWidth ?? this.maxContentWidth,
      compactBreakpoint: compactBreakpoint ?? this.compactBreakpoint,
      headingTextStyle: headingTextStyle ?? this.headingTextStyle,
      itemTitleTextStyle: itemTitleTextStyle ?? this.itemTitleTextStyle,
      itemDescriptionTextStyle:
          itemDescriptionTextStyle ?? this.itemDescriptionTextStyle,
      compactTitleTextStyle:
          compactTitleTextStyle ?? this.compactTitleTextStyle,
      iconColor: iconColor ?? this.iconColor,
      iconSize: iconSize ?? this.iconSize,
      itemsHorizontalGap: itemsHorizontalGap ?? this.itemsHorizontalGap,
      itemsVerticalGap: itemsVerticalGap ?? this.itemsVerticalGap,
      compactItemsHorizontalGap:
          compactItemsHorizontalGap ?? this.compactItemsHorizontalGap,
      compactItemsVerticalGap:
          compactItemsVerticalGap ?? this.compactItemsVerticalGap,
      compactMinTileWidth: compactMinTileWidth ?? this.compactMinTileWidth,
      headerBodySpacing: headerBodySpacing ?? this.headerBodySpacing,
      itemInnerSpacing: itemInnerSpacing ?? this.itemInnerSpacing,
    );
  }

  @override
  LandingBenefitsTheme lerp(
    covariant ThemeExtension<LandingBenefitsTheme>? other,
    double t,
  ) {
    if (other is! LandingBenefitsTheme) {
      return this;
    }

    return LandingBenefitsTheme(
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
      itemTitleTextStyle: TextStyle.lerp(
            itemTitleTextStyle,
            other.itemTitleTextStyle,
            t,
          ) ??
          itemTitleTextStyle,
      itemDescriptionTextStyle: TextStyle.lerp(
            itemDescriptionTextStyle,
            other.itemDescriptionTextStyle,
            t,
          ) ??
          itemDescriptionTextStyle,
      compactTitleTextStyle: TextStyle.lerp(
            compactTitleTextStyle,
            other.compactTitleTextStyle,
            t,
          ) ??
          compactTitleTextStyle,
      iconColor: Color.lerp(iconColor, other.iconColor, t) ?? iconColor,
      iconSize: lerpDouble(iconSize, other.iconSize, t) ?? iconSize,
      itemsHorizontalGap: lerpDouble(
            itemsHorizontalGap,
            other.itemsHorizontalGap,
            t,
          ) ??
          itemsHorizontalGap,
      itemsVerticalGap: lerpDouble(
            itemsVerticalGap,
            other.itemsVerticalGap,
            t,
          ) ??
          itemsVerticalGap,
      compactItemsHorizontalGap: lerpDouble(
            compactItemsHorizontalGap,
            other.compactItemsHorizontalGap,
            t,
          ) ??
          compactItemsHorizontalGap,
      compactItemsVerticalGap: lerpDouble(
            compactItemsVerticalGap,
            other.compactItemsVerticalGap,
            t,
          ) ??
          compactItemsVerticalGap,
      compactMinTileWidth:
          lerpDouble(compactMinTileWidth, other.compactMinTileWidth, t) ??
          compactMinTileWidth,
      headerBodySpacing: lerpDouble(
            headerBodySpacing,
            other.headerBodySpacing,
            t,
          ) ??
          headerBodySpacing,
      itemInnerSpacing: lerpDouble(
            itemInnerSpacing,
            other.itemInnerSpacing,
            t,
          ) ??
          itemInnerSpacing,
    );
  }
}
