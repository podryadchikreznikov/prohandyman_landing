import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

import 'repair_category_models.dart';
import 'repair_category_shared.dart';

class RepairCategoryCard extends StatefulWidget {
  const RepairCategoryCard({
    super.key,
    required this.category,
    this.onScrollLockChanged,
  });

  final RepairCategory category;
  final ValueChanged<bool>? onScrollLockChanged;

  @override
  State<RepairCategoryCard> createState() => _RepairCategoryCardState();
}

class _RepairCategoryCardState extends State<RepairCategoryCard>
    with SingleTickerProviderStateMixin {
  bool _hoverOverride = false;
  late final AnimationController _fadeController;
  late final Animation<double> _fadeAnimation;

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
  }

  @override
  void dispose() {
    _fadeController.dispose();
    super.dispose();
  }

  void _handleHoverEnter(PointerEnterEvent event) {
    setState(() {
      _hoverOverride = true;
    });

    widget.onScrollLockChanged?.call(true);
    _fadeController.forward(from: 0);
  }

  void _handleHoverExit(PointerExitEvent event) {
    setState(() {
      _hoverOverride = false;
    });

    widget.onScrollLockChanged?.call(false);
    _fadeController.reverse();
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
        child: DecoratedBox(
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
              aspectRatio: 4 / 3,
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
                        alignment: Alignment.center,
                        color: const Color(0xAA000000),
                        child: ScrollConfiguration(
                          behavior: const NoGlowScrollBehavior(),
                          child: SingleChildScrollView(
                            physics: const ClampingScrollPhysics(),
                            child: Align(
                              alignment: Alignment.center,
                              child: Text(
                                category.details,
                                style: bodyStyle,
                                textAlign: TextAlign.center,
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
                      alignment: Alignment.center,
                      color: const Color(0x99000000),
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
          ),
        ),
      ),
    );
  }
}
