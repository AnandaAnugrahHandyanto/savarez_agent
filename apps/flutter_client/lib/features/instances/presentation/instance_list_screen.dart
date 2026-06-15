import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../hermes_api/connection_profile.dart';
import '../../connections/data/connection_store.dart';
import '../data/instance_probe.dart';

class InstanceListScreen extends ConsumerWidget {
  const InstanceListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final connections = ref.watch(connectionStoreProvider);
    final selected = ref.watch(selectedConnectionProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Hermes Instances'),
        actions: [
          IconButton(
            tooltip: 'Add connection',
            onPressed: () => context.go('/connections/new'),
            icon: const Icon(Icons.add_link),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          for (final profile in connections)
            Card(
              child: ListTile(
                selected: selected?.id == profile.id,
                leading: const Icon(Icons.dns_outlined),
                title: Text(profile.name),
                subtitle: Text(profile.baseUrl.toString()),
                trailing: FilledButton.icon(
                  onPressed: () {
                    ref.read(selectedConnectionIdProvider.notifier).state =
                        profile.id;
                    context.go('/sessions');
                  },
                  icon: const Icon(Icons.login),
                  label: const Text('Use'),
                ),
                onTap: () {
                  ref.read(selectedConnectionIdProvider.notifier).state =
                      profile.id;
                },
              ),
            ),
          const SizedBox(height: 12),
          if (selected != null) _ProbePanel(profile: selected),
        ],
      ),
    );
  }
}

class _ProbePanel extends ConsumerWidget {
  const _ProbePanel({required this.profile});

  final ConnectionProfile profile;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final probe = ref.watch(instanceProbeProvider(profile));
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: probe.when(
          loading: () => const Row(
            children: [
              SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
              SizedBox(width: 12),
              Text('Testing status and mobile bootstrap...'),
            ],
          ),
          error: (error, stackTrace) => _StatusText(
            icon: Icons.error_outline,
            title: 'Status check failed',
            body: '$error',
          ),
          data: (result) => Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _StatusText(
                icon: Icons.check_circle_outline,
                title: 'Status reachable',
                body:
                    'Gateway: ${result.status.gatewayState ?? 'unknown'} | Active sessions: ${result.status.activeSessions ?? 0}',
              ),
              const SizedBox(height: 12),
              _StatusText(
                icon: result.bootstrap == null
                    ? Icons.info_outline
                    : Icons.mobile_friendly,
                title: result.bootstrap == null
                    ? 'Bootstrap endpoint pending'
                    : 'Bootstrap reachable',
                body: result.bootstrap == null
                    ? 'GET /api/mobile/bootstrap is not available yet or requires backend work.'
                    : 'Mobile bootstrap returned ${result.bootstrap!.raw.length} top-level fields.',
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusText extends StatelessWidget {
  const _StatusText({
    required this.icon,
    required this.title,
    required this.body,
  });

  final IconData icon;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 4),
              Text(body),
            ],
          ),
        ),
      ],
    );
  }
}
