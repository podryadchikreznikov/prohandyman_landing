import 'package:flutter/material.dart';
import 'package:flutter_tilt/flutter_tilt.dart';

/// Универсальная обёртка для добавления лёгкого параллакса и подсветки
/// вокруг любого дочернего виджета.
///
/// Использование:
/// TiltWrapper(
///   child: YourWidget(),
/// )
class TiltWrapper extends StatelessWidget {
  const TiltWrapper({
    super.key,
    required this.child,
    this.borderRadius,
    this.enableGestureSensors = false,
    this.angle,
    this.lightColor,
    this.enableLight = false,
  });

  final Widget child;

  /// Радиус скругления для рамки/света.
  final BorderRadius? borderRadius;

  /// Включать ли датчики устройства (гироскоп и т.п.). По умолчанию выкл,
  /// чтобы не мешать вебу/десктопу.
  final bool enableGestureSensors;

  /// Максимальный угол наклона. Если null - используется мягкое значение 3.
  final double? angle;

  /// Цвет "подсветки". По умолчанию мягкий белый.
  final Color? lightColor;

  /// Управляет подсветкой. По умолчанию выключено, оставляя только параллакс.
  final bool enableLight;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final radius = borderRadius ?? BorderRadius.circular(12);

    return Tilt(
      tiltConfig: TiltConfig(
        angle: angle ?? 3,
        enableGestureSensors: enableGestureSensors,
        filterQuality: FilterQuality.high,
      ),
      lightConfig: enableLight
          ? LightConfig(
              enableReverse: true,
              color: lightColor ?? Colors.white.withOpacity(0.35),
              spreadFactor: 2,
            )
          : const LightConfig(disable: true),
      shadowConfig: const ShadowConfig(disable: true),
      borderRadius: radius,
      border: Border.all(
        color: theme.colorScheme.outline.withOpacity(0.12),
        width: 1.5,
        strokeAlign: BorderSide.strokeAlignOutside,
      ),
      child: ClipRRect(
        borderRadius: radius,
        child: child,
      ),
    );
  }
}
