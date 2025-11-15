import 'package:dio/dio.dart';
import 'package:talker/talker.dart';

/// Base log for HTTP-related events.
class NetworkLog extends TalkerLog {
  NetworkLog(
    String super.message, {
    dynamic error,
    super.stackTrace,
  }) : super(error: error);

  @override
  String get title => 'HTTP';

  @override
  String get key => 'http';
}

/// Log for outgoing HTTP requests.
class HttpRequestLog extends NetworkLog {
  HttpRequestLog(
    RequestOptions options,
  ) : super(
          '→ ${options.method} ${options.uri}',
        );
}

/// Log for successful HTTP responses.
class HttpResponseLog extends NetworkLog {
  HttpResponseLog(
    Response response,
  ) : super(
          '← ${response.requestOptions.method} ${response.requestOptions.uri} '
          '${response.statusCode}',
        );
}

/// Log for HTTP errors.
class HttpErrorLog extends NetworkLog {
  HttpErrorLog(
    DioException error,
  ) : super(
          '! ${error.requestOptions.method} ${error.requestOptions.uri} '
          '${error.response?.statusCode ?? '-'}',
          error: error,
          stackTrace: error.stackTrace,
        );
}

