class NotFoundServerException implements Exception {}

class ServerException implements Exception {
  final String message;
  final int? statusCode;
  final Map<String, dynamic>? details;
  final String? requestUrl;
  final Map<String, String>? requestHeaders;
  final String? requestBody;
  final String? responseBody;
  final String? stackTrace;

  const ServerException({
    required this.message,
    this.statusCode,
    this.details,
    this.requestUrl,
    this.requestHeaders,
    this.requestBody,
    this.responseBody,
    this.stackTrace,
  });

  @override
  String toString() {
    final buffer = StringBuffer();
    buffer.writeln('ServerException: $message');

    if (statusCode != null) {
      buffer.writeln('Status Code: $statusCode');
    }

    if (requestUrl != null) {
      buffer.writeln('Request URL: $requestUrl');
    }

    if (requestHeaders != null && requestHeaders!.isNotEmpty) {
      buffer.writeln('Request Headers: $requestHeaders');
    }

    if (requestBody != null) {
      buffer.writeln('Request Body: $requestBody');
    }

    if (responseBody != null) {
      buffer.writeln('Response Body: $responseBody');
    }

    if (details != null && details!.isNotEmpty) {
      buffer.writeln('Details: $details');
    }

    if (stackTrace != null) {
      buffer.writeln('Stack Trace: $stackTrace');
    }

    return buffer.toString();
  }
}

class NetworkException implements Exception {
  final String message;
  final String? originalError;
  final String? requestUrl;
  final String? stackTrace;

  const NetworkException({
    required this.message,
    this.originalError,
    this.requestUrl,
    this.stackTrace,
  });

  @override
  String toString() {
    final buffer = StringBuffer();
    buffer.writeln('NetworkException: $message');

    if (requestUrl != null) {
      buffer.writeln('Request URL: $requestUrl');
    }

    if (originalError != null) {
      buffer.writeln('Original Error: $originalError');
    }

    if (stackTrace != null) {
      buffer.writeln('Stack Trace: $stackTrace');
    }

    return buffer.toString();
  }
}

class CacheException implements Exception {
  final String message;

  const CacheException({required this.message});

  @override
  String toString() => 'CacheException: $message';
}
