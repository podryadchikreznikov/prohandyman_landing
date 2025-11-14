part of 'landing_home_header.dart';

class _LandingHomeHeaderWide {
  static double headerHeight() => AppThemeTokens.landingHeaderHeight;

  static Widget buildBody(LandingHeaderTheme theme) {
    return SizedBox(
      height: headerHeight(),
      child: _LandingHeaderBody(theme: theme),
    );
  }
}
