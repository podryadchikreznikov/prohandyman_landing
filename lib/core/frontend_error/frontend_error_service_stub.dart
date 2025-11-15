import 'frontend_error_service_base.dart';

class FrontendErrorServiceStub implements FrontendErrorService {
  @override
  bool get isSupported => false;

  @override
  void start() {}

  @override
  void dispose() {}
}

FrontendErrorService createFrontendErrorService(_) =>
    FrontendErrorServiceStub();

