import 'dart:async';

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

import 'repair_category_models.dart';
import 'repair_category_shared.dart';

class RepairCategoryMobileSlide extends StatefulWidget {
  const RepairCategoryMobileSlide({
    super.key,
    required this.category,
    this.onScrollLockChanged,
  });

  final RepairCategory category;
  final ValueChanged<bool>? onScrollLockChanged;

  @override
  State<RepairCategoryMobileSlide> createState() => _RepairCategoryMobileSlideState();
}

class _RepairCategoryMobileSlideState extends State<RepairCategoryMobileSlide>
    with SingleTickerProviderStateMixin {
  bool _showDetails = false;
  bool _hoverOverride = false;
  bool _isScrollable = false;
  Timer? _cycleTimer;
  Timer? _scrollStartTimer;
  late final AnimationController _fadeController;
  late final Animation<double> _fadeAnimation;
  final ScrollController _scrollController = ScrollController();

  @override
  void initState() {
    super.initState();
    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    );
    _fadeAnimation = CurvedAnimation(
      parent: _fadeController,
      curve: Curves.easeInOut,
    );
    _startCycle();
  }

  @override
  void dispose() {
    _cycleTimer?.cancel();
    _scrollStartTimer?.cancel();
    _fadeController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _startCycle() {
    if (_hoverOverride) return;

    _cycleTimer?.cancel();
    _scrollStartTimer?.cancel();
    _resetScroll();

    setState(() => _showDetails = true);
    _fadeController.forward(from: 0);

    _scrollStartTimer = Timer(const Duration(seconds: 3), _startScrollIfNeeded);

    _cycleTimer = Timer(const Duration(seconds: 30), () {
      if (!mounted || _hoverOverride) return;
      setState(() => _showDetails = false);
      _fadeController.reverse();
      _resetScroll();
      _cycleTimer = Timer(const Duration(seconds: 30), () {
        if (!mounted || _hoverOverride) return;
        _startCycle();
      });
    });
  }

  void _resetScroll() {
    if (_scrollController.hasClients) {
      _scrollController.jumpTo(0);
    }
    if (_isScrollable) {
      _isScrollable = false;
    }
  }

  void _startScrollIfNeeded() {
    if (!_showDetails || !_scrollController.hasClients) return;
    final position = _scrollController.position;
    final canScroll = position.maxScrollExtent > 0;
    if (canScroll != _isScrollable) {
      setState(() => _isScrollable = canScroll);
    }
    if (!canScroll) return;

    _scrollController.animateTo(
      position.maxScrollExtent,
      duration: const Duration(seconds: 7),
      curve: Curves.linear,
    );
  }

  void _handleHoverEnter(PointerEnterEvent event) {
    _hoverOverride = true;
    _cycleTimer?.cancel();
    _scrollStartTimer?.cancel();
    _resetScroll();

    widget.onScrollLockChanged?.call(true);
    setState(() => _showDetails = true);
    _fadeController.forward(from: 0);
    _scrollStartTimer =
        Timer(const Duration(seconds: 3), _startScrollIfNeeded);
  }

  void _handleHoverExit(PointerExitEvent event) {
    _hoverOverride = false;
    _scrollStartTimer?.cancel();

    widget.onScrollLockChanged?.call(false);
    setState(() => _showDetails = false);
    _fadeController.reverse();
    _resetScroll();

    _cycleTimer?.cancel();
    _cycleTimer = Timer(const Duration(seconds: 30), () {
      if (!mounted || _hoverOverride) return;
      _startCycle();
    });
  }

  @override
  Widget build(BuildContext context) {
    final category = widget.category;
    final textTheme = Theme.of(context).textTheme;
    final bodyStyle =
        textTheme.bodySmall?.copyWith(color: Colors.white) ??
        const TextStyle(color: Colors.white, fontSize: 12);
    final titleStyle =
        textTheme.bodyMedium?.copyWith(color: Colors.white) ??
        const TextStyle(color: Colors.white, fontSize: 16);

    final scale = _hoverOverride ? 1.05 : 1.0;

    return MouseRegion(
      onEnter: _handleHoverEnter,
      onExit: _handleHoverExit,
      child: AnimatedScale(
        scale: scale,
        duration: const Duration(milliseconds: 150),
        curve: Curves.easeOut,
        child: Stack(
          fit: StackFit.expand,
          children: [
            RepairCategoryImage(assetPath: category.assetPath),
            Positioned.fill(
              child: FadeTransition(
                opacity: _fadeAnimation,
                child: Container(
                  margin: const EdgeInsets.only(bottom: 52),
                  padding: const EdgeInsets.all(16),
                  alignment:
                      _isScrollable ? Alignment.topLeft : Alignment.center,
                  color: const Color(0xAA000000),
                  child: ScrollConfiguration(
                    behavior: const NoGlowScrollBehavior(),
                    child: SingleChildScrollView(
                      controller: _scrollController,
                      primary: false,
                      physics: const ClampingScrollPhysics(),
                      child: Align(
                        alignment: _isScrollable
                            ? Alignment.topLeft
                            : Alignment.center,
                        child: Text(
                          category.details,
                          style: bodyStyle,
                          textAlign:
                              _isScrollable ? TextAlign.left : TextAlign.center,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
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
                  style: titleStyle,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
