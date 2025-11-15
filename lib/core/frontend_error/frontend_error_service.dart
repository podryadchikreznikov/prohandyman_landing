import 'package:talker/talker.dart';

import 'frontend_error_service_base.dart';
import 'frontend_error_service_stub.dart'
    if (dart.library.html) 'frontend_error_service_web.dart' as impl;

export 'frontend_error_service_base.dart';

FrontendErrorService createFrontendErrorService(Talker talker) =>
    impl.createFrontendErrorService(talker);

