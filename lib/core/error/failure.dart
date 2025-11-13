import 'package:equatable/equatable.dart';

abstract class Failure extends Equatable {
  final String message;
  final String? details;
  final int? statusCode;

  const Failure({required this.message, this.details, this.statusCode});

  @override
  List<Object?> get props => [message, details, statusCode];

  @override
  String toString() {
    final buffer = StringBuffer();
    buffer.writeln('Failure: $message');

    if (statusCode != null) {
      buffer.writeln('Status Code: $statusCode');
    }

    if (details != null && details!.isNotEmpty) {
      buffer.writeln('Details: $details');
    }

    return buffer.toString();
  }
}

class DatabaseFailure extends Failure {
  const DatabaseFailure({required super.message, super.details, super.statusCode});
}

class ConnectionFailure extends Failure {
  const ConnectionFailure({required super.message, super.details, super.statusCode});
}

class MessageFailure extends Failure {
  const MessageFailure({required super.message, super.details, super.statusCode});
}

class ServerFailure extends Failure {
  const ServerFailure({super.message = 'Ошибка сервера', super.details, super.statusCode});
}

class CacheFailure extends Failure {
  const CacheFailure({super.message = 'Ошибка кэша', super.details, super.statusCode});
}

class NetworkFailure extends Failure {
  const NetworkFailure({super.message = 'Ошибка сети', super.details, super.statusCode});
}

class UnexpectedFailure extends Failure {
  const UnexpectedFailure({
    super.message = 'Неожиданная ошибка',
    super.details,
    super.statusCode,
  });
}

class AccessDeniedFailure extends Failure {
  const AccessDeniedFailure({
    super.message = 'Недостаточно прав',
    super.details,
    super.statusCode,
  });
}
