import 'package:auto_route/auto_route.dart';
import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';
import 'package:prohandyman_landing/core/theme/extensions/landing_header_theme.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_footer.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_home_header.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_services_overview_section.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_services_pricing_section.dart';
import 'package:prohandyman_landing/presentation/widgets/tilt_wrapper.dart';

@RoutePage()
class LandingServicesPage extends StatefulWidget {
  const LandingServicesPage({
    super.key,
    @queryParam this.section,
  });

  final String? section;

  @override
  State<LandingServicesPage> createState() => _LandingServicesPageState();
}

class _LandingServicesPageState extends State<LandingServicesPage> {
  late final TiltGlobalPointerController _tiltPointerController;
  late final ScrollController _scrollController;
  final GlobalKey _pricingSectionKey = GlobalKey();
  String? _lastSection;

  @override
  void initState() {
    super.initState();
    _scrollController = ScrollController();
    _tiltPointerController = TiltGlobalPointerController();
  }

  @override
  void dispose() {
    _scrollController.dispose();
    _tiltPointerController.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant LandingServicesPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    _syncScrollWithSection(widget.section);
  }

  void _syncScrollWithSection(String? section) {
    if (_lastSection == section) {
      return;
    }
    _lastSection = section;

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) {
        return;
      }

      if (!(_scrollController.hasClients)) {
        return;
      }

      if (section == 'prices') {
        final context = _pricingSectionKey.currentContext;
        if (context != null) {
          Scrollable.ensureVisible(
            context,
            alignment: 0,
            duration: const Duration(milliseconds: 1),
          );
          return;
        }
      }

      if (_scrollController.offset != 0) {
        _scrollController.jumpTo(0);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    _syncScrollWithSection(widget.section);

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
          const _ServicesPatternBackgroundLayer(),
          Padding(
            padding: const EdgeInsets.only(top: AppThemeTokens.pageTopPadding),
            child: Scaffold(
              backgroundColor: Colors.transparent,
              appBar: header,
              body: SingleChildScrollView(
                controller: _scrollController,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const SizedBox(height: 32),
                    const LandingServicesOverviewSection(),
                    const SizedBox(height: 64),
                    KeyedSubtree(
                      key: _pricingSectionKey,
                      child: const LandingServicesPricingSection(),
                    ),
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

class _ServicesPatternBackgroundLayer extends StatelessWidget {
  const _ServicesPatternBackgroundLayer();

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
