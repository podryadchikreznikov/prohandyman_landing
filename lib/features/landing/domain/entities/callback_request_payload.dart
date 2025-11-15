import 'package:equatable/equatable.dart';

class CallbackRequestPayload extends Equatable {
  const CallbackRequestPayload({
    this.phoneNumber,
    this.email,
    this.userName,
    this.comment,
  });

  final String? phoneNumber;
  final String? email;
  final String? userName;
  final String? comment;

  bool get hasContact =>
      (phoneNumber?.trim().isNotEmpty ?? false) ||
      (email?.trim().isNotEmpty ?? false);

  CallbackRequestPayload copyWith({
    String? phoneNumber,
    String? email,
    String? userName,
    String? comment,
  }) {
    return CallbackRequestPayload(
      phoneNumber: phoneNumber ?? this.phoneNumber,
      email: email ?? this.email,
      userName: userName ?? this.userName,
      comment: comment ?? this.comment,
    );
  }

  @override
  List<Object?> get props => [
        phoneNumber?.trim(),
        email?.trim(),
        userName?.trim(),
        comment?.trim(),
      ];
}
