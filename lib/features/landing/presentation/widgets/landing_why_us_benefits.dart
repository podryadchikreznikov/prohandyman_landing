import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';
import 'package:prohandyman_landing/core/theme/extensions/landing_benefits_theme.dart';

/// Section explaining why it is beneficial to contact us.
class LandingWhyUsBenefitsSection extends StatefulWidget {
  const LandingWhyUsBenefitsSection({super.key});

  static const _items = [
    _BenefitItemData(
      icon: Icons.star_outline,
      title: 'Большой опыт работы',
      compactTitle: 'Большой опыт\nработы',
      description:
          'Команда из 20 штатных мастеров работает на крупных объектах и в B2B-сегменте.',
    ),
    _BenefitItemData(
      icon: Icons.security,
      title: 'Полная материальная ответственность',
      compactTitle: 'Материальная\nответственность',
      description:
          'Несём ответственность за выполненные работы и устраняем недочёты за свой счёт.',
    ),
    _BenefitItemData(
      icon: Icons.description_outlined,
      title: 'Полный пакет документов',
      compactTitle: 'Полный пакет\nдокументов',
      description:
          'Работаем по договору, выдаём акты и сохраняем прозрачность для юридических лиц.',
    ),
    _BenefitItemData(
      icon: Icons.attach_money_outlined,
      title: 'Гибкая ценовая политика',
      compactTitle: 'Гибкая\nценовая политика',
      description:
          'Гибкая ценовая политика для каждого заказчика, возможность отсрочки платежа',
    ),
    _BenefitItemData(
      icon: Icons.assignment_turned_in_outlined,
      title: 'Не меняем условий договора',
      compactTitle: 'Не меняем\nусловий договора',
      description:
          'Фиксируем объём и сроки заранее и соблюдаем согласованный план работ.',
    ),
    _BenefitItemData(
      icon: Icons.groups_outlined,
      title: 'Бригадир на весь срок работ',
      compactTitle: 'Бригадир на\nвесь срок работ',
      description:
          'На объекте есть ответственный, который держит связь и контролирует качество.',
    ),
    _BenefitItemData(
      icon: Icons.school_outlined,
      title: 'Профессиональные мастера',
      compactTitle: 'Профессиональные\nмастера',
      description:
          'Все мастера проходят обучение и работают по внутренним стандартам компании.',
    ),
    _BenefitItemData(
      icon: Icons.local_shipping_outlined,
      title: 'Бесплатный выезд и расчёт',
      compactTitle: 'Бесплатный выезд\nи расчёт',
      description:
          'Приезжаем на объект, оцениваем объём работ и даём предварительную смету без обязательств.',
    ),
    _BenefitItemData(
      icon: Icons.verified_outlined,
      title: 'Гарантия на работы',
      compactTitle: 'Гарантия\nна работы',
      description:
          'Даём гарантию на выполненные работы и быстро реагируем на замечания.',
    ),
  ];

  @override
  State<LandingWhyUsBenefitsSection> createState() =>
      _LandingWhyUsBenefitsSectionState();
}

class _LandingWhyUsBenefitsSectionState
    extends State<LandingWhyUsBenefitsSection> {
  bool? _useCompactLayout;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_useCompactLayout == null) {
      final benefitsTheme =
          Theme.of(context).extension<LandingBenefitsTheme>();
      assert(
        benefitsTheme != null,
        'LandingBenefitsTheme must be provided via AppTheme extensions.',
      );
      if (benefitsTheme == null) {
        _useCompactLayout = false;
        return;
      }
      final width = MediaQuery.of(context).size.width;
      _useCompactLayout = width < benefitsTheme.compactBreakpoint;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final benefitsTheme = theme.extension<LandingBenefitsTheme>();
    assert(
      benefitsTheme != null,
      'LandingBenefitsTheme must be provided via AppTheme extensions.',
    );
    if (benefitsTheme == null) {
      return const SizedBox.shrink();
    }

    final useCompact = _useCompactLayout ?? false;

    return Padding(
      padding: benefitsTheme.sectionPadding,
      child: Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: benefitsTheme.maxContentWidth,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'ПОЧЕМУ ВЫГОДНО ОБРАТИТЬСЯ К НАМ',
                textAlign: TextAlign.center,
                style: benefitsTheme.headingTextStyle,
              ),
              SizedBox(height: benefitsTheme.headerBodySpacing),
              if (useCompact)
                _CompactBenefitsGrid(
                  items: LandingWhyUsBenefitsSection._items,
                  theme: benefitsTheme,
                )
              else
                _WideBenefitsGrid(
                  items: LandingWhyUsBenefitsSection._items,
                  theme: benefitsTheme,
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _BenefitTile extends StatelessWidget {
  const _BenefitTile({
    required this.index,
    required this.theme,
    required this.child,
  });

  final int index;
  final LandingBenefitsTheme theme;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final themeData = Theme.of(context);
    // Accent color from global theme tokens (используем для обводки)
    final accent = AppThemeTokens.brandPrimary;
    final isOdd = (index + 1).isOdd; // 1-based odd/even

    // 11% / 22% implemented via opacity on full accent color for border
    final borderColor = isOdd
        ? accent.withOpacity(0.11)
        : accent.withOpacity(0.22);
    final iconColor = themeData.colorScheme.onSurface;

    return Container(
      padding: const EdgeInsets.all(8),
      child: Container(
        decoration: BoxDecoration(
          border: Border.all(color: borderColor, width: 2),
        ),
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 16),
        child: IconTheme(
          data: IconThemeData(
            color: iconColor,
            size: theme.iconSize,
          ),
          child: child,
        ),
      ),
    );
  }
}

class _BenefitItemData {
  const _BenefitItemData({
    required this.icon,
    required this.title,
    required this.description,
    this.compactTitle,
  });

  final IconData icon;
  final String title;
  final String description;
  final String? compactTitle;
}

class _BenefitItem extends StatelessWidget {
  const _BenefitItem({
    required this.data,
    required this.theme,
  });

  final _BenefitItemData data;
  final LandingBenefitsTheme theme;

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final titleStyle = textTheme.titleMedium;
    final descriptionStyle = textTheme.bodySmall;

    final hasDescription = data.description.trim().isNotEmpty;

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Icon(
          data.icon,
        ),
        SizedBox(height: theme.itemInnerSpacing),
        Text(
          data.title,
          textAlign: TextAlign.center,
          style: titleStyle,
        ),
        if (hasDescription) ...[
          SizedBox(height: theme.itemInnerSpacing),
          Text(
            data.description,
            textAlign: TextAlign.center,
            style: descriptionStyle,
          ),
        ],
      ],
    );
  }
}

class _WideBenefitsGrid extends StatefulWidget {
  const _WideBenefitsGrid({required this.items, required this.theme});

  final List<_BenefitItemData> items;
  final LandingBenefitsTheme theme;

  @override
  State<_WideBenefitsGrid> createState() => _WideBenefitsGridState();
}

class _WideBenefitsGridState extends State<_WideBenefitsGrid> {
  double? _maxTileHeight;

  void _reportTileHeight(double height) {
    if (height <= 0) return;
    if (_maxTileHeight == null || height > _maxTileHeight!) {
      setState(() {
        _maxTileHeight = height;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = widget.theme;
    final items = widget.items;

    return LayoutBuilder(
      builder: (context, constraints) {
        final maxWidth = constraints.maxWidth;
        final columns = _calculateColumns(maxWidth);
        const spacing = 0.0;
        final itemWidth = maxWidth / columns;

        return Wrap(
          alignment: WrapAlignment.center,
          spacing: spacing,
          runSpacing: 0,
          children: [
            for (var index = 0; index < items.length; index++)
              SizedBox(
                width: itemWidth,
                child: _BenefitTile(
                  index: index,
                  theme: theme,
                  child: _maxTileHeight == null
                      ? _MeasurableTile(
                          onSize: _reportTileHeight,
                          child: _BenefitItem(
                            data: items[index],
                            theme: theme,
                          ),
                        )
                      : SizedBox(
                          height: _maxTileHeight,
                          child: _BenefitItem(
                            data: items[index],
                            theme: theme,
                          ),
                        ),
                ),
              ),
          ],
        );
      },
    );
  }
}

class _MeasurableTile extends StatefulWidget {
  const _MeasurableTile({
    required this.child,
    required this.onSize,
  });

  final Widget child;
  final ValueChanged<double> onSize;

  @override
  State<_MeasurableTile> createState() => _MeasurableTileState();
}

class _MeasurableTileState extends State<_MeasurableTile> {
  final GlobalKey _key = GlobalKey();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _notifySize());
  }

  @override
  void didUpdateWidget(covariant _MeasurableTile oldWidget) {
    super.didUpdateWidget(oldWidget);
    WidgetsBinding.instance.addPostFrameCallback((_) => _notifySize());
  }

  void _notifySize() {
    final context = _key.currentContext;
    if (context == null) return;
    final size = context.size;
    if (size != null) {
      widget.onSize(size.height);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      key: _key,
      child: widget.child,
    );
  }
}

class _CompactBenefitsGrid extends StatefulWidget {
  const _CompactBenefitsGrid({required this.items, required this.theme});

  final List<_BenefitItemData> items;
  final LandingBenefitsTheme theme;

  @override
  State<_CompactBenefitsGrid> createState() => _CompactBenefitsGridState();
}

class _CompactBenefitsGridState extends State<_CompactBenefitsGrid> {
  double? _maxTileHeight;

  void _reportTileHeight(double height) {
    if (height <= 0) return;
    if (_maxTileHeight == null || height > _maxTileHeight!) {
      setState(() {
        _maxTileHeight = height;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = widget.theme;
    final items = widget.items;
    final titleStyle = theme.compactTitleTextStyle;

    return LayoutBuilder(
      builder: (context, constraints) {
        const columns = 3;
        const spacing = 0.0;
        const runSpacing = 0.0;
        final maxWidth = constraints.maxWidth;
        final computedWidth = maxWidth / columns;
        final tileWidth = math.max(theme.compactMinTileWidth, computedWidth);
        final totalWidth = columns * tileWidth;
        final needsScroll = totalWidth > maxWidth;

        final grid = SizedBox(
          width: totalWidth,
          child: Wrap(
            spacing: spacing,
            runSpacing: runSpacing,
            children: [
              for (var index = 0; index < items.length; index++)
                SizedBox(
                  width: tileWidth,
                  child: _BenefitTile(
                    index: index,
                    theme: theme,
                    child: _maxTileHeight == null
                        ? _MeasurableTile(
                            onSize: _reportTileHeight,
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(items[index].icon),
                                SizedBox(height: theme.itemInnerSpacing),
                                Text(
                                  items[index].compactTitle ??
                                      items[index].title,
                                  textAlign: TextAlign.center,
                                  style: titleStyle,
                                ),
                              ],
                            ),
                          )
                        : SizedBox(
                            height: _maxTileHeight,
                            child: Column(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(items[index].icon),
                                SizedBox(height: theme.itemInnerSpacing),
                                Text(
                                  items[index].compactTitle ??
                                      items[index].title,
                                  textAlign: TextAlign.center,
                                  style: titleStyle,
                                ),
                              ],
                            ),
                          ),
                  ),
                ),
            ],
          ),
        );

        if (needsScroll) {
          return SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: grid,
          );
        }

        return grid;
      },
    );
  }
}

int _calculateColumns(double maxWidth) {
  if (maxWidth >= AppThemeTokens.contentMaxWidth) {
    return 3;
  }
  if (maxWidth >= 900) {
    return 3;
  }
  if (maxWidth >= 600) {
    return 2;
  }
  return 1;
}
