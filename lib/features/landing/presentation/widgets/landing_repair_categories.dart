import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';
import 'package:prohandyman_landing/presentation/widgets/tilt_wrapper.dart';

import 'landing_repair_categories/repair_category_card.dart';
import 'landing_repair_categories/repair_category_mobile_slide.dart';
import 'landing_repair_categories/repair_category_models.dart';

/// Section that showcases the primary appliance categories we repair.
class LandingRepairCategories extends StatefulWidget {
  const LandingRepairCategories({
    super.key,
    this.onInnerScrollLockChanged,
  });

  final ValueChanged<bool>? onInnerScrollLockChanged;

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
                  'НАШИ УСЛУГИ',
                  textAlign: TextAlign.center,
                  style: headingStyle,
                ),
                const SizedBox(height: sectionSpacing),
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
                      spacing: sectionSpacing,
                      runSpacing: sectionSpacing,
                      alignment: WrapAlignment.start,
                      runAlignment: WrapAlignment.start,
                      crossAxisAlignment: WrapCrossAlignment.start,
                      children: [
                        for (var i = 0; i < repairCategories.length; i++)
                          SizedBox(
                            width: _resolveItemWidthForIndex(
                              availableWidth: availableWidth,
                              columns: columns,
                              index: i,
                              baseItemWidth: baseItemWidth,
                              itemCount: repairCategories.length,
                            ),
                            child: RepairCategoryCard(
                              category: repairCategories[i],
                              onScrollLockChanged:
                                  widget.onInnerScrollLockChanged,
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
          aspectRatio: carouselAspectRatio,
          child: Stack(
            children: [
              PageView.builder(
                controller: _pageController,
                itemCount: repairCategories.length,
                onPageChanged: (index) {
                  if (_currentIndex != index) {
                    setState(() => _currentIndex = index);
                  }
                  _restartAutoPlayTimer();
                },
                itemBuilder: (context, index) => Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 4),
                  child: TiltWrapper(
                    child: RepairCategoryMobileSlide(
                      category: repairCategories[index],
                      onScrollLockChanged: widget.onInnerScrollLockChanged,
                    ),
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
      carouselAutoPlayInterval,
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
    final nextIndex = (_currentIndex + 1) % repairCategories.length;
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
    final length = repairCategories.length;
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

    final totalSpacing = sectionSpacing * (columns - 1);
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
      final totalSpacing = sectionSpacing;
      final width = (availableWidth - totalSpacing) / 2;
      return math.max(0, width);
    }

    return baseItemWidth;
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
