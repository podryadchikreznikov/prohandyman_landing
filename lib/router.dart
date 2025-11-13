import 'package:auto_route/auto_route.dart';

import 'core/constants/constants.dart';
import 'features/landing/presentation/pages/landing_home_page.dart';
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
  List<AutoRoute> get routes => [
        AutoRoute(
          page: LandingHomeRoute.page,
          path: RoutePaths.root,
          initial: true,
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
