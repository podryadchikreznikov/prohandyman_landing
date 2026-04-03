import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';

class LandingPartnersSection extends StatelessWidget {
  const LandingPartnersSection({super.key});

  static const _partners = [
    _PartnerData(
      logoPath: 'assets/handyman_images/logo_partner_01.png',
      logoAspectRatio: 698 / 717,
      title: 'Koster',
      description:
          'Сильный ритейл-партнёр с высокой планкой по качеству сервиса. В таких проектах особенно важны скорость, аккуратность и предсказуемый результат.',
    ),
    _PartnerData(
      logoPath: 'assets/handyman_images/logo_partner_02.png',
      logoAspectRatio: 520 / 351,
      title: 'Петрович',
      description:
          'Крупный игрок рынка стройматериалов, где ценятся сроки и дисциплина. Работа с такими объектами показывает наш опыт на больших площадках.',
    ),
    _PartnerData(
      logoPath: 'assets/handyman_images/logo_partner_04.png',
      logoAspectRatio: 480 / 151,
      title: 'Ярче!',
      description:
          'Региональная сеть, где важны быстрый монтаж и аккуратная сдача объекта. Мы умеем работать в плотном графике без лишнего шума для клиента.',
    ),
    _PartnerData(
      logoPath: 'assets/handyman_images/logo_partner_05.png',
      logoAspectRatio: 500 / 218,
      title: 'VB Engineering',
      description:
          'Инженерный и производственный контур требует точности и документации. Для таких заказов мы держим высокий уровень организации и контроля.',
    ),
    _PartnerData(
      logoPath: 'assets/handyman_images/logo_partner_06.png',
      logoAspectRatio: 211 / 201,
      title: 'ПСБ',
      description:
          'Финансовый сектор любит прозрачность и дисциплину в каждом этапе. С такими клиентами особенно важны порядок в документах и соблюдение сроков.',
    ),
    _PartnerData(
      logoPath: 'assets/handyman_images/logo_partner_07.png',
      logoAspectRatio: 480 / 156,
      title: 'Детский мир',
      description:
          'Федеральный ритейл с высокими требованиями к качеству и безопасности. Это формат, где аккуратность и повторяемость результата решают всё.',
    ),
    _PartnerData(
      logoPath: 'assets/handyman_images/logo_partner_08.png',
      logoAspectRatio: 480 / 206,
      title: 'New Yorker',
      description:
          'Международный fashion-ритейл требует эстетики и быстрого запуска. Мы умеем держать стандарт на объектах с плотным сроком открытия.',
    ),
    _PartnerData(
      logoPath: 'assets/handyman_images/logo_partner_09.png',
      logoAspectRatio: 311 / 162,
      title: 'МКБ',
      description:
          'Банк доверяет только тем, кто работает максимально аккуратно и прозрачно. Такой партнёр подтверждает наш уровень надёжности и контроля.',
    ),
    _PartnerData(
      logoPath: 'assets/handyman_images/logo_partner_10.png',
      logoAspectRatio: 303 / 93,
      title: 'Эпика',
      description:
          'Производственный партнёр, которому важны стабильность и повторяемый результат. Для этого у нас выстроены процессы и ответственная команда на объекте.',
    ),
    _PartnerData(
      logoPath: 'assets/handyman_images/logo_partner_11.png',
      logoAspectRatio: 480 / 139,
      title: 'Персона Грата',
      description:
          'Офисные решения и мебель под задачи корпоративных клиентов. В таком формате особенно ценится гибкость и точное соблюдение ТЗ.',
    ),
    _PartnerData(
      logoPath: 'assets/handyman_images/logo_partner_12.png',
      logoAspectRatio: 453 / 320,
      title: 'Верстакофф',
      description:
          'Профильный бренд для рабочих пространств и производственных задач. Сотрудничество с ним подтверждает наш опыт в сложных монтажах и больших объёмах.',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(
            maxWidth: AppThemeTokens.contentMaxWidth,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'НАШИ ПАРТНЕРЫ',
                textAlign: TextAlign.center,
                style: theme.textTheme.displaySmall,
              ),
              const SizedBox(height: 12),
              Text(
                'Крупные бренды выбирают нас за точность, дисциплину и стабильное качество на больших объектах.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium,
              ),
              const SizedBox(height: 24),
              Column(
                children: [
                  for (var index = 0; index < _partners.length; index++) ...[
                    _PartnerRow(
                      partner: _partners[index],
                      imageOnLeft: index.isEven,
                    ),
                    if (index != _partners.length - 1)
                      const SizedBox(height: 28),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PartnerRow extends StatelessWidget {
  const _PartnerRow({
    required this.partner,
    required this.imageOnLeft,
  });

  final _PartnerData partner;
  final bool imageOnLeft;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return LayoutBuilder(
      builder: (context, constraints) {
        final isCompact = constraints.maxWidth < 820;

        if (isCompact) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _PartnerImageBlock(partner: partner),
              const SizedBox(height: 12),
              _PartnerTextBlock(partner: partner, theme: theme),
            ],
          );
        }

        final image = Expanded(
          flex: 1,
          child: _PartnerImageBlock(partner: partner),
        );
        final text = Expanded(
          flex: 1,
          child: _PartnerTextBlock(partner: partner, theme: theme),
        );

        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: imageOnLeft
              ? [image, const SizedBox(width: 24), text]
              : [text, const SizedBox(width: 24), image],
        );
      },
    );
  }
}

class _PartnerImageBlock extends StatelessWidget {
  const _PartnerImageBlock({required this.partner});

  final _PartnerData partner;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppThemeTokens.backgroundSurface,
      ),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: AspectRatio(
          aspectRatio: partner.logoAspectRatio,
          child: Image.asset(
            partner.logoPath,
            fit: BoxFit.contain,
          ),
        ),
      ),
    );
  }
}

class _PartnerTextBlock extends StatelessWidget {
  const _PartnerTextBlock({required this.partner, required this.theme});

  final _PartnerData partner;
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            partner.title,
            textAlign: TextAlign.left,
            style: theme.textTheme.titleMedium?.copyWith(
              color: AppThemeTokens.brandPrimaryDark,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            partner.description,
            textAlign: TextAlign.left,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: AppThemeTokens.textDark,
              height: 1.45,
            ),
          ),
          const SizedBox(height: 14),
          Container(
            width: 120,
            height: 2,
            color: AppThemeTokens.brandPrimary,
          ),
        ],
      ),
    );
  }
}

class _PartnerData {
  const _PartnerData({
    required this.logoPath,
    required this.logoAspectRatio,
    required this.title,
    required this.description,
  });

  final String logoPath;
  final double logoAspectRatio;
  final String title;
  final String description;
}
