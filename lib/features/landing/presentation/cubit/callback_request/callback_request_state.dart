import 'package:equatable/equatable.dart';

enum CallbackRequestStatus {
  idle,
  submitting,
  success,
  failure,
}

class CallbackRequestState extends Equatable {
  const CallbackRequestState({
    this.name = '',
    this.phone = '',
    this.email = '',
    this.comment = '',
    this.status = CallbackRequestStatus.idle,
    this.errorMessage,
  });

  final String name;
  final String phone;
  final String email;
  final String comment;
  final CallbackRequestStatus status;
  final String? errorMessage;

  bool get hasContact => phone.trim().isNotEmpty;

  bool get isBusy => status == CallbackRequestStatus.submitting;

  bool get canSubmit => hasContact && !isBusy;

  CallbackRequestState copyWith({
    String? name,
    String? phone,
    String? email,
    String? comment,
    CallbackRequestStatus? status,
    String? errorMessage,
    bool clearError = false,
  }) {
    return CallbackRequestState(
      name: name ?? this.name,
      phone: phone ?? this.phone,
      email: email ?? this.email,
      comment: comment ?? this.comment,
      status: status ?? this.status,
      errorMessage: clearError ? null : errorMessage ?? this.errorMessage,
    );
  }

  @override
  List<Object?> get props => [
        name,
        phone,
        email,
        comment,
        status,
        errorMessage,
      ];
}
