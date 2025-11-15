import 'package:dio/dio.dart';
import 'package:get_it/get_it.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:talker_dio_logger/talker_dio_logger.dart';
import 'package:talker_flutter/talker_flutter.dart';
import 'package:uuid/uuid.dart';

import 'core/constants/constants.dart';
import 'core/frontend_error/frontend_error_service.dart';
import 'core/smart_captcha/smart_captcha_service.dart';
import 'features/landing/data/data_source/callback_request_remote_data_source.dart';
import 'features/landing/data/repositories/callback_request_repository_impl.dart';
import 'features/landing/domain/repositories/callback_request_repository.dart';
import 'features/landing/domain/usecases/submit_callback_request.dart';
import 'router.dart';

/// Global service locator used across the app layers.
final sl = GetIt.instance;

/// Centralised dependency registration.
///
/// Keep this lean: register interfaces here and wire concrete
/// implementations inside dedicated setup helpers.
Future<void> setupLocator() async {
  final talker = TalkerFlutter.init();
  sl.registerSingleton<Talker>(talker);

  final prefs = await SharedPreferences.getInstance();
  sl.registerSingleton<SharedPreferences>(prefs);

  sl.registerLazySingleton<Uuid>(() => const Uuid());

  sl.registerLazySingleton<Dio>(() {
    final dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.apiBaseUrl,
        connectTimeout: AppConfig.defaultTimeout,
        receiveTimeout: AppConfig.defaultTimeout,
      ),
    );

    dio.interceptors.add(
      TalkerDioLogger(
        talker: sl<Talker>(),
        settings: const TalkerDioLoggerSettings(
          printRequestData: false,
          printResponseData: false,
          printResponseMessage: false,
        ),
      ),
    );

    return dio;
  });

  sl.registerLazySingleton<SmartCaptchaService>(
    () => createSmartCaptchaService(sl<Talker>()),
  );

  sl.registerLazySingleton<FrontendErrorService>(
    () => createFrontendErrorService(sl<Talker>()),
  );

  sl.registerLazySingleton<CallbackRequestRemoteDataSource>(
    () => CallbackRequestRemoteDataSourceImpl(dio: sl(), uuid: sl()),
  );

  sl.registerLazySingleton<CallbackRequestRepository>(
    () => CallbackRequestRepositoryImpl(sl()),
  );

  sl.registerLazySingleton<SubmitCallbackRequest>(
    () => SubmitCallbackRequest(sl()),
  );

  sl.registerLazySingleton<AppRouter>(AppRouter.new);
}
