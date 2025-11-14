// lib/features/landing/presentation/widgets/landing_home_body.dart
import 'package:flutter/material.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_hero_carousel.dart';

/// Body content of the landing page (without its own scrolling).
class LandingHomeBody extends StatelessWidget {
  const LandingHomeBody({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        const RepaintBoundary(child: LandingHeroCarousel()),
        const SizedBox(height: 24),
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: AppThemeTokens.contentMaxWidth,
            ),
            child: const Padding(
              padding: EdgeInsets.all(16),
              child: Text(
                'Ключевые преимущества работы с нами и краткое описание услуг.',
                textAlign: TextAlign.center,
              ),
            ),
          ),
        ),
      ],
    );
  }
}
