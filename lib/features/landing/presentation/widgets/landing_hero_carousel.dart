// lib/features/landing/presentation/widgets/landing_hero_carousel.dart
import 'dart:async';
import 'dart:math' as math;

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
      title: 'Сборка мебели и оборудования под крупные проекты',
      subtitle: 'Офисы, магазины, гостиницы, рестораны и жилые комплексы',
    ),
    _LandingCarouselSlide(
      assetPath: 'assets/slides/slide2.jpg',
      title: 'Команда из 20 штатных мастеров',
      subtitle: 'Работаем по договору, соблюдаем сроки и держим качество',
    ),
    _LandingCarouselSlide(
      assetPath: 'assets/slides/slide3.jpg',
      title: 'Торговая, металлическая и корпусная мебель',
      subtitle: 'Соблюдаем ГОСТы, проектную документацию и стандарты заказчика',
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
                    isLeft: true,
                    theme: theme,
                    onPressed: () => _changeSlide(-1, resetTimer: true),
                  ),
                  _CarouselArrowButton(
                    isLeft: false,
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

class _TriangleArrowPainter extends CustomPainter {
  _TriangleArrowPainter({
    required this.color,
    required this.isLeft,
  });

  final Color color;
  final bool isLeft;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.fill;

    final width = size.width;
    final height = size.height;
    final minSide = math.min(width, height);
    final centerX = width / 2;
    final centerY = height / 2;

    // Triangle dimensions relative to the smallest side to keep shape consistent.
    final baseHalf = minSide * 0.3; // half of the base width
    final halfHeight = minSide * 0.35;

    final path = Path();
    if (isLeft) {
      // Apex on the left, base on the right.
      path
        ..moveTo(centerX - baseHalf, centerY)
        ..lineTo(centerX + baseHalf, centerY - halfHeight)
        ..lineTo(centerX + baseHalf, centerY + halfHeight)
        ..close();
    } else {
      // Apex on the right, base on the left.
      path
        ..moveTo(centerX + baseHalf, centerY)
        ..lineTo(centerX - baseHalf, centerY - halfHeight)
        ..lineTo(centerX - baseHalf, centerY + halfHeight)
        ..close();
    }

    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _TriangleArrowPainter oldDelegate) {
    return oldDelegate.color != color || oldDelegate.isLeft != isLeft;
  }
}

class _TriangleClipper extends CustomClipper<Path> {
  _TriangleClipper({required this.isLeft});

  final bool isLeft;

  @override
  Path getClip(Size size) {
    final width = size.width;
    final height = size.height;
    final minSide = math.min(width, height);
    final centerX = width / 2;
    final centerY = height / 2;

    final baseHalf = minSide * 0.3;
    final halfHeight = minSide * 0.35;

    final path = Path();
    if (isLeft) {
      path
        ..moveTo(centerX - baseHalf, centerY)
        ..lineTo(centerX + baseHalf, centerY - halfHeight)
        ..lineTo(centerX + baseHalf, centerY + halfHeight)
        ..close();
    } else {
      path
        ..moveTo(centerX + baseHalf, centerY)
        ..lineTo(centerX - baseHalf, centerY - halfHeight)
        ..lineTo(centerX - baseHalf, centerY + halfHeight)
        ..close();
    }

    return path;
  }

  @override
  bool shouldReclip(covariant _TriangleClipper oldClipper) {
    return oldClipper.isLeft != isLeft;
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
class _CarouselArrowButton extends StatelessWidget {
  const _CarouselArrowButton({
    required this.isLeft,
    required this.theme,
    required this.onPressed,
  });

  final bool isLeft;
  final LandingCarouselTheme theme;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12),
      child: GestureDetector(
        behavior: HitTestBehavior.translucent,
        onTap: onPressed,
        child: SizedBox(
          // Enlarged hit area around the visual triangle.
          width: theme.arrowButtonSize * 1.8,
          height: theme.arrowButtonSize * 1.8,
          child: Center(
            child: SizedBox(
              width: theme.arrowButtonSize,
              height: theme.arrowButtonSize,
              child: ClipPath(
                clipper: _TriangleClipper(isLeft: isLeft),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: onPressed,
                    splashColor: theme.arrowBackgroundColor,
                    highlightColor: Colors.transparent,
                    child: CustomPaint(
                      painter: _TriangleArrowPainter(
                        color: theme.arrowBackgroundColor,
                        isLeft: isLeft,
                      ),
                    ),
                  ),
                ),
              ),
            ),
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
