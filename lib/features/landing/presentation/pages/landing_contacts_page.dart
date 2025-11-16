import 'package:auto_route/auto_route.dart';
import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';
import 'package:prohandyman_landing/core/theme/extensions/landing_header_theme.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/callback_request/landing_callback_request_section.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_footer.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_home_header.dart';

@RoutePage()
class LandingContactsPage extends StatelessWidget {
  const LandingContactsPage({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final headerTheme = theme.extension<LandingHeaderTheme>();
    assert(
      headerTheme != null,
      'LandingHeaderTheme must be provided via AppTheme extensions.',
    );
    if (headerTheme == null) {
      return const SizedBox.shrink();
    }

    final appBarBackgroundColor = headerTheme.headerBackgroundColor;
    final appBarForegroundColor =
        headerTheme.headerInfoTextStyle.color ??
        theme.appBarTheme.foregroundColor ??
        theme.colorScheme.onSurface;

    final header = LandingWideHeaderAppBar(
      headerTheme: headerTheme,
      backgroundColor: appBarBackgroundColor,
      foregroundColor: appBarForegroundColor,
    );

    return Stack(
      children: [
        const _ContactsPatternBackgroundLayer(),
        Padding(
          padding: const EdgeInsets.only(top: AppThemeTokens.pageTopPadding),
          child: Scaffold(
            backgroundColor: Colors.transparent,
            appBar: header,
            body: const SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  SizedBox(height: 32),
                  LandingCallbackRequestSection(),
                  SizedBox(height: 80),
                  LandingFooter(),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _ContactsPatternBackgroundLayer extends StatelessWidget {
  const _ContactsPatternBackgroundLayer();

  @override
  Widget build(BuildContext context) {
    return const Positioned.fill(
      child: RepaintBoundary(
        child: DecoratedBox(
          decoration: BoxDecoration(
            image: DecorationImage(
              repeat: ImageRepeat.repeat,
              alignment: Alignment.topLeft,
              image: AssetImage('assets/pattern.png'),
            ),
          ),
        ),
      ),
    );
  }
}
