import '../../domain/entities/callback_request_payload.dart';

class CallbackRequestModel extends CallbackRequestPayload {
  const CallbackRequestModel({
    super.phoneNumber,
    super.email,
    super.userName,
    super.comment,
  });

  factory CallbackRequestModel.fromEntity(CallbackRequestPayload entity) {
    return CallbackRequestModel(
      phoneNumber: entity.phoneNumber?.trim(),
      email: entity.email?.trim(),
      userName: entity.userName?.trim(),
      comment: entity.comment?.trim(),
    );
  }

  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{};
    if (phoneNumber != null && phoneNumber!.isNotEmpty) {
      map['phone_number'] = phoneNumber;
    }
    if (email != null && email!.isNotEmpty) {
      map['email'] = email;
    }
    if (userName != null && userName!.isNotEmpty) {
      map['user_name'] = userName;
    }
    if (comment != null && comment!.isNotEmpty) {
      map['comment'] = comment;
    }
    return map;
  }
}
