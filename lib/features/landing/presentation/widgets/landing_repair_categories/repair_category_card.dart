import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:prohandyman_landing/presentation/widgets/tilt_wrapper.dart';

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
    setState(() {});
    widget.onScrollLockChanged?.call(true);
    _fadeController.forward(from: 0);
  }

  void _handleHoverExit(PointerExitEvent event) {
    setState(() {});
    widget.onScrollLockChanged?.call(false);
    _fadeController.reverse();
  }

  @override
  Widget build(BuildContext context) {
    final category = widget.category;
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    final bodyStyle =
        textTheme.bodyMedium?.copyWith(color: Colors.white) ??
        const TextStyle(color: Colors.white, fontSize: 14);
    final titleStyle = textTheme.titleMedium?.copyWith(
          fontWeight: FontWeight.w600,
          color: Colors.black87,
        ) ??
        const TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w600,
          color: Colors.black87,
        );

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        MouseRegion(
          onEnter: _handleHoverEnter,
          onExit: _handleHoverExit,
          child: TiltWrapper(
            borderRadius: BorderRadius.zero,
            clipChild: false,
            enableHoverScale: true,
            hoverScale: 1.05,
            enableHoverShadow: false,
            enableBorder: false,
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
                  ],
                ),
              ),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          category.title,
          textAlign: TextAlign.center,
          style: titleStyle,
        ),
      ],
    );
  }
}
