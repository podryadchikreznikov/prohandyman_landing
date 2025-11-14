part of 'landing_home_header.dart';

class _LandingHomeHeaderCompact {
  static Widget buildBody(
    LandingHeaderTheme theme,
    double contentWidth,
  ) {
    final height = headerHeight(contentWidth, theme);
    return SizedBox(
      height: height,
      child: _LandingHeaderBody(theme: theme),
    );
  }

  static double headerHeight(
    double contentWidth,
    LandingHeaderTheme theme,
  ) {
    final estimated = _estimateStackedHeaderHeight(contentWidth, theme);
    return math.max(AppThemeTokens.landingHeaderHeight, estimated);
  }

  static double _estimateStackedHeaderHeight(
    double contentWidth,
    LandingHeaderTheme theme,
  ) {
    const double verticalPadding = 32;
    const double spacingBetweenSections = 16;
    const double compactCompanyHeight = 56;

    final contactsHeight =
        _estimateContactWrapHeight(contentWidth, theme);
    return verticalPadding +
        compactCompanyHeight +
        spacingBetweenSections +
        contactsHeight;
  }

  static double _estimateContactWrapHeight(
    double contentWidth,
    LandingHeaderTheme theme,
  ) {
    if (contentWidth <= 0) {
      return _contactWrapRowHeight(theme) * _headerInfoItems.length;
    }

    final blockWidths = _headerInfoItems
        .map(
          (item) => _estimateInfoBlockWidth(
            text: item.$2,
            theme: theme,
          ),
        )
        .toList();

    double currentRowWidth = 0;
    int rows = 1;

    for (final width in blockWidths) {
      if (currentRowWidth == 0) {
        currentRowWidth = width;
        continue;
      }

      final proposedWidth = currentRowWidth + 16 + width;
      if (proposedWidth <= contentWidth) {
        currentRowWidth = proposedWidth;
      } else {
        rows++;
        currentRowWidth = width;
      }
    }

    final rowHeight = _contactWrapRowHeight(theme);
    const runSpacing = 8;

    return rows * rowHeight + (rows - 1) * runSpacing;
  }

  static double _contactWrapRowHeight(LandingHeaderTheme theme) {
    final padding = theme.infoPadding.resolve(TextDirection.ltr);
    final textStyle = theme.headerInfoTextStyle;
    final textHeight = (textStyle.fontSize ?? 14) *
        (textStyle.height ?? 1.0);
    final contentHeight = textHeight > 20 ? textHeight : 20;
    return padding.vertical + contentHeight;
  }

  static double _estimateInfoBlockWidth({
    required String text,
    required LandingHeaderTheme theme,
  }) {
    final padding = theme.infoPadding.resolve(TextDirection.ltr);
    final textPainter = TextPainter(
      text: TextSpan(text: text, style: theme.headerInfoTextStyle),
      maxLines: 1,
      textDirection: TextDirection.ltr,
    )..layout(maxWidth: double.infinity);

    const iconSize = 20.0;
    const gap = 8.0;

    return padding.horizontal + iconSize + gap + textPainter.width;
  }
}
