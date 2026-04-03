import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';

class LandingPricingSection extends StatelessWidget {
  const LandingPricingSection({super.key});

  static const _offers = [
    _PricingOffer(
      title: 'Сборка мебели по дизайн-проектам',
      price: 'от 3 500 ₽',
      description:
          'Для офисов, гостиниц, ресторанов и объектов под сдачу. Работаем по проекту, с фиксацией сроков и аккуратной сдачей.',
    ),
    _PricingOffer(
      title: 'Сборка торговой мебели и оборудования',
      price: 'от 2 500 ₽',
      description:
          'Монтаж витрин, стеллажей, прилавков, торговых островов и складских систем. Подходит для магазинов и сетевых точек.',
    ),
    _PricingOffer(
      title: 'Сборка металлической мебели',
      price: 'от 1 800 ₽',
      description:
          'Шкафы, сейфы, стеллажи, перегородки, рабочие столы и другое оборудование для учреждений и производств.',
    ),
    _PricingOffer(
      title: 'Выезд и предварительный расчёт',
      price: 'бесплатно',
      description:
          'Оцениваем объём работ, обсуждаем сроки и подготавливаем смету до старта проекта без обязательств.',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

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
                'ЦЕНЫ И ФОРМАТ РАБОТЫ',
                textAlign: TextAlign.center,
                style: theme.textTheme.displaySmall,
              ),
              const SizedBox(height: 12),
              Text(
                'Точный расчёт делаем по объёму, срокам и сложности. Для крупных объектов готовим отдельную смету и закрепляем ответственного бригадира.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium,
              ),
              const SizedBox(height: 24),
              LayoutBuilder(
                builder: (context, constraints) {
                  final width = constraints.maxWidth;
                  final columns = width >= 980 ? 2 : 1;
                  const spacing = 20.0;
                  final itemWidth =
                      (width - spacing * (columns - 1)) / columns;

                  return Wrap(
                    spacing: spacing,
                    runSpacing: spacing,
                    children: _offers
                        .map(
                          (offer) => SizedBox(
                            width: itemWidth,
                            child: _PricingCard(offer: offer),
                          ),
                        )
                        .toList(),
                  );
                },
              ),
              const SizedBox(height: 20),
              Text(
                'Гарантия, договор и бесплатный первичный выезд входят в формат работы.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PricingCard extends StatelessWidget {
  const _PricingCard({required this.offer});

  final _PricingOffer offer;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return DecoratedBox(
      decoration: BoxDecoration(
        color: theme.colorScheme.surface.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: AppThemeTokens.brandPrimary.withValues(alpha: 0.12),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              offer.title,
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            Text(
              offer.price,
              style: theme.textTheme.headlineSmall?.copyWith(
                color: AppThemeTokens.brandPrimary,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              offer.description,
              style: theme.textTheme.bodyMedium,
            ),
          ],
        ),
      ),
    );
  }
}

class _PricingOffer {
  const _PricingOffer({
    required this.title,
    required this.price,
    required this.description,
  });

  final String title;
  final String price;
  final String description;
}
