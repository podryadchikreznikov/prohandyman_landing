import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';
import 'package:prohandyman_landing/core/theme/extensions/landing_benefits_theme.dart';

/// Section explaining why it is beneficial to contact us.
class LandingWhyUsBenefitsSection extends StatefulWidget {
  const LandingWhyUsBenefitsSection({super.key});

  static const _items = [
    _BenefitItemData(
      icon: Icons.access_time,
      title: 'Работаем 24/7',
      compactTitle: 'Работаем\n24/7',
      description:
          'Ремонтируем бытовую технику каждый день без перерывов, выходных и праздников',
    ),
    _BenefitItemData(
      icon: Icons.local_shipping_outlined,
      title: 'Бесплатный выезд',
      compactTitle: 'Бесплатный\nвыезд',
      description:
          'Мастер бесплатно приезжает на дом к клиенту для проведения диагностики и ремонта',
    ),
    _BenefitItemData(
      icon: Icons.schedule_send_outlined,
      title: 'Быстрое реагирование',
      compactTitle: 'Быстрое\nреагирование',
      description:
          'Будем на месте в течение часа после оставления заявки на сайте или звонка в сервис',
    ),
    _BenefitItemData(
      icon: Icons.local_offer_outlined,
      title: 'Скидка 10%',
      compactTitle: 'Скидка\n10%',
      description:
          'Действует система дополнительных бонусов при оформлении заявки с нашего сайта',
    ),
    _BenefitItemData(
      icon: Icons.verified_outlined,
      title: 'Гарантия 12 месяцев',
      compactTitle: 'Гарантия\n12 месяцев',
      description:
          'После завершения ремонта предоставляется гарантийный талон сроком до года',
    ),
    _BenefitItemData(
      icon: Icons.attach_money_outlined,
      title: 'Демократия цен',
      compactTitle: 'Демократия\nцен',
      description:
          'Наши тарифы прозрачны и доступны всем, являясь одними из самых низких в городе',
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

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Icon(
          data.icon,
          size: theme.iconSize,
          color: theme.iconColor,
        ),
        SizedBox(height: theme.itemInnerSpacing),
        Text(
          data.title,
          textAlign: TextAlign.center,
          style: titleStyle,
        ),
        SizedBox(height: theme.itemInnerSpacing),
        Text(
          data.description,
          textAlign: TextAlign.center,
          style: descriptionStyle,
        ),
      ],
    );
  }
}

class _WideBenefitsGrid extends StatelessWidget {
  const _WideBenefitsGrid({required this.items, required this.theme});

  final List<_BenefitItemData> items;
  final LandingBenefitsTheme theme;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final maxWidth = constraints.maxWidth;
        final columns = _calculateColumns(maxWidth);
        final spacing = theme.itemsHorizontalGap;
        final itemWidth = (maxWidth - spacing * (columns - 1)) / columns;

        return Wrap(
          alignment: WrapAlignment.center,
          spacing: spacing,
          runSpacing: theme.itemsVerticalGap,
          children: items
              .map(
                (item) => SizedBox(
                  width: itemWidth,
                  child: _BenefitItem(data: item, theme: theme),
                ),
              )
              .toList(),
        );
      },
    );
  }
}

class _CompactBenefitsGrid extends StatelessWidget {
  const _CompactBenefitsGrid({required this.items, required this.theme});

  final List<_BenefitItemData> items;
  final LandingBenefitsTheme theme;

  @override
  Widget build(BuildContext context) {
    final titleStyle = theme.compactTitleTextStyle;

    return LayoutBuilder(
      builder: (context, constraints) {
        const columns = 3;
        final spacing = theme.compactItemsHorizontalGap;
        final runSpacing = theme.compactItemsVerticalGap;
        final maxWidth = constraints.maxWidth;
        final computedWidth =
            (maxWidth - spacing * (columns - 1)) / columns;
        final tileWidth = math.max(theme.compactMinTileWidth, computedWidth);
        final totalWidth = columns * tileWidth + spacing * (columns - 1);
        final needsScroll = totalWidth > maxWidth;

        final grid = SizedBox(
          width: totalWidth,
          child: Wrap(
            spacing: spacing,
            runSpacing: runSpacing,
            children: [
              for (final item in items)
                SizedBox(
                  width: tileWidth,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        item.icon,
                        size: theme.iconSize,
                        color: theme.iconColor,
                      ),
                      SizedBox(height: theme.itemInnerSpacing),
                      Text(
                        item.compactTitle ?? item.title,
                        textAlign: TextAlign.center,
                        style: titleStyle,
                      ),
                    ],
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
