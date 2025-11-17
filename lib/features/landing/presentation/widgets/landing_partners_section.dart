import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';

class LandingPartnersSection extends StatelessWidget {
  const LandingPartnersSection({super.key});

  static const _partnerLogos = [
    'assets/handyman_images/logo_partner_01.png',
    'assets/handyman_images/logo_partner_02.png',
    'assets/handyman_images/logo_partner_04.png',
    'assets/handyman_images/logo_partner_05.png',
    'assets/handyman_images/logo_partner_06.png',
    'assets/handyman_images/logo_partner_07.png',
    'assets/handyman_images/logo_partner_08.png',
    'assets/handyman_images/logo_partner_09.png',
    'assets/handyman_images/logo_partner_10.png',
    'assets/handyman_images/logo_partner_11.png',
    'assets/handyman_images/logo_partner_12.png',
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Padding
    (
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
              const SizedBox(height: 24),
              LayoutBuilder(
                builder: (context, constraints) {
                  const spacing = 24.0;

                  return Wrap(
                    alignment: WrapAlignment.center,
                    spacing: spacing,
                    runSpacing: spacing,
                    children: _partnerLogos
                        .map(
                          (path) => _PartnerLogo(path: path),
                        )
                        .toList(),
                  );
                },
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PartnerLogo extends StatelessWidget {
  const _PartnerLogo({required this.path});

  final String path;

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(
        maxHeight: 64,
      ),
      child: FittedBox(
        fit: BoxFit.scaleDown,
        child: Image.asset(path),
      ),
    );
  }
}
