import 'package:auto_route/auto_route.dart';
import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';
import 'package:prohandyman_landing/core/theme/extensions/landing_header_theme.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_home_body.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_home_header.dart';

/// Placeholder for the future landing home screen.
@RoutePage()
class LandingHomePage extends StatefulWidget {
  const LandingHomePage({super.key});

  @override
  State<LandingHomePage> createState() => _LandingHomePageState();
}

class _LandingHomePageState extends State<LandingHomePage> {
  bool? _useCompactHeader;
  double? _initialViewportWidth;
  late final ScrollController _scrollController;
  double _lastScrollOffset = 0;
  double _headerTranslation = 0;
  double? _headerExtent;

  @override
  void initState() {
    super.initState();
    _scrollController = ScrollController()..addListener(_handleScroll);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_useCompactHeader == null) {
      final mediaQuery = MediaQuery.of(context);
      _useCompactHeader =
          mediaQuery.size.width <
          AppThemeTokens.landingHeaderCompactHeightBreakpoint;
      _initialViewportWidth = mediaQuery.size.width;
    }
  }

  void _handleScroll() {
    final extent = _headerExtent;
    final offset = _scrollController.hasClients ? _scrollController.offset : 0.0;
    final delta = offset - _lastScrollOffset;
    _lastScrollOffset = offset;

    if (extent == null || delta == 0) {
      return;
    }

    final nextTranslation = (_headerTranslation - delta)
        .clamp(-extent, 0.0)
        .toDouble();
    if ((nextTranslation - _headerTranslation).abs() > 0.1) {
      setState(() => _headerTranslation = nextTranslation);
    }
  }

  @override
  void dispose() {
    _scrollController.removeListener(_handleScroll);
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final mediaQuery = MediaQuery.of(context);
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

    final useCompactHeader = _useCompactHeader ?? false;
    final viewportWidth = _initialViewportWidth ?? mediaQuery.size.width;

    final wideHeader = LandingWideHeaderAppBar(
      headerTheme: headerTheme,
      backgroundColor: appBarBackgroundColor,
      foregroundColor: appBarForegroundColor,
    );

    final compactHeader = LandingCompactHeaderAppBar(
      headerTheme: headerTheme,
      backgroundColor: appBarBackgroundColor,
      foregroundColor: appBarForegroundColor,
      viewportWidth: viewportWidth,
    );

    final PreferredSizeWidget header =
        useCompactHeader ? compactHeader : wideHeader;
    final headerHeight = header.preferredSize.height;
    _headerExtent = headerHeight;
    _headerTranslation =
        _headerTranslation.clamp(-headerHeight, 0.0).toDouble();
    final headerVisibleHeight = (headerHeight + _headerTranslation)
        .clamp(0.0, headerHeight)
        .toDouble();

    return Stack(
      children: [
        const _PatternBackgroundLayer(),
        Padding(
          padding: const EdgeInsets.only(top: AppThemeTokens.pageTopPadding),
          child: Scaffold(
            backgroundColor: Colors.transparent,
            body: Stack(
              clipBehavior: Clip.none,
              children: [
                SingleChildScrollView(
                  controller: _scrollController,
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(minHeight: 5000),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        SizedBox(height: headerVisibleHeight),
                        const LandingHomeBody(),
                      ],
                    ),
                  ),
                ),
                Positioned(
                  top: 0,
                  left: 0,
                  right: 0,
                  child: Transform.translate(
                    offset: Offset(0, _headerTranslation),
                    child: header,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

/// Отдельный слой фона с паттерном, «запечённый» в RepaintBoundary,
/// чтобы не перерисовываться при каждом изменении контента поверх.
class _PatternBackgroundLayer extends StatelessWidget {
  const _PatternBackgroundLayer();

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
