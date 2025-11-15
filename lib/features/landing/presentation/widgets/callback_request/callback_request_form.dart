import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../cubit/callback_request/callback_request_cubit.dart';
import '../../cubit/callback_request/callback_request_state.dart';

class CallbackRequestForm extends StatefulWidget {
  const CallbackRequestForm({super.key});

  @override
  State<CallbackRequestForm> createState() => _CallbackRequestFormState();
}

class _CallbackRequestFormState extends State<CallbackRequestForm> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _nameController;
  late final TextEditingController _phoneController;
  late final TextEditingController _emailController;
  late final TextEditingController _commentController;
  bool _suppressTextUpdates = false;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController();
    _phoneController = TextEditingController();
    _emailController = TextEditingController();
    _commentController = TextEditingController();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _phoneController.dispose();
    _emailController.dispose();
    _commentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<CallbackRequestCubit, CallbackRequestState>(
      listener: (context, state) {
        final messenger = ScaffoldMessenger.of(context);
        final colorScheme = Theme.of(context).colorScheme;

        if (state.status == CallbackRequestStatus.success) {
          _suppressTextUpdates = true;
          _nameController.clear();
          _phoneController.clear();
          _emailController.clear();
          _commentController.clear();
          _suppressTextUpdates = false;
          messenger.showSnackBar(
            SnackBar(
              content: const Text(
                'Заявка отправлена. Мы скоро свяжемся с вами.',
              ),
              backgroundColor: colorScheme.primary,
            ),
          );
        } else if (state.status == CallbackRequestStatus.failure &&
            state.errorMessage != null &&
            state.errorMessage!.isNotEmpty) {
          messenger.showSnackBar(
            SnackBar(
              content: Text(state.errorMessage!),
              backgroundColor: colorScheme.error,
            ),
          );
        }
      },
      builder: (context, state) {
        final theme = Theme.of(context);
        final colorScheme = theme.colorScheme;
        final dimmedColor = colorScheme.onSurface.withValues(alpha: 0.5);
        final activeColor = colorScheme.onSurface.withValues(alpha: 0.8);

        final canSubmitByPhone =
            !state.isBusy && _isValidPhone(_phoneController.text);

        return Form(
          key: _formKey,
          autovalidateMode: AutovalidateMode.onUserInteraction,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Обратный звонок', style: theme.textTheme.displaySmall),
              const SizedBox(height: 24),
              _FeedbackBanner(state: state),
              TextFormField(
                controller: _nameController,
                decoration: InputDecoration(
                  labelText: 'Имя (необязательно)',
                  hintText: 'Как к вам обращаться?',
                  labelStyle: TextStyle(
                    color: _nameController.text.trim().isEmpty
                        ? dimmedColor
                        : activeColor,
                  ),
                  hintStyle: TextStyle(color: dimmedColor),
                  border: const OutlineInputBorder(
                    borderRadius: BorderRadius.zero,
                  ),
                ),
                textInputAction: TextInputAction.next,
                onChanged: _handleNameChanged,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _phoneController,
                keyboardType: TextInputType.phone,
                decoration: InputDecoration(
                  labelText: 'Телефон *',
                  hintText: '+7 (999) 000-00-00',
                  labelStyle: TextStyle(
                    color: colorScheme.error,
                    fontWeight: FontWeight.w600,
                  ),
                  border: const OutlineInputBorder(
                    borderRadius: BorderRadius.zero,
                  ),
                ),
                textInputAction: TextInputAction.next,
                onChanged: _handlePhoneChanged,
                validator: _validatePhone,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _emailController,
                keyboardType: TextInputType.emailAddress,
                decoration: InputDecoration(
                  labelText: 'Email (необязательно)',
                  hintText: 'you@example.com',
                  labelStyle: TextStyle(
                    color: _emailController.text.trim().isEmpty
                        ? dimmedColor
                        : activeColor,
                  ),
                  hintStyle: TextStyle(color: dimmedColor),
                  border: const OutlineInputBorder(
                    borderRadius: BorderRadius.zero,
                  ),
                ),
                textInputAction: TextInputAction.next,
                onChanged: _handleEmailChanged,
                validator: _validateEmail,
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _commentController,
                decoration: InputDecoration(
                  labelText: 'Комментарий (необязательно)',
                  hintText: 'Опишите задачу или удобное время для связи',
                  labelStyle: TextStyle(
                    color: _commentController.text.trim().isEmpty
                        ? dimmedColor
                        : activeColor,
                  ),
                  hintStyle: TextStyle(color: dimmedColor),
                  border: const OutlineInputBorder(
                    borderRadius: BorderRadius.zero,
                  ),
                ),
                maxLines: 4,
                minLines: 3,
                onChanged: _handleCommentChanged,
              ),
              const SizedBox(height: 24),
              Row(
                children: [
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: canSubmitByPhone
                          ? () => _submit(context)
                          : null,
                      icon: state.isBusy
                          ? SizedBox(
                              width: 18,
                              height: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                valueColor: AlwaysStoppedAnimation<Color>(
                                  colorScheme.onPrimary,
                                ),
                              ),
                            )
                          : const Icon(Icons.send_outlined),
                      label: Text(
                        state.isBusy ? 'Отправляем...' : 'Отправить заявку',
                      ),
                      style: ButtonStyle(
                        padding: WidgetStateProperty.all(
                          const EdgeInsets.symmetric(vertical: 16),
                        ),
                        backgroundColor:
                            WidgetStateProperty.resolveWith<Color?>((states) {
                              if (states.contains(WidgetState.disabled)) {
                                return colorScheme.surface;
                              }
                              return colorScheme.primary;
                            }),
                        foregroundColor:
                            WidgetStateProperty.resolveWith<Color?>((states) {
                              if (states.contains(WidgetState.disabled)) {
                                return colorScheme.primary.withValues(
                                  alpha: 0.5,
                                );
                              }
                              return colorScheme.onPrimary;
                            }),
                        shape: WidgetStateProperty.resolveWith<OutlinedBorder>((
                          states,
                        ) {
                          final isDisabled = states.contains(
                            WidgetState.disabled,
                          );
                          return RoundedRectangleBorder(
                            borderRadius: BorderRadius.zero,
                            side: BorderSide(
                              color: colorScheme.primary,
                              width: isDisabled ? 3.0 : 1.2,
                            ),
                          );
                        }),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerLeft,
                child: InkWell(
                  onTap: _openSmartCaptchaPolicy,
                  child: Text(
                    'Политика обработки данных (smart captcha)',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurface.withValues(alpha: 0.6),
                      decoration: TextDecoration.underline,
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  void _submit(BuildContext context) {
    final form = _formKey.currentState;
    if (form == null) {
      return;
    }
    if (!form.validate()) {
      return;
    }
    FocusScope.of(context).unfocus();
    context.read<CallbackRequestCubit>().submit();
  }

  void _handleNameChanged(String value) {
    if (_suppressTextUpdates) return;
    context.read<CallbackRequestCubit>().updateName(value);
  }

  void _handlePhoneChanged(String value) {
    if (_suppressTextUpdates) return;
    context.read<CallbackRequestCubit>().updatePhone(value);
  }

  void _handleEmailChanged(String value) {
    if (_suppressTextUpdates) return;
    context.read<CallbackRequestCubit>().updateEmail(value);
  }

  void _handleCommentChanged(String value) {
    if (_suppressTextUpdates) return;
    context.read<CallbackRequestCubit>().updateComment(value);
  }

  String? _validatePhone(String? value) {
    final phone = value?.trim() ?? '';
    if (phone.isEmpty) {
      return 'Укажите телефон';
    }
    if (!_isValidPhone(phone)) {
      return 'Неверный номер';
    }
    return null;
  }

  String? _validateEmail(String? value) {
    final email = value?.trim() ?? '';
    if (email.isEmpty) {
      return null;
    }
    if (!_isValidEmail(email)) {
      return 'Неверный email';
    }
    return null;
  }

  bool _isValidPhone(String value) {
    final phone = value.trim();
    if (phone.isEmpty) return false;
    final digits = phone.replaceAll(RegExp(r'[^\d+]'), '');
    // Минимум 10 цифр для более реалистичного номера
    return digits.length >= 10;
  }

  bool _isValidEmail(String value) {
    final email = value.trim();
    if (email.isEmpty) return true;
    final regex = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');
    return regex.hasMatch(email);
  }

  Future<void> _openSmartCaptchaPolicy() async {
    const url = 'https://yandex.ru/legal/smartcaptcha_notice/ru/';
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }
}

class _FeedbackBanner extends StatelessWidget {
  const _FeedbackBanner({required this.state});

  final CallbackRequestState state;

  @override
  Widget build(BuildContext context) {
    final showSuccess = state.status == CallbackRequestStatus.success;
    final showError =
        state.status == CallbackRequestStatus.failure &&
        (state.errorMessage?.isNotEmpty ?? false);

    if (!showSuccess && !showError) {
      return const SizedBox.shrink();
    }

    final colorScheme = Theme.of(context).colorScheme;
    final backgroundColor = showSuccess
        ? colorScheme.primary.withValues(alpha: 0.1)
        : colorScheme.error.withValues(alpha: 0.12);
    final foregroundColor = showSuccess
        ? colorScheme.primary
        : colorScheme.error;
    final icon = showSuccess ? Icons.check_circle : Icons.error_outline;
    final text = showSuccess
        ? 'Спасибо! Мы уже получили заявку и вскоре свяжемся.'
        : state.errorMessage!;

    return Padding(
      padding: const EdgeInsets.only(bottom: 20),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: backgroundColor,
          borderRadius: BorderRadius.zero,
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: foregroundColor),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                text,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: foregroundColor,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
            IconButton(
              icon: Icon(Icons.close, size: 18, color: foregroundColor),
              splashRadius: 18,
              onPressed: () =>
                  context.read<CallbackRequestCubit>().dismissFeedback(),
            ),
          ],
        ),
      ),
    );
  }
}
