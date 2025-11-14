import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';
import 'package:prohandyman_landing/core/theme/extensions/landing_header_theme.dart';

part 'landing_home_header_wide.dart';
part 'landing_home_header_compact.dart';
part 'landing_home_header_shared.dart';

/// Full-width landing header for wide layouts.
class LandingWideHeaderAppBar extends StatelessWidget
    implements PreferredSizeWidget {
  const LandingWideHeaderAppBar({
    super.key,
    required this.headerTheme,
    required this.backgroundColor,
    required this.foregroundColor,
  });

  final LandingHeaderTheme headerTheme;
  final Color backgroundColor;
  final Color foregroundColor;

  @override
  Size get preferredSize {
    final headerHeight = _LandingHomeHeaderWide.headerHeight();
    return Size.fromHeight(headerHeight + headerTheme.navBarHeight);
  }

  @override
  Widget build(BuildContext context) {
    final headerBody = _LandingHomeHeaderWide.buildBody(headerTheme);
    return _LandingHeaderShell(
      backgroundColor: backgroundColor,
      foregroundColor: foregroundColor,
      headerTheme: headerTheme,
      headerBody: headerBody,
      navWidget: _NavBar(theme: headerTheme),
    );
  }
}

/// Compact landing header with adaptive height and scroll-aware behavior.
class LandingCompactHeaderAppBar extends StatelessWidget
    implements PreferredSizeWidget {
  const LandingCompactHeaderAppBar({
    super.key,
    required this.headerTheme,
    required this.backgroundColor,
    required this.foregroundColor,
    required this.viewportWidth,
  });

  final LandingHeaderTheme headerTheme;
  final Color backgroundColor;
  final Color foregroundColor;
  final double viewportWidth;

  double get _effectiveWidth =>
      viewportWidth.clamp(0, AppThemeTokens.contentMaxWidth).toDouble();

  double get _horizontalPadding =>
      headerTheme.titleSpacing.clamp(0.0, _effectiveWidth / 4).toDouble();

  double get _contentWidth => (_effectiveWidth - _horizontalPadding * 2)
      .clamp(0.0, _effectiveWidth)
      .toDouble();

  @override
  Size get preferredSize {
    final headerHeight = _LandingHomeHeaderCompact.headerHeight(
      _contentWidth,
      headerTheme,
    );
    return Size.fromHeight(headerHeight + headerTheme.navBarHeight);
  }

  @override
  Widget build(BuildContext context) {
    final headerBody = _LandingHomeHeaderCompact.buildBody(
      headerTheme,
      _contentWidth,
    );
    return _LandingHeaderShell(
      backgroundColor: backgroundColor,
      foregroundColor: foregroundColor,
      headerTheme: headerTheme,
      headerBody: headerBody,
      navWidget: _CompactNavigationMenu(theme: headerTheme),
    );
  }
}
