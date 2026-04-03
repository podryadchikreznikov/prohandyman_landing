// dart format width=80
// GENERATED CODE - DO NOT MODIFY BY HAND

// **************************************************************************
// AutoRouterGenerator
// **************************************************************************

// ignore_for_file: type=lint
// coverage:ignore-file

part of 'router.dart';

/// generated route for
/// [AuthPlaceholderPage]
class AuthPlaceholderRoute extends PageRouteInfo<void> {
  const AuthPlaceholderRoute({List<PageRouteInfo>? children})
    : super(AuthPlaceholderRoute.name, initialChildren: children);

  static const String name = 'AuthPlaceholderRoute';

  static PageInfo page = PageInfo(
    name,
    builder: (data) {
      return const AuthPlaceholderPage();
    },
  );
}

/// generated route for
/// [EmptyRouterPage]
class EmptyRouterRoute extends PageRouteInfo<void> {
  const EmptyRouterRoute({List<PageRouteInfo>? children})
    : super(EmptyRouterRoute.name, initialChildren: children);

  static const String name = 'EmptyRouterRoute';

  static PageInfo page = PageInfo(
    name,
    builder: (data) {
      return const EmptyRouterPage();
    },
  );
}

/// generated route for
/// [LandingAboutPage]
class LandingAboutRoute extends PageRouteInfo<void> {
  const LandingAboutRoute({List<PageRouteInfo>? children})
    : super(LandingAboutRoute.name, initialChildren: children);

  static const String name = 'LandingAboutRoute';

  static PageInfo page = PageInfo(
    name,
    builder: (data) {
      return const LandingAboutPage();
    },
  );
}

/// generated route for
/// [LandingContactsPage]
class LandingContactsRoute extends PageRouteInfo<void> {
  const LandingContactsRoute({List<PageRouteInfo>? children})
    : super(LandingContactsRoute.name, initialChildren: children);

  static const String name = 'LandingContactsRoute';

  static PageInfo page = PageInfo(
    name,
    builder: (data) {
      return const LandingContactsPage();
    },
  );
}

/// generated route for
/// [LandingHomePage]
class LandingHomeRoute extends PageRouteInfo<void> {
  const LandingHomeRoute({List<PageRouteInfo>? children})
    : super(LandingHomeRoute.name, initialChildren: children);

  static const String name = 'LandingHomeRoute';

  static PageInfo page = PageInfo(
    name,
    builder: (data) {
      return const LandingHomePage();
    },
  );
}

/// generated route for
/// [LandingPartnersPage]
class LandingPartnersRoute extends PageRouteInfo<void> {
  const LandingPartnersRoute({List<PageRouteInfo>? children})
    : super(LandingPartnersRoute.name, initialChildren: children);

  static const String name = 'LandingPartnersRoute';

  static PageInfo page = PageInfo(
    name,
    builder: (data) {
      return const LandingPartnersPage();
    },
  );
}

/// generated route for
/// [LandingServicesPage]
class LandingServicesRoute extends PageRouteInfo<LandingServicesRouteArgs> {
  LandingServicesRoute({
    Key? key,
    String? section,
    List<PageRouteInfo>? children,
  }) : super(
         LandingServicesRoute.name,
         args: LandingServicesRouteArgs(key: key, section: section),
         rawQueryParams: {'section': section},
         initialChildren: children,
       );

  static const String name = 'LandingServicesRoute';

  static PageInfo page = PageInfo(
    name,
    builder: (data) {
      final queryParams = data.queryParams;
      final args = data.argsAs<LandingServicesRouteArgs>(
        orElse: () =>
            LandingServicesRouteArgs(section: queryParams.optString('section')),
      );
      return LandingServicesPage(key: args.key, section: args.section);
    },
  );
}

class LandingServicesRouteArgs {
  const LandingServicesRouteArgs({this.key, this.section});

  final Key? key;

  final String? section;

  @override
  String toString() {
    return 'LandingServicesRouteArgs{key: $key, section: $section}';
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    if (other is! LandingServicesRouteArgs) return false;
    return key == other.key && section == other.section;
  }

  @override
  int get hashCode => key.hashCode ^ section.hashCode;
}
