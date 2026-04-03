import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';

const _hexSize = Size(110, 110);
const _hexVerticalPadding = 12.0;
const _horizontalConnectorLength = 42.0;
const _verticalConnectorLength = 32.0;

const _stepCardDescriptionWidth = 200.0;
const _stepCardHorizontalPadding = 8.0;
const _horizontalStepGap = 16.0;

const _compactStepperBreakpoint = 900.0;

/// Section that highlights how the company works.
class LandingHowWeWork extends StatefulWidget {
  const LandingHowWeWork({super.key});

  static const _steps = <_HowWeWorkStep>[
    _HowWeWorkStep(
      icon: Icons.call_outlined,
      title: 'Заявка',
      description: 'Оставляете заявку на сайте, по телефону или в мессенджере',
    ),
    _HowWeWorkStep(
      icon: Icons.calculate_outlined,
      title: 'Расчёт стоимости',
      description:
          'Менеджер уточняет детали и готовит предварительную смету',
    ),
    _HowWeWorkStep(
      icon: Icons.chat_bubble_outline,
      title: 'Согласование',
      description: 'Согласовываем условия, сроки и официальный договор',
    ),
    _HowWeWorkStep(
      icon: Icons.engineering_outlined,
      title: 'Выполнение работ',
      description: 'Мастера выполняют работы по проекту и техническому заданию',
    ),
    _HowWeWorkStep(
      icon: Icons.assignment_turned_in_outlined,
      title: 'Приемка работ',
      description: 'Принимаете результат и подписываете акт выполненных работ',
    ),
    _HowWeWorkStep(
      icon: Icons.payment_outlined,
      title: 'Оплата',
      description: 'Финальная оплата после вашего одобрения результата',
    ),
  ];

  @override
  State<LandingHowWeWork> createState() => _LandingHowWeWorkState();
}

class _LandingHowWeWorkState extends State<LandingHowWeWork> {
  bool? _useCompactLayout;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_useCompactLayout == null) {
      final width = MediaQuery.of(context).size.width;
      _useCompactLayout = width < _compactStepperBreakpoint;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final headingStyle = theme.textTheme.displaySmall;
    final useCompact = _useCompactLayout ?? false;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: AppThemeTokens.contentMaxWidth,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'КАК МЫ РАБОТАЕМ',
                textAlign: TextAlign.center,
                style: headingStyle,
              ),
              const SizedBox(height: 40),
              if (useCompact)
                const _CompactStepperGrid(steps: LandingHowWeWork._steps)
              else
                LayoutBuilder(
                  builder: (context, constraints) {
                    final isHorizontal =
                        constraints.maxWidth >= _compactStepperBreakpoint;
                    final child = isHorizontal
                        ? const _HorizontalStepper(steps: LandingHowWeWork._steps)
                        : const _VerticalStepper(steps: LandingHowWeWork._steps);
                    return Align(alignment: Alignment.center, child: child);
                  },
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CompactStepperGrid extends StatelessWidget {
  const _CompactStepperGrid({required this.steps});

  final List<_HowWeWorkStep> steps;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final textStyle = textTheme.titleMedium;
    final baseLabelStyle = textStyle ?? const TextStyle(
      fontSize: 18,
      fontWeight: FontWeight.w600,
    );
    final labelStyle = baseLabelStyle.copyWith(color: Colors.grey.shade600);

    return LayoutBuilder(
      builder: (context, constraints) {
        final maxWidth = constraints.maxWidth;
        final spacing = 24.0;
        const columns = 2;
        final itemWidth = (maxWidth - spacing * (columns - 1)) / columns;
        final hexLeftInset = (itemWidth - _hexSize.width) / 2;

        return Wrap(
          spacing: spacing,
          runSpacing: spacing,
          alignment: WrapAlignment.center,
          children: [
            for (var index = 0; index < steps.length; index++)
              SizedBox(
                width: itemWidth,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    SizedBox(
                      height: _hexSize.height + 12,
                      child: Stack(
                        clipBehavior: Clip.none,
                        children: [
                          Positioned(
                            left: hexLeftInset + 4,
                            top: 0,
                            child: Text('${index + 1}', style: labelStyle),
                          ),
                          Align(
                            alignment: Alignment.bottomCenter,
                            child: _HexIcon(
                              icon: steps[index].icon,
                              index: index,
                              totalCount: steps.length,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      steps[index].title,
                      textAlign: TextAlign.center,
                      style: textStyle,
                    ),
                  ],
                ),
              ),
          ],
        );
      },
    );
  }
}

class _HorizontalStepper extends StatelessWidget {
  const _HorizontalStepper({required this.steps});

  final List<_HowWeWorkStep> steps;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final children = <Widget>[];

        for (var i = 0; i < steps.length; i++) {
          if (i != 0) {
            children.add(const SizedBox(width: _horizontalStepGap));
          }
          children.add(
            Expanded(
              child: _HowWeWorkStepCard(
                step: steps[i],
                index: i,
                totalCount: steps.length,
              ),
            ),
          );
        }

        return SizedBox(
          width: constraints.maxWidth,
          child: Stack(
            alignment: Alignment.center,
            children: [
              Positioned.fill(
                child: CustomPaint(
                  painter: _BackgroundDashedLinePainter(
                    stepsCount: steps.length,
                    gap: _horizontalStepGap,
                  ),
                ),
              ),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: children,
              ),
            ],
          ),
        );
      },
    );
  }
}

class _VerticalStepper extends StatelessWidget {
  const _VerticalStepper({required this.steps});

  final List<_HowWeWorkStep> steps;

  @override
  Widget build(BuildContext context) {
    final children = <Widget>[];
    for (var i = 0; i < steps.length; i++) {
      children.add(
        _HowWeWorkStepCard(
          step: steps[i],
          index: i,
          totalCount: steps.length,
        ),
      );
      if (i != steps.length - 1) {
        children.add(
          const _StepConnector(
            horizontal: false,
            length: _verticalConnectorLength,
          ),
        );
      }
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: children,
    );
  }
}

class _HowWeWorkStepCard extends StatelessWidget {
  const _HowWeWorkStepCard({
    required this.step,
    required this.index,
    required this.totalCount,
  });

  final _HowWeWorkStep step;
  final int index;
  final int totalCount;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final titleStyle =
        textTheme.titleMedium?.copyWith(
          fontWeight: FontWeight.w600,
          color: Colors.black87,
        ) ??
        const TextStyle(
          fontSize: 18,
          fontWeight: FontWeight.w600,
          color: Colors.black87,
        );
    final descriptionStyle =
        textTheme.bodyMedium?.copyWith(color: Colors.black54) ??
        const TextStyle(color: Colors.black54);

    final content = Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        _HexIcon(icon: step.icon, index: index, totalCount: totalCount),
        const SizedBox(height: 16),
        Text(step.title, style: titleStyle, textAlign: TextAlign.center),
        const SizedBox(height: 8),
        SizedBox(
          width: _stepCardDescriptionWidth,
          child: Text(
            step.description,
            style: descriptionStyle,
            textAlign: TextAlign.center,
          ),
        ),
      ],
    );

    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: _stepCardHorizontalPadding,
        vertical: _hexVerticalPadding,
      ),
      child: content,
    );
  }
}

class _HexIcon extends StatelessWidget {
  const _HexIcon({
    required this.icon,
    required this.index,
    required this.totalCount,
  });

  final IconData icon;
  final int index;
  final int totalCount;

  @override
  Widget build(BuildContext context) {
    final total = totalCount <= 1 ? 1 : totalCount - 1;
    final t = totalCount <= 1 ? 0.0 : index / total;

    const startColor = Color(0xFF8B1A3C); // бордовый
    const endColor = Color(0xFFFFD700); // золотой
    final backgroundColor =
        Color.lerp(startColor, endColor, t) ?? startColor;

    final luminance = backgroundColor.computeLuminance();
    final iconColor = luminance > 0.5 ? Colors.black87 : Colors.white;

    return SizedBox(
      width: _hexSize.width,
      height: _hexSize.height,
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.center,
        children: [
          ClipPath(
            clipper: _HexagonClipper(),
            child: Container(
              decoration: BoxDecoration(color: backgroundColor),
            ),
          ),
          Icon(icon, size: 38, color: iconColor),
        ],
      ),
    );
  }
}

class _StepConnector extends StatelessWidget {
  const _StepConnector({required this.horizontal, this.length});

  final bool horizontal;
  final double? length;

  @override
  Widget build(BuildContext context) {
    const thickness = 2.0;
    final connectorLength =
        length ??
        (horizontal ? _horizontalConnectorLength : _verticalConnectorLength);

    return SizedBox(
      width: horizontal ? connectorLength : thickness,
      height: horizontal ? thickness : connectorLength,
      child: CustomPaint(painter: _DashedLinePainter(horizontal: horizontal)),
    );
  }
}

class _BackgroundDashedLinePainter extends CustomPainter {
  const _BackgroundDashedLinePainter({
    required this.stepsCount,
    required this.gap,
  });

  final int stepsCount;
  final double gap;

  @override
  void paint(Canvas canvas, Size size) {
    if (stepsCount <= 0) return;

    const dashWidth = 5.0;
    const dashGap = 5.0;
    final paint = Paint()
      ..color = Colors.grey.shade400
      ..strokeWidth = 2;

    final totalGapWidth = gap * (stepsCount - 1).clamp(0, stepsCount - 1);
    final cardWidth =
        stepsCount > 0 ? (size.width - totalGapWidth) / stepsCount : size.width;
    final hexHorizontalOffsetInsideCard =
        (cardWidth - _hexSize.width).clamp(0, cardWidth) / 2;

    // Укорачиваем линию, чтобы она оставалась внутри крайних шестигранников
    const safeInsetInsideHex = 8.0;
    final sideInset = hexHorizontalOffsetInsideCard + safeInsetInsideHex;

    var startX = sideInset;
    final maxX = size.width - sideInset;

    final theoreticalCenterY = _hexVerticalPadding + _hexSize.height / 2;
    final centerY = math.min(theoreticalCenterY, size.height - 1);

    while (startX < maxX) {
      final endX = math.min(startX + dashWidth, maxX);
      canvas.drawLine(Offset(startX, centerY), Offset(endX, centerY), paint);
      startX = endX + dashGap;
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _DashedLinePainter extends CustomPainter {
  const _DashedLinePainter({required this.horizontal});

  final bool horizontal;

  @override
  void paint(Canvas canvas, Size size) {
    const dashWidth = 4.0;
    const dashSpace = 4.0;
    final paint = Paint()
      ..color = Colors.grey.shade400
      ..strokeWidth = 1.5;

    double start = 0;
    final max = horizontal ? size.width : size.height;
    while (start < max) {
      final end = math.min(start + dashWidth, max);
      if (horizontal) {
        canvas.drawLine(
          Offset(start, size.height / 2),
          Offset(end, size.height / 2),
          paint,
        );
      } else {
        canvas.drawLine(
          Offset(size.width / 2, start),
          Offset(size.width / 2, end),
          paint,
        );
      }
      start += dashWidth + dashSpace;
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _HexagonClipper extends CustomClipper<Path> {
  @override
  Path getClip(Size size) {
    final path = Path();
    final width = size.width;
    final height = size.height;
    final triangleHeight = height / 2;

    path.moveTo(width / 2, 0);
    path.lineTo(width, triangleHeight / 2);
    path.lineTo(width, triangleHeight * 1.5);
    path.lineTo(width / 2, height);
    path.lineTo(0, triangleHeight * 1.5);
    path.lineTo(0, triangleHeight / 2);
    path.close();
    return path;
  }

  @override
  bool shouldReclip(covariant CustomClipper<Path> oldClipper) => false;
}

class _HowWeWorkStep {
  const _HowWeWorkStep({
    required this.icon,
    required this.title,
    required this.description,
  });

  final IconData icon;
  final String title;
  final String description;
}
