import 'dart:async' as async;

import 'package:flutter/material.dart';
import 'package:flutter_tilt/flutter_tilt.dart';

/// Универсальная обёртка для добавления лёгкого параллакса и подсветки
/// вокруг любого дочернего виджета.
///
/// Использование:
/// TiltWrapper(
///   child: YourWidget(),
/// )
class TiltGlobalPointerController extends ChangeNotifier {
  Offset? _position;

  Offset? get position => _position;

  void updatePosition(Offset? newPosition) {
    if (_position == newPosition) return;
    _position = newPosition;
    notifyListeners();
  }
}

class TiltWrapper extends StatefulWidget {
  const TiltWrapper({
    super.key,
    required this.child,
    this.borderRadius,
    this.enableGestureSensors = false,
    this.angle,
    this.lightColor,
    this.enableLight = false,
    this.globalPointerMode = false,
    this.globalPointerController,
    this.invertGlobalPointer = false,
  });

  final Widget child;
  final BorderRadius? borderRadius;
  final bool enableGestureSensors;
  final double? angle;
  final Color? lightColor;
  final bool enableLight;
  final bool globalPointerMode;
  final TiltGlobalPointerController? globalPointerController;
  final bool invertGlobalPointer;

  @override
  State<TiltWrapper> createState() => _TiltWrapperState();
}

class _TiltWrapperState extends State<TiltWrapper> {
  async.StreamController<TiltStreamModel>? _globalStream;
  Offset? _lastGlobalPointer;
  bool _listenerAttached = false;

  bool get _useGlobalPointer =>
      widget.globalPointerMode && widget.globalPointerController != null;

  @override
  void initState() {
    super.initState();
    _attachGlobalListenerIfNeeded();
  }

  @override
  void didUpdateWidget(covariant TiltWrapper oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.globalPointerController != widget.globalPointerController ||
        oldWidget.globalPointerMode != widget.globalPointerMode) {
      _detachGlobalListener(oldWidget);
      _attachGlobalListenerIfNeeded();
    }
  }

  @override
  void dispose() {
    _detachGlobalListener(widget);
    _globalStream?.close();
    super.dispose();
  }

  void _attachGlobalListenerIfNeeded() {
    if (!_useGlobalPointer) return;
    widget.globalPointerController!.addListener(_handleGlobalPointerChange);
    _listenerAttached = true;
    _globalStream ??= async.StreamController<TiltStreamModel>.broadcast();
  }

  void _detachGlobalListener(TiltWrapper? target) {
    final controller = target?.globalPointerController;
    if (_listenerAttached && controller != null) {
      controller.removeListener(_handleGlobalPointerChange);
      _listenerAttached = false;
    }
    if (!_useGlobalPointer) {
      _globalStream?.add(
        const TiltStreamModel(
          position: Offset.zero,
          gesturesType: GesturesType.controller,
          gestureUse: false,
        ),
      );
      _globalStream?.close();
      _globalStream = null;
    }
  }

  void _handleGlobalPointerChange() {
    _lastGlobalPointer = widget.globalPointerController?.position;
    _emitGlobalPointerUpdate();
  }

  void _emitGlobalPointerUpdate() {
    if (!_useGlobalPointer || _globalStream == null || !mounted) {
      return;
    }
    final renderBox = context.findRenderObject() as RenderBox?;
    if (renderBox == null || !renderBox.hasSize) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _emitGlobalPointerUpdate());
      return;
    }
    final pointer = _lastGlobalPointer;
    if (pointer == null) {
      _globalStream!.add(
        const TiltStreamModel(
          position: Offset.zero,
          gesturesType: GesturesType.controller,
          gestureUse: false,
        ),
      );
      return;
    }
    final localPosition = renderBox.globalToLocal(pointer);
    final size = renderBox.size;
    Offset positionForTilt = localPosition;
    if (widget.invertGlobalPointer) {
      positionForTilt = Offset(
        (size.width - localPosition.dx).clamp(0.0, size.width),
        (size.height - localPosition.dy).clamp(0.0, size.height),
      );
    }
    _globalStream!.add(
      TiltStreamModel(
        position: positionForTilt,
        gesturesType: GesturesType.controller,
        gestureUse: true,
      ),
    );
  }

  TiltConfig _buildTiltConfig() {
    return TiltConfig(
      angle: widget.angle ?? 3,
      enableGestureSensors: widget.enableGestureSensors,
      filterQuality: FilterQuality.high,
      enableGestureHover: !_useGlobalPointer,
      enableGestureTouch: !_useGlobalPointer,
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final radius = widget.borderRadius ?? BorderRadius.circular(12);

    return Tilt(
      tiltConfig: _buildTiltConfig(),
      tiltStreamController: _useGlobalPointer ? _globalStream : null,
      lightConfig: widget.enableLight
          ? LightConfig(
              enableReverse: true,
              color: widget.lightColor ?? Colors.white.withOpacity(0.35),
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
        child: widget.child,
      ),
    );
  }
}
