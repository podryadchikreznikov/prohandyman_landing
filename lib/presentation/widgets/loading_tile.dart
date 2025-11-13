import 'package:card_loading/card_loading.dart';
import 'package:flutter/material.dart';

class LoadingTile extends StatelessWidget {
  final double? height;
  final double? maxHeight;
  final double? width;
  final double? maxWidth;
  const LoadingTile({
    super.key,
    this.height,
    this.maxHeight,
    this.width,
    this.maxWidth,
  });

  @override
  Widget build(BuildContext context) {
    if (maxWidth != null) {
      return Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Flexible(
            child: ConstrainedBox(
              constraints: BoxConstraints(maxWidth: maxWidth!),
              child: _cardLoading(),
            ),
          ),
        ],
      );
    }
    if (maxHeight != null) {
      return Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Flexible(
            child: ConstrainedBox(
              constraints: BoxConstraints(maxHeight: maxHeight!),
              child: _cardLoading(),
            ),
          ),
        ],
      );
    }
    return _cardLoading();
  }

  Color _overlayColor(Color background, Color overlay, double opacity) {
    final r = (overlay.red * opacity + background.red * (1 - opacity)).round();
    final g =
        (overlay.green * opacity + background.green * (1 - opacity)).round();
    final b =
        (overlay.blue * opacity + background.blue * (1 - opacity)).round();
    return Color.fromRGBO(r, g, b, 1);
  }

  Widget _cardLoading() {
    return LayoutBuilder(
      builder: (context, constraints) {
        // log("🐈🖌️ ${Theme.of(context).colorScheme.surface.hashCode}");
        Color colorOne = _overlayColor(
          Theme.of(context).colorScheme.surface,
          Theme.of(context).colorScheme.secondaryContainer,
          0.2,
        );
        Color colorTwo = _overlayColor(
          Theme.of(context).colorScheme.surface,
          Theme.of(context).colorScheme.secondaryContainer,
          0.4,
        );
        return CardLoading(
          height: height ?? constraints.maxHeight,
          width: width,
          borderRadius: const BorderRadius.all(Radius.circular(32)),
          cardLoadingTheme: CardLoadingTheme(
            colorOne: colorOne,
            colorTwo: colorTwo,
          ),
        );
      },
    );
  }
}
