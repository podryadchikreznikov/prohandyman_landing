import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';

class LandingFooter extends StatelessWidget {
  const LandingFooter({super.key});

  static const _contacts = [
    '+7 (999) 497-85-32',
    '+7 (343) 521-55-09',
    'info@MTL-servis.ru',
    'Пн-Вс: с 08:00 до 20:00',
    '620078, г. Екатеринбург, ул. Данилы Зверева, 31 s',
  ];

  static const _companyInfo = [
    'ИНН 331602832171',
    'ОГРН 3043316117500051',
    'ИП Мартынов Тимур Львович',
  ];

  static const _services = [
    'Ремонт стиральных машин',
    'Ремонт посудомоечных машин',
    'Ремонт варочных панелей и духовых шкафов',
    'Ремонт холодильников',
    'Ремонт водонагревателей',
  ];

  static const _navLinks = [
    'Главная',
    'Цены',
    'Отзывы',
    'О компании',
    'Контакты',
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    final baseTextStyle =
        (textTheme.bodySmall ?? const TextStyle(fontSize: 14)).copyWith(
      color: AppThemeTokens.textLightMuted,
      height: 1.4,
    );
    final linkTextStyle = baseTextStyle.copyWith(
      color: AppThemeTokens.textLight,
    );

    const footerBackground = AppThemeTokens.brandPrimary;
    const footerBottomBackground = AppThemeTokens.brandPrimaryDark;

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: AppThemeTokens.contentMaxWidth,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ColoredBox(
              color: footerBackground,
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24,
                  vertical: 32,
                ),
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    final maxWidth = constraints.maxWidth;
                    final isWide = maxWidth >= 960;
                    final isMedium = !isWide && maxWidth >= 640;

                    final topContent = isWide
                        ? Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(
                                flex: 3,
                                child: _ContactsColumn(
                                  baseTextStyle: baseTextStyle,
                                ),
                              ),
                              const SizedBox(width: 48),
                              Expanded(
                                flex: 2,
                                child: _CompanyInfoColumn(
                                  baseTextStyle: baseTextStyle,
                                ),
                              ),
                              const SizedBox(width: 48),
                              Expanded(
                                flex: 3,
                                child: _ServicesColumn(
                                  linkTextStyle: linkTextStyle,
                                ),
                              ),
                              const SizedBox(width: 48),
                              Expanded(
                                flex: 2,
                                child: _NavColumn(
                                  linkTextStyle: linkTextStyle,
                                ),
                              ),
                            ],
                          )
                        : Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              _ContactsColumn(baseTextStyle: baseTextStyle),
                              const SizedBox(height: 8),
                              _CompanyInfoColumn(baseTextStyle: baseTextStyle),
                              const SizedBox(height: 24),
                              if (isMedium)
                                Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Expanded(
                                      child: _ServicesColumn(
                                        linkTextStyle: linkTextStyle,
                                      ),
                                    ),
                                    const SizedBox(width: 32),
                                    Expanded(
                                      child: _NavColumn(
                                        linkTextStyle: linkTextStyle,
                                      ),
                                    ),
                                  ],
                                )
                              else ...[
                                _ServicesColumn(linkTextStyle: linkTextStyle),
                                const SizedBox(height: 24),
                                _NavColumn(linkTextStyle: linkTextStyle),
                              ],
                            ],
                          );

                    return Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        topContent,
                        const SizedBox(height: 32),
                        Divider(
                          color:
                              AppThemeTokens.textLightMuted.withOpacity(0.6),
                          height: 1,
                        ),
                        const SizedBox(height: 16),
                        _BottomBar(
                          baseTextStyle: baseTextStyle,
                          highlightStyle: baseTextStyle.copyWith(
                            color: AppThemeTokens.textLight,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
            ),
            SizedBox(
              height: 32,
              width: double.infinity,
              child: ColoredBox(color: footerBottomBackground),
            ),
          ],
        ),
      ),
    );
  }
}

class _ContactsColumn extends StatelessWidget {
  const _ContactsColumn({required this.baseTextStyle});

  final TextStyle baseTextStyle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final line in LandingFooter._contacts)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(line, style: baseTextStyle),
          ),
      ],
    );
  }
}

class _CompanyInfoColumn extends StatelessWidget {
  const _CompanyInfoColumn({required this.baseTextStyle});

  final TextStyle baseTextStyle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final line in LandingFooter._companyInfo)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(line, style: baseTextStyle),
          ),
      ],
    );
  }
}

class _ServicesColumn extends StatelessWidget {
  const _ServicesColumn({required this.linkTextStyle});

  final TextStyle linkTextStyle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final service in LandingFooter._services)
          _UnderlinedFooterItem(
            text: service,
            textStyle: linkTextStyle,
          ),
      ],
    );
  }
}

class _NavColumn extends StatelessWidget {
  const _NavColumn({required this.linkTextStyle});

  final TextStyle linkTextStyle;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final link in LandingFooter._navLinks)
          _UnderlinedFooterItem(
            text: link,
            textStyle: linkTextStyle,
          ),
      ],
    );
  }
}

class _UnderlinedFooterItem extends StatelessWidget {
  const _UnderlinedFooterItem({
    required this.text,
    required this.textStyle,
  });

  final String text;
  final TextStyle textStyle;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Text(
        text,
        style: textStyle.copyWith(
          decoration: TextDecoration.underline,
          decorationColor: textStyle.color ?? AppThemeTokens.textLight,
        ),
        overflow: TextOverflow.ellipsis,
        maxLines: 2,
      ),
    );
  }
}

class _BottomBar extends StatelessWidget {
  const _BottomBar({
    required this.baseTextStyle,
    required this.highlightStyle,
  });

  final TextStyle baseTextStyle;
  final TextStyle highlightStyle;

  @override
  Widget build(BuildContext context) {
    const copyrightText =
        '© MTL СЕРВИСНЫЙ ЦЕНТР 2025. Все права защищены.';

    return LayoutBuilder(
      builder: (context, constraints) {
        final maxWidth = constraints.maxWidth;
        final isWide = maxWidth >= 640;

        final left = Text(
          copyrightText,
          style: baseTextStyle,
        );

        final right = RichText(
          text: TextSpan(
            text: 'Сделано командой БАЛАНСОВЕД',
            style: highlightStyle,
          ),
        );

        if (isWide) {
          return Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Flexible(child: left),
              const SizedBox(width: 24),
              right,
            ],
          );
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            left,
            const SizedBox(height: 8),
            right,
          ],
        );
      },
    );
  }
}
