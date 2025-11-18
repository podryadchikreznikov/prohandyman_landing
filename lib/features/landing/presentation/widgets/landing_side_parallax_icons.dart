import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';
import 'package:prohandyman_landing/presentation/widgets/tilt_wrapper.dart';

/// Фоновый слой с "висящими" иконками строительства по бокам сайта.
/// Работает только когда ширина экрана больше контентной (1200px),
/// иконки живут в полях слева/справа и реагируют на скролл и глобальный курсор.
class LandingSideParallaxIcons extends StatefulWidget {
  const LandingSideParallaxIcons({
    super.key,
    required this.scrollController,
    required this.pointerController,
  });

  final ScrollController scrollController;
  final TiltGlobalPointerController pointerController;

  @override
  State<LandingSideParallaxIcons> createState() => _LandingSideParallaxIconsState();
}

class _LandingSideParallaxIconsState extends State<LandingSideParallaxIcons> {
  double _scrollOffset = 0;
  Offset? _pointer;

  static const _maxContentWidth = AppThemeTokens.contentMaxWidth;

  late final List<_ParallaxIcon> _leftIcons;
  late final List<_ParallaxIcon> _rightIcons;

  @override
  void initState() {
    super.initState();
    _scrollOffset = widget.scrollController.hasClients
        ? widget.scrollController.offset
        : 0;
    widget.scrollController.addListener(_handleScroll);
    widget.pointerController.addListener(_handlePointer);
    _leftIcons = _generateIcons(isLeft: true);
    _rightIcons = _generateIcons(isLeft: false);
  }

  @override
  void dispose() {
    widget.scrollController.removeListener(_handleScroll);
    widget.pointerController.removeListener(_handlePointer);
    super.dispose();
  }

  void _handleScroll() {
    if (!mounted) return;
    setState(() {
      _scrollOffset = widget.scrollController.offset;
    });
  }

  void _handlePointer() {
    if (!mounted) return;
    setState(() {
      _pointer = widget.pointerController.position;
    });
  }

  List<_ParallaxIcon> _generateIcons({required bool isLeft}) {
    final iconsPool = isLeft
        ? const <IconData>[
            Icons.construction,
            Icons.home_work_outlined,
            Icons.handyman_outlined,
            Icons.build_outlined,
          ]
        : const <IconData>[
            Icons.apartment_outlined,
            Icons.factory_outlined,
            Icons.precision_manufacturing_outlined,
            Icons.account_tree_outlined,
          ];

    final result = <_ParallaxIcon>[];

    // Генерируем несколько "слоёв" по высоте, чтобы при скролле
    // всегда что‑то было в кадре.
    const count = 14;
    for (var i = 0; i < count; i++) {
      final depth = 0.12 + (i % 5) * 0.04; // 0.12..0.28 (0.12 — дальше, 0.28 — ближе)
      final baseY = -0.3 + (i / (count - 1)) * 1.6; // -0.3..1.3
      final baseX = isLeft
          ? 0.25 + (i % 3) * 0.18 // 3 столбца слева
          : 0.35 + (i % 3) * 0.18; // 3 столбца справа
      // Нормализованный "близости" коэффициент: 0 — далеко, 1 — близко.
      const minDepth = 0.12;
      const maxDepth = 0.28;
      final closeness = ((depth - minDepth) / (maxDepth - minDepth))
          .clamp(0.0, 1.0); // 0..1

      // Ближние иконки крупнее, дальние — меньше.
      final size = 44 + closeness * 36; // ~44..80

      // Дальние иконки более плотные (больше alpha), ближние — крупнее, но прозрачнее.
      final alphaFar = 0.32;
      final alphaNear = 0.14;
      final alpha = (alphaFar - (alphaFar - alphaNear) * closeness)
          .clamp(0.12, 0.3);
      final iconData = iconsPool[i % iconsPool.length];

      result.add(
        _ParallaxIcon(
          icon: iconData,
          basePosition: Offset(baseX.clamp(0.0, 1.0), baseY),
          depth: depth,
          size: size,
          alpha: alpha.clamp(0.1, 0.25),
        ),
      );
    }

    return result;
  }

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: IgnorePointer(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final totalWidth = constraints.maxWidth;
            final sideWidth =
                (totalWidth - _maxContentWidth).clamp(0.0, totalWidth) / 2;
            if (sideWidth <= 40) {
              // Практически нет полей – ничего не рисуем.
              return const SizedBox.shrink();
            }
            return Row(
              children: [
                SizedBox(
                  width: sideWidth,
                  child: _buildSide(isLeft: true, width: sideWidth),
                ),
                const Expanded(child: SizedBox()),
                SizedBox(
                  width: sideWidth,
                  child: _buildSide(isLeft: false, width: sideWidth),
                ),
              ],
            );
          },
        ),
      ),
    );
  }

  Widget _buildSide({required bool isLeft, required double width}) {
    final icons = isLeft ? _leftIcons : _rightIcons;
    return Container(
      child: Stack(
        children: [
          for (final icon in icons)
            _buildIcon(icon: icon, width: width, isLeft: isLeft),
        ],
      ),
    );
  }

  Widget _buildIcon({
    required _ParallaxIcon icon,
    required double width,
    required bool isLeft,
  }) {
    // Специально НЕ реагируем на курсор для боковин — только скролл.
    final pointer = _pointer;
    double pointerShiftX = 0;
    const double pointerShiftY = 0;
    if (pointer != null) {
      // Делаем no-op обращение, чтобы использовать поле и не получать lint.
      // Сам сдвиг по X оставляем равным нулю.
      // ignore: unused_local_variable
      final _ = pointer.dx;
    }

    final viewportHeight = MediaQuery.of(context).size.height;
    // При скролле вниз контент и иконки двигаются вверх; мы сдвигаем иконки
    // в ту же сторону, но с меньшей скоростью (эффект заднего плана).
    final parallaxFactor = 0.15 + icon.depth * 0.25; // ближе — немного быстрее
    final top = icon.basePosition.dy * viewportHeight -
        _scrollOffset * parallaxFactor;

    final left = icon.basePosition.dx * width;

    // Базовая непрозрачность по глубине.
    final baseOpacity = (icon.alpha * 2).clamp(0.25, 0.7);

    // Градиент альфа от контентной области к краю поля (96px).
    const fadeWidth = 0.0;
    // ВАЖНО: завязан только на геометрию (left), не на позицию курсора.
    final localX = left.clamp(0.0, width);
    final edgeDistance = isLeft
        ? width - localX // расстояние от внутреннего края слева (границы 1200px)
        : localX; // расстояние от внутреннего края справа
    final edgeFactor = (edgeDistance / fadeWidth).clamp(0.0, 1.0);
    final effectiveOpacity = (baseOpacity * edgeFactor).clamp(0.0, 1.0);

    final baseColor = AppThemeTokens.brandPrimaryDark.withOpacity(
      effectiveOpacity,
    );
    // Эффект распада применяем к крупным и средним иконкам (ближний план),
    // маленькие остаются цельными.
    final isBig = icon.size >= 56;

    return Positioned(
      top: top + pointerShiftY,
      left: isLeft ? left + pointerShiftX : null,
      right: isLeft ? null : left - pointerShiftX,
      child: AnimatedOpacity(
        duration: const Duration(milliseconds: 400),
        opacity: effectiveOpacity,
        child: isBig
            ? _PixelatedIcon(
                icon: icon.icon,
                size: icon.size,
                color: baseColor,
              )
            : Icon(
                icon.icon,
                size: icon.size,
                color: baseColor,
              ),
      ),
    );
  }
}

class _ParallaxIcon {
  const _ParallaxIcon({
    required this.icon,
    required this.basePosition,
    required this.depth,
    required this.size,
    required this.alpha,
  });

  final IconData icon;
  final Offset basePosition;
  final double depth;
  final double size;
  final double alpha;
}

/// Иконка с эффектом «распада на пиксели» (как будто решето).
class _PixelatedIcon extends StatelessWidget {
  const _PixelatedIcon({
    required this.icon,
    required this.size,
    required this.color,
  });

  final IconData icon;
  final double size;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: Size.square(size),
      painter: _PixelatedIconPainter(
        icon: icon,
        color: color,
      ),
    );
  }
}

class _PixelatedIconPainter extends CustomPainter {
  _PixelatedIconPainter({
    required this.icon,
    required this.color,
  });

  final IconData icon;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final textPainter = TextPainter(
      text: TextSpan(
        text: String.fromCharCode(icon.codePoint),
        style: TextStyle(
          fontFamily: icon.fontFamily,
          package: icon.fontPackage,
          fontSize: size.width,
          color: color,
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();

    final iconOffset = Offset(
      (size.width - textPainter.width) / 2,
      (size.height - textPainter.height) / 2,
    );

    // Рисуем иконку на отдельном слое, чтобы затем "выкусить" из неё дырки
    // с помощью BlendMode.clear.
    final layerBounds = Offset.zero & size;
    canvas.saveLayer(layerBounds, Paint());

    // Базовая иконка
    textPainter.paint(canvas, iconOffset);

    // «Решето»: рисуем сетку квадратных "пикселей", часть которых
    // пробиваем BlendMode.clear, создавая эффект распада.
    // Делаем сетку достаточно мелкой.
    const int steps = 54;
    final rand = math.Random(icon.codePoint);
    final cellSize = size.width / steps; // width == height, сетка строго квадратная
    final holePaint = Paint()..blendMode = BlendMode.clear;

    // Нормализуем прозрачность: чем меньше opacity, тем больше дырок.
    final opacity = color.opacity.clamp(0.0, 1.0);
    const minO = 0.25;
    const maxO = 0.7;
    final t = ((opacity - minO) / (maxO - minO)).clamp(0.0, 1.0); // 0..1
    final invOpacity = 1.0 - t; // 0 — максимально плотная, 1 — очень прозрачная

    for (var i = 0; i < steps; i++) {
      for (var j = 0; j < steps; j++) {
        // Привязываем клетки к целочисленной сетке, чтобы форма была
        // максимально квадратной, без смещения по субпикселям.
        final double x = (i * cellSize).floorToDouble();
        final double y = (j * cellSize).floorToDouble();
        final double w = cellSize.ceilToDouble();
        final double h = cellSize.ceilToDouble();
        final cellRect = Rect.fromLTWH(x, y, w, h);

        // Чем ближе к правому краю и нижней части — тем больше вероятность дырки.
        final dxFactor = i / (steps - 1);
        final dyFactor = j / (steps - 1);
        final spatialFactor = (dxFactor + dyFactor) / 2;

        // Базовая вероятность "дырок" растёт, когда иконка более прозрачная.
        final baseHole = 0.15 + 0.55 * invOpacity; // 0.15..0.7
        final holeProbability =
            (baseHole * (0.4 + 0.6 * spatialFactor)).clamp(0.0, 0.95);

        if (rand.nextDouble() < holeProbability) {
          // Отключаем сглаживание, чтобы углы выглядели максимально
          // "пиксельно".
          holePaint.isAntiAlias = false;
          canvas.drawRect(cellRect, holePaint);
        }
      }
    }

    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _PixelatedIconPainter oldDelegate) {
    return oldDelegate.icon != icon || oldDelegate.color != color;
  }
}
