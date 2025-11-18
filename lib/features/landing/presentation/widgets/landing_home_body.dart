// lib/features/landing/presentation/widgets/landing_home_body.dart
import 'package:flutter/material.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/callback_request/landing_callback_request_section.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_hero_carousel.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_how_we_work.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_repair_categories.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_service_center_section.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_why_us_benefits.dart';
import 'package:prohandyman_landing/features/landing/presentation/widgets/landing_partners_section.dart';
import 'package:prohandyman_landing/presentation/widgets/tilt_wrapper.dart';

/// Body content of the landing page (without its own scrolling).
class LandingHomeBody extends StatelessWidget {
  const LandingHomeBody({
    super.key,
    this.onInnerScrollLockChanged,
    this.tiltPointerController,
  });

  final ValueChanged<bool>? onInnerScrollLockChanged;
  final TiltGlobalPointerController? tiltPointerController;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      mainAxisSize: MainAxisSize.min,
      children: [
        const RepaintBoundary(child: LandingHeroCarousel()),
        const SizedBox(height: 48),
        LandingRepairCategories(
          onInnerScrollLockChanged: onInnerScrollLockChanged,
        ),
        const SizedBox(height: 64),
        const LandingHowWeWork(),
        const SizedBox(height: 64),
        LandingServiceCenterSection(
          tiltPointerController: tiltPointerController,
        ),
        const SizedBox(height: 64),
        const LandingWhyUsBenefitsSection(),
        const SizedBox(height: 64),
        const LandingPartnersSection(),
        const SizedBox(height: 64),
        LandingCallbackRequestSection(
          tiltPointerController: tiltPointerController,
        ),
        const SizedBox(height: 80),
      ],
    );
  }
}
