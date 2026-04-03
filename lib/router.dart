import 'package:auto_route/auto_route.dart';
import 'package:flutter/material.dart';

import 'core/constants/constants.dart';
import 'features/landing/presentation/pages/landing_contacts_page.dart';
import 'features/landing/presentation/pages/landing_home_page.dart';
import 'features/landing/presentation/pages/landing_about_page.dart';
import 'features/landing/presentation/pages/landing_partners_page.dart';
import 'features/landing/presentation/pages/landing_services_page.dart';
import 'presentation/pages/auth_placeholder_page.dart';
import 'presentation/pages/empty_router_page.dart';

part 'router.gr.dart';

/// Central application router built with `auto_route`.
///
/// Add new feature entry points here and keep the structure flat
/// until a concrete flow requires nested routes.
@AutoRouterConfig(replaceInRouteName: 'Page,Route')
class AppRouter extends RootStackRouter {
  AppRouter({super.navigatorKey});

  @override
  RouteType get defaultRouteType => RouteType.custom(
        transitionsBuilder: (context, animation, secondaryAnimation, child) {
          return FadeTransition(opacity: animation, child: child);
        },
        duration: const Duration(milliseconds: 500),
        reverseDuration: const Duration(milliseconds: 500),
      );

  @override
  List<AutoRoute> get routes => [
        AutoRoute(
          page: LandingHomeRoute.page,
          path: RoutePaths.root,
          initial: true,
        ),
        AutoRoute(
          page: LandingAboutRoute.page,
          path: RoutePaths.about,
        ),
        AutoRoute(
          page: LandingServicesRoute.page,
          path: RoutePaths.services,
        ),
        AutoRoute(
          page: LandingPartnersRoute.page,
          path: RoutePaths.partners,
        ),
        AutoRoute(
          page: LandingContactsRoute.page,
          path: RoutePaths.contacts,
        ),
        AutoRoute(
          page: AuthPlaceholderRoute.page,
          path: RoutePaths.auth,
        ),
        AutoRoute(
          page: EmptyRouterRoute.page,
          path: RoutePaths.placeholder,
        ), // kept as nested shell placeholder
      ];
}
