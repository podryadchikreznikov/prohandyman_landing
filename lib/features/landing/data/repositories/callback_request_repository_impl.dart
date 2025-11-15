import 'package:dartz/dartz.dart';
import 'package:dio/dio.dart';

import '../../../../core/error/failure.dart';
import '../../domain/entities/callback_request_payload.dart';
import '../../domain/repositories/callback_request_repository.dart';
import '../data_source/callback_request_remote_data_source.dart';
import '../models/callback_request_model.dart';

class CallbackRequestRepositoryImpl implements CallbackRequestRepository {
  CallbackRequestRepositoryImpl(this._remoteDataSource);

  final CallbackRequestRemoteDataSource _remoteDataSource;

  @override
  Future<Either<Failure, Unit>> submitRequest({
    required CallbackRequestPayload payload,
    String? captchaToken,
  }) async {
    try {
      final model = CallbackRequestModel.fromEntity(payload);
      await _remoteDataSource.submitRequest(
        model: model,
        captchaToken: captchaToken,
      );
      return const Right(unit);
    } on DioException catch (error) {
      return Left(_mapDioError(error));
    } catch (error) {
      return Left(
        UnexpectedFailure(
          message: 'Неизвестная ошибка при отправке заявки',
          details: error.toString(),
        ),
      );
    }
  }

  Failure _mapDioError(DioException error) {
    final statusCode = error.response?.statusCode;
    final rawDetails = error.response?.data;
    final message = _extractMessage(rawDetails);
    final details = _stringifyDetails(rawDetails);

    if (statusCode == 400) {
      return MessageFailure(
        message: message ?? 'Проверьте корректность данных',
        details: details,
        statusCode: statusCode,
      );
    }

    if (statusCode == 401 || statusCode == 403) {
      return AccessDeniedFailure(
        message: message ?? 'Не пройдена SmartCaptcha или отклонено авторизатором',
        details: details,
        statusCode: statusCode,
      );
    }

    if (statusCode != null && statusCode >= 500) {
      return ServerFailure(
        message: message ?? 'Сервер временно недоступен',
        details: details,
        statusCode: statusCode,
      );
    }

    if (error.type == DioExceptionType.unknown ||
        error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.receiveTimeout ||
        error.type == DioExceptionType.connectionError) {
      return NetworkFailure(
        message: message ?? 'Сетевая ошибка. Проверьте соединение',
        details: details,
        statusCode: statusCode,
      );
    }

    return UnexpectedFailure(
      message: message ?? 'Неизвестная ошибка при обращении к API',
      details: details,
      statusCode: statusCode,
    );
  }

  String? _extractMessage(dynamic data) {
    if (data is Map<String, dynamic>) {
      final direct = data['message'];
      if (direct is String && direct.isNotEmpty) {
        return direct;
      }

      final error = data['error'];
      if (error is Map<String, dynamic>) {
        final nestedMessage = error['message'];
        if (nestedMessage is String && nestedMessage.isNotEmpty) {
          return nestedMessage;
        }
        final code = error['code'];
        if (code is String && code.isNotEmpty) {
          return code;
        }
      } else if (error is String && error.isNotEmpty) {
        return error;
      }
    } else if (data is String && data.isNotEmpty) {
      return data;
    }
    return null;
  }

  String? _stringifyDetails(dynamic data) {
    if (data == null) {
      return null;
    }
    if (data is String) {
      return data;
    }
    try {
      return data.toString();
    } catch (_) {
      return null;
    }
  }
}
