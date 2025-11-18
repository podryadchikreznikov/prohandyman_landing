import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:prohandyman_landing/core/theme/app_theme_tokens.dart';
import 'package:prohandyman_landing/presentation/widgets/tilt_wrapper.dart';

import '../../../../../core/smart_captcha/smart_captcha_service.dart';
import '../../../../../injection_container.dart';
import '../../cubit/callback_request/callback_request_cubit.dart';
import '../../../domain/usecases/submit_callback_request.dart';
import 'callback_request_form.dart';

class LandingCallbackRequestSection extends StatelessWidget {
  const LandingCallbackRequestSection({
    super.key,
    this.tiltPointerController,
  });

  final TiltGlobalPointerController? tiltPointerController;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: BlocProvider(
        create: (_) => CallbackRequestCubit(
          submitCallbackRequest: sl<SubmitCallbackRequest>(),
          smartCaptchaService: sl<SmartCaptchaService>(),
        ),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: AppThemeTokens.contentMaxWidth,
            ),
            child: DecoratedBox(
              decoration: BoxDecoration(
                color: colorScheme.surface.withValues(alpha: 0.96),
                borderRadius: BorderRadius.zero,
              ),
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: _CallbackRequestBody(
                  tiltPointerController: tiltPointerController,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _CallbackRequestBody extends StatelessWidget {
  const _CallbackRequestBody({this.tiltPointerController});

  final TiltGlobalPointerController? tiltPointerController;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final isWide = constraints.maxWidth >= 900;

        if (!isWide) {
          return const CallbackRequestForm();
        }

        final theme = Theme.of(context);
        final colorScheme = theme.colorScheme;

        return Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Expanded(
              flex: 4,
              child: CallbackRequestForm(),
            ),
            const SizedBox(width: 32),
            Expanded(
              flex: 6,
              child: TiltWrapper(
                borderRadius: BorderRadius.zero,
                enableLight: false,
                globalPointerMode: tiltPointerController != null,
                globalPointerController: tiltPointerController,
                invertGlobalPointer: true,
                child: AspectRatio(
                  aspectRatio: 4 / 3,
                  child: ClipRRect(
                    borderRadius: BorderRadius.zero,
                    child: Container(
                      decoration: BoxDecoration(
                        color: colorScheme.surface,
                        image: const DecorationImage(
                          image: AssetImage('assets/service_form_hero.jpg'),
                          fit: BoxFit.cover,
                          alignment: Alignment.center,
                        ),
                      ),
                    ),
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
