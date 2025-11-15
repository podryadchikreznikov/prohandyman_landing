import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';

const double _sectionSpacing = 24.0;
const double _carouselAspectRatio = 16 / 9;
const Duration _carouselAutoPlayInterval = Duration(seconds: 10);

const _repairCategories = <_RepairCategory>[
  _RepairCategory(
    title: 'Стиральные машины',
    assetPath: 'assets/repair_categories/washing_machine.jpg',
    semanticsLabel: 'Белая стиральная машина в интерьере.',
  ),
  _RepairCategory(
    title: 'Посудомоечные машины',
    assetPath: 'assets/repair_categories/dishwasher.jpg',
    semanticsLabel: 'Современная посудомоечная машина на кухне.',
  ),
  _RepairCategory(
    title: 'Варочные панели и духовые шкафы',
    assetPath: 'assets/repair_categories/oven.jpg',
    semanticsLabel: 'Встроенная духовка и варочная панель на кухне.',
  ),
  _RepairCategory(
    title: 'Холодильники',
    assetPath: 'assets/repair_categories/refrigerator.jpg',
    semanticsLabel: 'Открытый холодильник с продуктами.',
  ),
  _RepairCategory(
    title: 'Водонагреватели',
    assetPath: 'assets/repair_categories/water_heater.jpg',
    semanticsLabel: 'Настенный водонагреватель в ванной комнате.',
  ),
];

/// Section that showcases the primary appliance categories we repair.
class LandingRepairCategories extends StatefulWidget {
  const LandingRepairCategories({super.key});

  @override
  State<LandingRepairCategories> createState() =>
      _LandingRepairCategoriesState();
}

class _LandingRepairCategoriesState extends State<LandingRepairCategories> {
  late final PageController _pageController;
  Timer? _autoPlayTimer;
  bool _carouselActive = false;
  int _currentIndex = 0;

  @override
  void initState() {
    super.initState();
    _pageController = PageController();
  }

  @override
  void dispose() {
    _autoPlayTimer?.cancel();
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final headingStyle = theme.textTheme.displaySmall;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: RepaintBoundary(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: AppThemeTokens.contentMaxWidth,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'МЫ РЕМОНТИРУЕМ',
                  textAlign: TextAlign.center,
                  style: headingStyle,
                ),
                const SizedBox(height: _sectionSpacing),
                LayoutBuilder(
                  builder: (context, constraints) {
                    final availableWidth = constraints.maxWidth.isFinite
                        ? constraints.maxWidth
                        : AppThemeTokens.contentMaxWidth.toDouble();
                    final columns = _resolveColumns(availableWidth);
                    final useCarousel = columns == 1;
                    _updateAutoPlayState(useCarousel);
                    if (useCarousel) {
                      return _buildCarousel(context);
                    }
                    final baseItemWidth = _resolveItemWidth(
                      availableWidth,
                      columns,
                    );

                    return Wrap(
                      spacing: _sectionSpacing,
                      runSpacing: _sectionSpacing,
                      alignment: WrapAlignment.start,
                      runAlignment: WrapAlignment.start,
                      crossAxisAlignment: WrapCrossAlignment.start,
                      children: [
                        for (var i = 0; i < _repairCategories.length; i++)
                          SizedBox(
                            width: _resolveItemWidthForIndex(
                              availableWidth: availableWidth,
                              columns: columns,
                              index: i,
                              baseItemWidth: baseItemWidth,
                              itemCount: _repairCategories.length,
                            ),
                            child: _RepairCategoryCard(
                              category: _repairCategories[i],
                            ),
                          ),
                      ],
                    );
                  },
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildCarousel(BuildContext context) {
    return Column(
      children: [
        AspectRatio(
          aspectRatio: _carouselAspectRatio,
          child: Stack(
            children: [
              PageView.builder(
                controller: _pageController,
                itemCount: _repairCategories.length,
                onPageChanged: (index) {
                  if (_currentIndex != index) {
                    setState(() => _currentIndex = index);
                  }
                  _restartAutoPlayTimer();
                },
                itemBuilder: (context, index) => Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: _MobileCategorySlide(
                    category: _repairCategories[index],
                  ),
                ),
              ),
              Positioned.fill(child: _buildCarouselArrows()),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildCarouselArrows() {
    return Align(
      alignment: Alignment.center,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          _CarouselArrowButton(
            icon: Icons.chevron_left,
            onPressed: () => _handleManualSlide(-1),
          ),
          _CarouselArrowButton(
            icon: Icons.chevron_right,
            onPressed: () => _handleManualSlide(1),
          ),
        ],
      ),
    );
  }

  void _updateAutoPlayState(bool shouldRun) {
    if (shouldRun) {
      if (!_carouselActive || _autoPlayTimer == null) {
        _carouselActive = true;
        _startAutoPlayTimer();
      }
    } else if (_carouselActive) {
      _carouselActive = false;
      _stopAutoPlayTimer();
    }
  }

  void _startAutoPlayTimer() {
    _autoPlayTimer?.cancel();
    _autoPlayTimer = Timer.periodic(
      _carouselAutoPlayInterval,
      (_) => _goToNextSlide(),
    );
  }

  void _restartAutoPlayTimer() {
    if (_carouselActive) {
      _startAutoPlayTimer();
    }
  }

  void _stopAutoPlayTimer() {
    _autoPlayTimer?.cancel();
    _autoPlayTimer = null;
  }

  void _goToNextSlide() {
    if (!_carouselActive || !_pageController.hasClients) {
      return;
    }
    final nextIndex = (_currentIndex + 1) % _repairCategories.length;
    _pageController.animateToPage(
      nextIndex,
      duration: const Duration(milliseconds: 400),
      curve: Curves.easeInOut,
    );
    setState(() => _currentIndex = nextIndex);
  }

  void _handleManualSlide(int delta) {
    if (!_pageController.hasClients) {
      return;
    }
    final length = _repairCategories.length;
    final targetIndex = (_currentIndex + delta + length) % length;
    _pageController.animateToPage(
      targetIndex,
      duration: const Duration(milliseconds: 400),
      curve: Curves.easeInOut,
    );
    setState(() => _currentIndex = targetIndex);
    _restartAutoPlayTimer();
  }

  int _resolveColumns(double width) {
    if (width >= 1100) {
      return 3;
    }
    if (width >= 720) {
      return 2;
    }
    return 1;
  }

  double _resolveItemWidth(double width, int columns) {
    if (columns <= 1) {
      return width;
    }

    final totalSpacing = _sectionSpacing * (columns - 1);
    final computedWidth = (width - totalSpacing) / columns;
    return math.max(0, computedWidth);
  }

  double _resolveItemWidthForIndex({
    required double availableWidth,
    required int columns,
    required int index,
    required double baseItemWidth,
    required int itemCount,
  }) {
    // Для макета из 5 карточек на широких экранах:
    // первая строка — 3 колонки, вторая — 2 растянутые карточки.
    if (columns == 3 && itemCount == 5 && index >= 3) {
      final totalSpacing = _sectionSpacing;
      final width = (availableWidth - totalSpacing) / 2;
      return math.max(0, width);
    }

    return baseItemWidth;
  }
}

class _RepairCategoryCard extends StatelessWidget {
  const _RepairCategoryCard({required this.category});

  final _RepairCategory category;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        boxShadow: [
          BoxShadow(
            color: Color(0x33000000),
            blurRadius: 20,
            offset: Offset(0, 10),
          ),
        ],
      ),
      child: Semantics(
        label: category.semanticsLabel,
        child: AspectRatio(
          aspectRatio: 16 / 9,
          child: Stack(
            fit: StackFit.expand,
            children: [
              _CategoryImage(assetPath: category.assetPath),
              Align(
                alignment: Alignment.bottomCenter,
              child: Container(
                  height: 52,
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  alignment: Alignment.center,
                  color: const Color(0x99000000),
                  child: Text(
                    category.title,
                    textAlign: TextAlign.center,
                    style:
                        Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Colors.white,
                        ) ??
                        const TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                        ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CategoryImage extends StatelessWidget {
  const _CategoryImage({required this.assetPath});

  final String assetPath;

  @override
  Widget build(BuildContext context) {
    return Image.asset(
      assetPath,
      fit: BoxFit.cover,
      filterQuality: FilterQuality.medium,
      errorBuilder: (context, error, stackTrace) {
        return ColoredBox(
          color: Theme.of(context).colorScheme.surfaceContainerHighest,
          child: const Center(
            child: Icon(Icons.broken_image_outlined, size: 48),
          ),
        );
      },
    );
  }
}

class _RepairCategory {
  const _RepairCategory({
    required this.title,
    required this.assetPath,
    required this.semanticsLabel,
  });

  final String title;
  final String assetPath;
  final String semanticsLabel;
}

class _MobileCategorySlide extends StatelessWidget {
  const _MobileCategorySlide({required this.category});

  final _RepairCategory category;

  @override
  Widget build(BuildContext context) {
    return Stack(
      fit: StackFit.expand,
      children: [
        _CategoryImage(assetPath: category.assetPath),
        Align(
          alignment: Alignment.bottomCenter,
          child: Container(
            height: 52,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            color: const Color(0x99000000),
            alignment: Alignment.center,
            child: Text(
              category.title,
              textAlign: TextAlign.center,
              style:
                  Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.white,
                  ) ??
                  const TextStyle(
                    color: Colors.white,
                    fontSize: 16,
                  ),
            ),
          ),
        ),
      ],
    );
  }
}

class _CarouselArrowButton extends StatelessWidget {
  const _CarouselArrowButton({required this.icon, required this.onPressed});

  final IconData icon;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Material(
        color: Colors.black.withOpacity(0.25),
        shape: const CircleBorder(),
        child: InkWell(
          onTap: onPressed,
          customBorder: const CircleBorder(),
          child: SizedBox(
            width: 40,
            height: 40,
            child: Icon(icon, color: Colors.white),
          ),
        ),
      ),
    );
  }
}
