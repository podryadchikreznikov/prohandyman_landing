// lib/features/landing/presentation/widgets/landing_hero_carousel.dart
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/extensions/landing_carousel_theme.dart';

/// Hero carousel that showcases marketing slides on the landing page.
class LandingHeroCarousel extends StatefulWidget {
  const LandingHeroCarousel({super.key});

  @override
  State<LandingHeroCarousel> createState() => _LandingHeroCarouselState();
}

class _LandingHeroCarouselState extends State<LandingHeroCarousel> {
  static const _slides = [
    _LandingCarouselSlide(
      assetPath: 'assets/slides/slide1.jpg',
      title: 'Выездной ремонт бытовой техники в Екатеринбурге',
      subtitle: 'Срочная диагностика и восстановление на дому и в офисе',
    ),
    _LandingCarouselSlide(
      assetPath: 'assets/slides/slide2.jpg',
      title: 'Постгарантийное обслуживание премиальных брендов',
      subtitle: 'Сертифицированные мастера и оригинальные комплектующие',
    ),
    _LandingCarouselSlide(
      assetPath: 'assets/slides/slide3.jpg',
      title: 'Комплексная модернизация кухонных студий',
      subtitle: 'Проектирование, монтаж и настройка техники под ключ',
    ),
  ];

  static final Map<String, AssetImage> _assetImages = {
    for (final slide in _slides) slide.assetPath: AssetImage(slide.assetPath),
  };

  Timer? _autoPlayTimer;
  Duration? _currentInterval;
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        unawaited(_precacheSlides());
      }
    });
  }

  @override
  void dispose() {
    _autoPlayTimer?.cancel();
    super.dispose();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final theme = Theme.of(context).extension<LandingCarouselTheme>();
    final interval = theme?.autoPlayInterval ?? const Duration(seconds: 10);
    if (interval != _currentInterval) {
      _currentInterval = interval;
      _restartAutoPlay(interval);
    }
  }

  Future<void> _precacheSlides() async {
    final context = this.context;
    for (final image in _assetImages.values) {
      try {
        await precacheImage(image, context);
      } catch (_) {
        // Ignore failures; we'll still show the fallback loader.
      }
      if (!mounted) return;
    }
  }

  void _restartAutoPlay(Duration interval) {
    _autoPlayTimer?.cancel();
    _autoPlayTimer = Timer.periodic(interval, (_) => _changeSlide(1));
  }

  void _changeSlide(int delta, {bool resetTimer = false}) {
    setState(() {
      final length = _slides.length;
      _currentIndex = (_currentIndex + delta + length) % length;
    });
    if (resetTimer && _currentInterval != null) {
      _restartAutoPlay(_currentInterval!);
    }
  }

  @override
  Widget build(BuildContext context) {
    final carouselTheme = Theme.of(context).extension<LandingCarouselTheme>();
    assert(
      carouselTheme != null,
      'LandingCarouselTheme must be provided via AppTheme extensions.',
    );
    if (carouselTheme == null) {
      return const SizedBox.shrink();
    }

    final slide = _slides[_currentIndex];
    final image = _assetImages[slide.assetPath]!;

    return Center(
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: carouselTheme.maxWidth),
        child: Padding(
          padding: const EdgeInsets.only(bottom: 24),
          child: SizedBox(
            height: carouselTheme.height,
            child: Stack(
              fit: StackFit.expand,
              children: [
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 350),
                  switchInCurve: Curves.easeIn,
                  switchOutCurve: Curves.easeOut,
                  layoutBuilder: (currentChild, previousChildren) {
                    return Stack(
                      fit: StackFit.expand,
                      children: [
                        ...previousChildren,
                        if (currentChild != null) currentChild,
                      ],
                    );
                  },
                  child: _CarouselSlide(
                    key: ValueKey(slide.assetPath),
                    image: image,
                    semanticsLabel: slide.title,
                  ),
                ),
                Positioned.fill(
                  child: IgnorePointer(
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        gradient: carouselTheme.overlayGradient,
                      ),
                    ),
                  ),
                ),
                _buildSlideContent(carouselTheme, slide),
                _buildArrowButtons(carouselTheme),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSlideContent(
    LandingCarouselTheme theme,
    _LandingCarouselSlide slide,
  ) {
    return Align(
      alignment: Alignment.bottomCenter,
      child: Padding(
        padding: theme.contentPadding,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Text(
              slide.title,
              style: theme.titleTextStyle,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              slide.subtitle,
              style: theme.subtitleTextStyle,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            _CarouselIndicators(
              itemCount: _slides.length,
              currentIndex: _currentIndex,
              theme: theme,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildArrowButtons(LandingCarouselTheme theme) {
    return Positioned.fill(
      child: Align(
        alignment: Alignment.center,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _CarouselArrowButton(
                    icon: Icons.chevron_left,
                    theme: theme,
                    onPressed: () => _changeSlide(-1, resetTimer: true),
                  ),
                  _CarouselArrowButton(
                    icon: Icons.chevron_right,
                    theme: theme,
                    onPressed: () => _changeSlide(1, resetTimer: true),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CarouselSlide extends StatelessWidget {
  const _CarouselSlide({
    super.key,
    required this.image,
    required this.semanticsLabel,
  });

  final AssetImage image;
  final String semanticsLabel;

  @override
  Widget build(BuildContext context) {
    return RepaintBoundary(
      child: Semantics(
        label: semanticsLabel,
        child: LayoutBuilder(
          builder: (context, constraints) {
            final width = constraints.maxWidth.isFinite
                ? constraints.maxWidth
                : null;
            final height = constraints.maxHeight.isFinite
                ? constraints.maxHeight
                : null;

            return Image(
              image: image,
              fit: BoxFit.cover,
              filterQuality: FilterQuality.low,
              gaplessPlayback: true,
              width: width,
              height: height,
              frameBuilder: (context, child, frame, wasSyncLoaded) {
                if (wasSyncLoaded || frame != null) {
                  return child;
                }
                return const Center(
                  child: SizedBox(
                    width: 48,
                    height: 48,
                    child: CircularProgressIndicator(),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}

class _CarouselIndicators extends StatelessWidget {
  const _CarouselIndicators({
    required this.itemCount,
    required this.currentIndex,
    required this.theme,
  });

  final int itemCount;
  final int currentIndex;
  final LandingCarouselTheme theme;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(itemCount, (index) {
        final isActive = index == currentIndex;
        return AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          width: theme.indicatorSize,
          height: theme.indicatorSize,
          margin: EdgeInsets.only(
            right: index == itemCount - 1 ? 0 : theme.indicatorSpacing,
          ),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: isActive ? theme.indicatorActiveColor : Colors.transparent,
            border: Border.all(
              color: isActive
                  ? theme.indicatorActiveColor
                  : theme.indicatorInactiveColor,
              width: 2,
            ),
          ),
        );
      }),
    );
  }
}

class _CarouselArrowButton extends StatelessWidget {
  const _CarouselArrowButton({
    required this.icon,
    required this.theme,
    required this.onPressed,
  });

  final IconData icon;
  final LandingCarouselTheme theme;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: Material(
        color: theme.arrowBackgroundColor,
        shape: const CircleBorder(),
        child: InkWell(
          onTap: onPressed,
          customBorder: const CircleBorder(),
          child: SizedBox(
            width: theme.arrowButtonSize,
            height: theme.arrowButtonSize,
            child: Icon(icon, color: theme.arrowIconColor),
          ),
        ),
      ),
    );
  }
}

class _LandingCarouselSlide {
  const _LandingCarouselSlide({
    required this.assetPath,
    required this.title,
    required this.subtitle,
  });

  final String assetPath;
  final String title;
  final String subtitle;
}
