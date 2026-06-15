import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../connections/data/connection_store.dart';

class SessionsScreen extends ConsumerWidget {
  const SessionsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(selectedConnectionProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Sessions')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              profile == null
                  ? 'No instance selected'
                  : 'Selected instance: ${profile.name}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: profile == null ? null : () => context.go('/chat'),
              icon: const Icon(Icons.add_comment_outlined),
              label: const Text('New Session'),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: profile == null ? null : () => context.go('/chat'),
              icon: const Icon(Icons.history),
              label: const Text('Resume Session'),
            ),
            const SizedBox(height: 24),
            const Text(
              'Next step: replace this placeholder with mobile bootstrap data and a typed session list from the Hermes dashboard API. New Session and Resume stay separate so the app never silently crosses conversation boundaries.',
            ),
          ],
        ),
      ),
    );
  }
}
