import 'package:dio/dio.dart';
import 'package:get_it/get_it.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:talker_flutter/talker_flutter.dart';

import 'core/constants/constants.dart';
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

  sl.registerLazySingleton<Dio>(
    () => Dio(
      BaseOptions(
        baseUrl: AppConfig.apiBaseUrl,
        connectTimeout: AppConfig.defaultTimeout,
        receiveTimeout: AppConfig.defaultTimeout,
      ),
    ),
  );

  sl.registerLazySingleton<AppRouter>(AppRouter.new);
}
