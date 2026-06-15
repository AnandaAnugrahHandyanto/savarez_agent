import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../hermes_api/connection_profile.dart';
import '../data/connection_store.dart';

class AddConnectionScreen extends ConsumerStatefulWidget {
  const AddConnectionScreen({super.key});

  @override
  ConsumerState<AddConnectionScreen> createState() =>
      _AddConnectionScreenState();
}

class _AddConnectionScreenState extends ConsumerState<AddConnectionScreen> {
  final _formKey = GlobalKey<FormState>();
  final _name = TextEditingController();
  final _url = TextEditingController(text: 'http://127.0.0.1:9119');
  final _token = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _url.dispose();
    _token.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Add Connection')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            TextFormField(
              controller: _name,
              decoration: const InputDecoration(
                labelText: 'Name',
                prefixIcon: Icon(Icons.badge_outlined),
              ),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _url,
              decoration: const InputDecoration(
                labelText: 'Dashboard URL',
                prefixIcon: Icon(Icons.link),
              ),
              keyboardType: TextInputType.url,
              validator: (value) =>
                  value == null || value.trim().isEmpty ? 'URL required' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _token,
              decoration: const InputDecoration(
                labelText: 'Session token',
                prefixIcon: Icon(Icons.key_outlined),
              ),
              obscureText: true,
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: TextStyle(color: ColorScheme.of(context).error)),
            ],
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: _save,
              icon: const Icon(Icons.save_outlined),
              label: const Text('Save connection'),
            ),
          ],
        ),
      ),
    );
  }

  void _save() {
    if (!_formKey.currentState!.validate()) {
      return;
    }
    try {
      final profile = ConnectionProfile.fromForm(
        name: _name.text,
        baseUrl: _url.text,
        token: _token.text,
      );
      ref.read(connectionStoreProvider.notifier).add(profile);
      ref.read(selectedConnectionIdProvider.notifier).state = profile.id;
      context.go('/');
    } on FormatException catch (error) {
      setState(() => _error = error.message);
    }
  }
}
