import 'package:auto_route/auto_route.dart';
import 'package:flutter/material.dart';

/// Temporary authentication entry point that gets replaced with real flow later.
@RoutePage()
class AuthPlaceholderPage extends StatelessWidget {
  const AuthPlaceholderPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('ProHandyman')),
      body: Center(
        child: Text(
          'prohandyman.ru — автор Reznikov',
          style: Theme.of(context).textTheme.titleMedium,
        ),
      ),
    );
  }
}
