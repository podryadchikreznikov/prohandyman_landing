import 'package:dio/dio.dart';
import 'package:uuid/uuid.dart';

import '../../../../core/constants/constants.dart';
import '../models/callback_request_model.dart';

abstract class CallbackRequestRemoteDataSource {
  Future<void> submitRequest({
    required CallbackRequestModel model,
    String? captchaToken,
  });
}

class CallbackRequestRemoteDataSourceImpl
    implements CallbackRequestRemoteDataSource {
  CallbackRequestRemoteDataSourceImpl({
    required Dio dio,
    required Uuid uuid,
  })  : _dio = dio,
        _uuid = uuid;

  final Dio _dio;
  final Uuid _uuid;

  @override
  Future<void> submitRequest({
    required CallbackRequestModel model,
    String? captchaToken,
  }) async {
    final payload = model.toJson();
    final headers = <String, dynamic>{
      'Content-Type': 'application/json',
      'X-Correlation-Id': _uuid.v4(),
      'X-Request-Schema-Hash': AppConfig.callbackRequestSchemaHash,
      'X-Response-Schema-Hash': AppConfig.callbackResponseSchemaHash,
      if (captchaToken != null && captchaToken.isNotEmpty)
        'SmartCaptcha-Token': captchaToken,
    };

    await _dio.post<void>(
      '${AppConfig.callbackRequestApiBaseUrl}${AppConfig.callbackRequestPath}',
      data: payload,
      options: Options(headers: headers),
    );
  }
}
