import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../connections/data/connection_store.dart';

class ChatScreen extends ConsumerWidget {
  const ChatScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final profile = ref.watch(selectedConnectionProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('Chat')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              profile == null ? 'No instance selected' : profile.name,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 16),
            const Text(
              'This prototype stops before implementing the transcript. The production chat screen should connect through /api/ws, wait for gateway.ready, then bind a single explicit session id before sending prompts.',
            ),
            const SizedBox(height: 16),
            const Text(
              'Required next contracts: create session, resume session, stream messages, approvals, tool activity, and reconnect behavior.',
            ),
          ],
        ),
      ),
    );
  }
}
