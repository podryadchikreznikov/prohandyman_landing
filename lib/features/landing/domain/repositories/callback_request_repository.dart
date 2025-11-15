import 'package:dartz/dartz.dart';

import '../../../../core/error/failure.dart';
import '../entities/callback_request_payload.dart';

abstract class CallbackRequestRepository {
  Future<Either<Failure, Unit>> submitRequest({
    required CallbackRequestPayload payload,
    String? captchaToken,
  });
}
