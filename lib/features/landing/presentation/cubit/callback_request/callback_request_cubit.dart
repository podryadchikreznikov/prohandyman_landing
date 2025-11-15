import 'package:flutter_bloc/flutter_bloc.dart';

import '../../../../../core/smart_captcha/smart_captcha_service.dart';
import '../../../domain/entities/callback_request_payload.dart';
import '../../../domain/usecases/submit_callback_request.dart';
import 'callback_request_state.dart';

class CallbackRequestCubit extends Cubit<CallbackRequestState> {
  CallbackRequestCubit({
    required SubmitCallbackRequest submitCallbackRequest,
    required SmartCaptchaService smartCaptchaService,
  })  : _submitCallbackRequest = submitCallbackRequest,
        _smartCaptchaService = smartCaptchaService,
        super(const CallbackRequestState());

  final SubmitCallbackRequest _submitCallbackRequest;
  final SmartCaptchaService _smartCaptchaService;

  void updateName(String value) => _emitInputChange(name: value);

  void updatePhone(String value) => _emitInputChange(phone: value);

  void updateEmail(String value) => _emitInputChange(email: value);

  void updateComment(String value) => _emitInputChange(comment: value);

  void dismissFeedback() {
    if (state.status == CallbackRequestStatus.success ||
        state.status == CallbackRequestStatus.failure) {
      emit(
        state.copyWith(
          status: CallbackRequestStatus.idle,
          clearError: true,
        ),
      );
    }
  }

  Future<void> submit() async {
    if (state.isBusy) {
      return;
    }

    if (!state.hasContact) {
      emit(
        state.copyWith(
          status: CallbackRequestStatus.failure,
          errorMessage: 'Укажите телефон или email, чтобы мы могли ответить.',
        ),
      );
      return;
    }

    emit(
      state.copyWith(
        status: CallbackRequestStatus.submitting,
        clearError: true,
      ),
    );

    String? captchaToken;

    final shouldTriggerCaptcha = _smartCaptchaService.isSupported &&
        _smartCaptchaService.isInitialized;

    if (shouldTriggerCaptcha) {
      try {
        captchaToken = await _smartCaptchaService.verify();
      } catch (error) {
        emit(
          state.copyWith(
            status: CallbackRequestStatus.failure,
            errorMessage: 'Не удалось подтвердить SmartCaptcha. Попробуйте ещё раз.',
          ),
        );
        _smartCaptchaService.reset();
        return;
      }
    }

    final payload = CallbackRequestPayload(
      userName: state.name.trim().isEmpty ? null : state.name.trim(),
      phoneNumber: state.phone.trim().isEmpty ? null : state.phone.trim(),
      email: state.email.trim().isEmpty ? null : state.email.trim(),
      comment: state.comment.trim().isEmpty ? null : state.comment.trim(),
    );

    final result = await _submitCallbackRequest(
      payload: payload,
      captchaToken: captchaToken,
    );

    result.fold(
      (failure) {
        emit(
          state.copyWith(
            status: CallbackRequestStatus.failure,
            errorMessage: failure.message,
          ),
        );
      },
      (_) {
        emit(
          state.copyWith(
            name: '',
            phone: '',
            email: '',
            comment: '',
            status: CallbackRequestStatus.success,
            clearError: true,
          ),
        );
      },
    );

    if (shouldTriggerCaptcha) {
      _smartCaptchaService.reset();
    }
  }

  void _emitInputChange({
    String? name,
    String? phone,
    String? email,
    String? comment,
  }) {
    var next = state.copyWith(
      name: name,
      phone: phone,
      email: email,
      comment: comment,
      clearError: true,
    );

    if (state.status == CallbackRequestStatus.success ||
        state.status == CallbackRequestStatus.failure) {
      next = next.copyWith(status: CallbackRequestStatus.idle);
    }

    emit(next);
  }
}
