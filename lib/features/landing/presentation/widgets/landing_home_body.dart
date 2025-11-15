// lib/features/landing/presentation/widgets/landing_home_body.dart
import 'package:flutter/material.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/callback_request/landing_callback_request_section.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_hero_carousel.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_how_we_work.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_repair_categories.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_service_center_section.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_why_us_benefits.dart';

/// Body content of the landing page (without its own scrolling).
class LandingHomeBody extends StatelessWidget {
  const LandingHomeBody({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: const [
        RepaintBoundary(child: LandingHeroCarousel()),
        SizedBox(height: 48),
        LandingRepairCategories(),
        SizedBox(height: 64),
        LandingHowWeWork(),
        SizedBox(height: 64),
        LandingServiceCenterSection(),
        SizedBox(height: 64),
        LandingWhyUsBenefitsSection(),
        SizedBox(height: 64),
        LandingCallbackRequestSection(),
        SizedBox(height: 80),
      ],
    );
  }
}
