import 'package:auto_route/auto_route.dart';
import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';
import 'package:prohandyman_landing/core/theme/extensions/landing_header_theme.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_footer.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_home_header.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_service_center_section.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_why_us_benefits.dart';
import 'package:prohandyman_landing/presentation/widgets/tilt_wrapper.dart';

@RoutePage()
class LandingAboutPage extends StatefulWidget {
  const LandingAboutPage({super.key});

  @override
  State<LandingAboutPage> createState() => _LandingAboutPageState();
}

class _LandingAboutPageState extends State<LandingAboutPage> {
  late final TiltGlobalPointerController _tiltPointerController;

  @override
  void initState() {
    super.initState();
    _tiltPointerController = TiltGlobalPointerController();
  }

  @override
  void dispose() {
    _tiltPointerController.dispose();
    super.dispose();
  }

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

    return MouseRegion(
      onHover: (event) =>
          _tiltPointerController.updatePosition(event.position),
      onExit: (_) => _tiltPointerController.updatePosition(null),
      child: Stack(
        children: [
          const _AboutPatternBackgroundLayer(),
          Padding(
            padding: const EdgeInsets.only(top: AppThemeTokens.pageTopPadding),
            child: Scaffold(
              backgroundColor: Colors.transparent,
              appBar: header,
              body: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const SizedBox(height: 32),
                    LandingServiceCenterSection(
                      tiltPointerController: _tiltPointerController,
                    ),
                    const SizedBox(height: 64),
                    const LandingWhyUsBenefitsSection(),
                    const SizedBox(height: 80),
                    const LandingFooter(),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _AboutPatternBackgroundLayer extends StatelessWidget {
  const _AboutPatternBackgroundLayer();

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
