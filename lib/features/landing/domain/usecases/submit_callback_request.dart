import 'package:dartz/dartz.dart';

import '../../../../core/error/failure.dart';
import '../entities/callback_request_payload.dart';
import '../repositories/callback_request_repository.dart';

class SubmitCallbackRequest {
  const SubmitCallbackRequest(this._repository);

  final CallbackRequestRepository _repository;

  Future<Either<Failure, Unit>> call({
    required CallbackRequestPayload payload,
    String? captchaToken,
  }) {
    return _repository.submitRequest(
      payload: payload,
      captchaToken: captchaToken,
    );
  }
}
