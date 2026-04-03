import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';

import 'landing_services_models.dart';

class LandingServicesOverviewSection extends StatelessWidget {
  const LandingServicesOverviewSection({super.key});

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
                'УСЛУГИ',
                textAlign: TextAlign.center,
                style: theme.textTheme.displaySmall,
              ),
              const SizedBox(height: 12),
              Text(
                'Каждый блок — это отдельный тип работ с понятной ценой, сроками выполнения и окном на согласование.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium,
              ),
              const SizedBox(height: 24),
              for (var index = 0; index < landingServiceOffers.length; index++) ...[
                _ServiceOfferRow(
                  offer: landingServiceOffers[index],
                  imageOnLeft: index.isEven,
                ),
                if (index != landingServiceOffers.length - 1)
                  const SizedBox(height: 28),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ServiceOfferRow extends StatelessWidget {
  const _ServiceOfferRow({
    required this.offer,
    required this.imageOnLeft,
  });

  final LandingServiceOffer offer;
  final bool imageOnLeft;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isCompact = constraints.maxWidth < 860;

        if (isCompact) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _ServiceImage(offer: offer),
              const SizedBox(height: 14),
              _ServiceText(offer: offer),
            ],
          );
        }

        final image = Expanded(
          flex: 5,
          child: _ServiceImage(offer: offer),
        );
        final text = Expanded(
          flex: 5,
          child: _ServiceText(offer: offer),
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

class _ServiceImage extends StatelessWidget {
  const _ServiceImage({required this.offer});

  final LandingServiceOffer offer;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        color: AppThemeTokens.backgroundSurface,
      ),
      child: AspectRatio(
        aspectRatio: 4 / 3,
        child: Image.asset(
          offer.imagePath,
          fit: BoxFit.cover,
        ),
      ),
    );
  }
}

class _ServiceText extends StatelessWidget {
  const _ServiceText({required this.offer});

  final LandingServiceOffer offer;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final titleStyle = theme.textTheme.titleMedium?.copyWith(
      color: AppThemeTokens.brandPrimaryDark,
      fontWeight: FontWeight.w700,
    );
    final bodyStyle = theme.textTheme.bodyMedium?.copyWith(
      color: AppThemeTokens.textDark,
      height: 1.45,
    );
    final labelStyle = theme.textTheme.labelSmall?.copyWith(
      color: AppThemeTokens.brandPrimaryDark,
      fontWeight: FontWeight.w700,
      letterSpacing: 0.8,
    );
    final valueStyle = theme.textTheme.titleSmall?.copyWith(
      color: AppThemeTokens.textDark,
      fontWeight: FontWeight.w600,
    );

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(offer.title, style: titleStyle),
          const SizedBox(height: 12),
          Text(offer.summary, style: bodyStyle),
          const SizedBox(height: 18),
          Container(
            height: 2,
            color: AppThemeTokens.brandPrimary,
          ),
          const SizedBox(height: 14),
          Wrap(
            spacing: 20,
            runSpacing: 12,
            children: [
              _MetaChip(label: 'Цена', value: offer.priceFrom, labelStyle: labelStyle, valueStyle: valueStyle),
              _MetaChip(label: 'Срок работ', value: offer.workDuration, labelStyle: labelStyle, valueStyle: valueStyle),
              _MetaChip(label: 'Согласование', value: offer.approvalTime, labelStyle: labelStyle, valueStyle: valueStyle),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            'Финальная смета закрепляется после выезда и подтверждения объёма работ.',
            style: theme.textTheme.bodySmall?.copyWith(
              color: AppThemeTokens.textDark,
            ),
          ),
        ],
      ),
    );
  }
}

class _MetaChip extends StatelessWidget {
  const _MetaChip({
    required this.label,
    required this.value,
    required this.labelStyle,
    required this.valueStyle,
  });

  final String label;
  final String value;
  final TextStyle? labelStyle;
  final TextStyle? valueStyle;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 160,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label.toUpperCase(), style: labelStyle),
          const SizedBox(height: 4),
          Text(value, style: valueStyle),
        ],
      ),
    );
  }
}
