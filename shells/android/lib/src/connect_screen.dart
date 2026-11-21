import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:madalean_shell/src/address.dart';
import 'package:madalean_shell/src/controller.dart';
import 'package:madalean_shell/src/scan_screen.dart';
import 'package:madalean_shell/src/storage.dart';
import 'package:madalean_shell/src/strings.dart';
import 'package:madalean_shell/src/update.dart';
import 'package:madalean_shell/src/update_ui.dart';

class ConnectScreen extends StatefulWidget {
  const ConnectScreen({
    required this.controller,
    required this.state,
    this.updater,
    this.openTailscale,
    this.openAppSettings,
    super.key,
  });
  final ShellController controller;
  final ConnectState state;
  final Updater? updater;

  /// Native actions (null in tests).
  final Future<String> Function()? openTailscale;
  final Future<bool> Function()? openAppSettings;

  @override
  State<ConnectScreen> createState() => _ConnectScreenState();
}

class _ConnectScreenState extends State<ConnectScreen> {
  final _address = TextEditingController();
  final _code = TextEditingController();
  final _device = TextEditingController();
  int _rev = -1;

  @override
  void initState() {
    super.initState();
    _device.text = widget.controller.defaultDeviceName;
    _sync();
  }

  @override
  void didUpdateWidget(ConnectScreen old) {
    super.didUpdateWidget(old);
    _sync();
  }

  void _sync() {
    if (widget.state.revision != _rev) {
      _rev = widget.state.revision;
      _address.text = widget.state.address;
      _code.text = widget.state.code;
    }
  }

  @override
  void dispose() {
    _address.dispose();
    _code.dispose();
    _device.dispose();
    super.dispose();
  }

  Future<void> _paste() async {
    final data = await Clipboard.getData(Clipboard.kTextPlain);
    final text = data?.text ?? '';
    if (!widget.controller.handleLink(text) && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(widget.controller.s.noLinkInClipboard)),
      );
    }
  }

  /// Explains the camera once, then opens the in-app scanner; a scanned
  /// pairing link fills the form and pairs at once.
  Future<void> _scan() async {
    final c = widget.controller;
    final s = c.s;
    if (await c.prefs.getString('camera_explained') != '1') {
      if (!mounted) return;
      final ok = await showDialog<bool>(
        context: context,
        builder: (d) => AlertDialog(
          icon: const Icon(Icons.photo_camera_outlined),
          title: Text(s.cameraWhyTitle),
          content: Text(s.cameraWhy),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(d, false),
              child: Text(s.cancel),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(d, true),
              child: Text(s.continueLabel),
            ),
          ],
        ),
      );
      if (!(ok ?? false)) return;
      await c.prefs.setString('camera_explained', '1');
    }
    if (!mounted) return;
    final raw = await Navigator.of(context).push<String>(
      MaterialPageRoute(
        builder: (_) =>
            ScanScreen(strings: c.s, openAppSettings: widget.openAppSettings),
      ),
    );
    if (raw == null || !mounted) return;
    await c.scanned(raw, deviceName: _device.text);
  }

  void _submit() {
    FocusScope.of(context).unfocus();
    unawaited(
      widget.controller.pair(
        address: _address.text,
        code: _code.text,
        deviceName: _device.text,
      ),
    );
  }

  Future<void> _forget(SavedServer server, S s) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        content: Text(s.forgetConfirm(displayAddress(server.origin))),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: Text(s.cancel),
          ),
          TextButton(
            onPressed: () => Navigator.pop(c, true),
            child: Text(s.forget),
          ),
        ],
      ),
    );
    if (ok ?? false) await widget.controller.forgetServer(server);
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.controller;
    final s = c.s;
    final st = widget.state;
    final theme = Theme.of(context);
    final saved = c.servers.servers;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Madalean'),
        actions: [
          LanguageMenu(controller: c),
          if (widget.updater != null)
            IconButton(
              tooltip: s.settings,
              icon: const Icon(Icons.settings_outlined),
              onPressed: () =>
                  unawaited(showUpdateSettings(context, widget.updater!, s)),
            ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Text(s.connectTitle, style: theme.textTheme.headlineSmall),
                const SizedBox(height: 8),
                Text(s.connectIntro, style: theme.textTheme.bodyMedium),
                if (st.message != null) ...[
                  const SizedBox(height: 16),
                  Semantics(
                    liveRegion: true,
                    child: Card(
                      color: theme.colorScheme.errorContainer,
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              st.message!(s),
                              style: TextStyle(
                                color: theme.colorScheme.onErrorContainer,
                              ),
                            ),
                            if (st.tailscale &&
                                widget.openTailscale != null) ...[
                              const SizedBox(height: 8),
                              FilledButton.icon(
                                icon: const Icon(Icons.vpn_lock_outlined),
                                onPressed: () =>
                                    unawaited(widget.openTailscale!()),
                                label: Text(s.openTailscale),
                              ),
                            ],
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
                const SizedBox(height: 20),
                FilledButton.icon(
                  key: const Key('scan'),
                  onPressed: st.busy ? null : () => unawaited(_scan()),
                  icon: const Icon(Icons.qr_code_scanner),
                  label: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    child: Text(s.scanQr, style: const TextStyle(fontSize: 18)),
                  ),
                ),
                const SizedBox(height: 8),
                Text(s.scanIntro, style: theme.textTheme.bodySmall),
                if (saved.isNotEmpty) ...[
                  const SizedBox(height: 24),
                  Text(s.savedServers, style: theme.textTheme.titleMedium),
                  const SizedBox(height: 8),
                  for (final server in saved)
                    Card(
                      child: ListTile(
                        title: Text(displayAddress(server.origin)),
                        subtitle: server.hostName.isEmpty
                            ? null
                            : Text(server.hostName),
                        onTap: st.busy ? null : () => c.openServer(server),
                        trailing: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            IconButton(
                              tooltip: s.forget,
                              icon: const Icon(Icons.delete_outline),
                              onPressed: st.busy
                                  ? null
                                  : () => _forget(server, s),
                            ),
                            FilledButton.tonal(
                              onPressed: st.busy
                                  ? null
                                  : () => c.openServer(server),
                              child: Text(s.open),
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
                const SizedBox(height: 24),
                Text(s.orManual, style: theme.textTheme.titleMedium),
                const SizedBox(height: 12),
                TextField(
                  controller: _address,
                  enabled: !st.busy,
                  keyboardType: TextInputType.url,
                  autocorrect: false,
                  textInputAction: TextInputAction.next,
                  decoration: InputDecoration(
                    labelText: s.addressLabel,
                    hintText: s.addressHint,
                    helperText: s.addressHelp,
                    helperMaxLines: 3,
                    suffixIcon: IconButton(
                      tooltip: s.pasteLink,
                      icon: const Icon(Icons.content_paste),
                      onPressed: st.busy ? null : _paste,
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: _code,
                  enabled: !st.busy,
                  keyboardType: TextInputType.number,
                  maxLength: 6,
                  autofillHints: const [AutofillHints.oneTimeCode],
                  inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                  textInputAction: TextInputAction.next,
                  style: const TextStyle(letterSpacing: 4, fontSize: 20),
                  decoration: InputDecoration(
                    labelText: s.codeLabel,
                    helperText: s.codeHelp,
                    helperMaxLines: 3,
                  ),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _device,
                  enabled: !st.busy,
                  maxLength: 64,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _submit(),
                  decoration: InputDecoration(labelText: s.deviceLabel),
                ),
                const SizedBox(height: 16),
                FilledButton.tonal(
                  onPressed: st.busy ? null : _submit,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    child: st.busy
                        ? Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              const SizedBox.square(
                                dimension: 18,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              ),
                              const SizedBox(width: 12),
                              Text(s.connecting),
                            ],
                          )
                        : Text(s.pair),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Language selector: shows the current language, menu with both.
class LanguageMenu extends StatelessWidget {
  const LanguageMenu({required this.controller, super.key});
  final ShellController controller;

  static const Map<Lang, String> _names = {
    Lang.fr: 'Français',
    Lang.en: 'English',
  };

  @override
  Widget build(BuildContext context) {
    final c = controller;
    return PopupMenuButton<Lang>(
      tooltip: c.s.language,
      initialValue: c.lang,
      onSelected: (l) => unawaited(c.setLang(l)),
      itemBuilder: (_) => [
        for (final l in Lang.values)
          CheckedPopupMenuItem(
            value: l,
            checked: l == c.lang,
            child: Text(_names[l]!),
          ),
      ],
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.language, size: 20),
            const SizedBox(width: 6),
            Text(_names[c.lang]!),
          ],
        ),
      ),
    );
  }
}

class UnreachableScreen extends StatelessWidget {
  const UnreachableScreen({
    required this.controller,
    required this.state,
    this.openTailscale,
    super.key,
  });
  final ShellController controller;
  final UnreachableState state;
  final Future<String> Function()? openTailscale;

  @override
  Widget build(BuildContext context) {
    final s = controller.s;
    final theme = Theme.of(context);
    final known = state.tailscale || state.net != null;
    return Scaffold(
      appBar: AppBar(actions: [LanguageMenu(controller: controller)]),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: ListView(
              shrinkWrap: true,
              padding: const EdgeInsets.all(24),
              children: [
                Icon(
                  Icons.cloud_off_outlined,
                  size: 48,
                  color: theme.colorScheme.outline,
                ),
                const SizedBox(height: 16),
                Text(
                  s.unreachableTitle,
                  style: theme.textTheme.headlineSmall,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 12),
                Text(
                  known
                      ? netMessage(s, state.net, tailscale: state.tailscale)
                      : s.unreachableBody(displayAddress(state.server.origin)),
                  textAlign: TextAlign.center,
                ),
                if (state.detail != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    s.details(state.detail!),
                    style: theme.textTheme.bodySmall,
                    textAlign: TextAlign.center,
                  ),
                ],
                const SizedBox(height: 24),
                if (state.tailscale && openTailscale != null) ...[
                  FilledButton.icon(
                    icon: const Icon(Icons.vpn_lock_outlined),
                    onPressed: () => unawaited(openTailscale!()),
                    label: Text(s.openTailscale),
                  ),
                  const SizedBox(height: 8),
                  OutlinedButton(
                    onPressed: controller.retry,
                    child: Text(s.retry),
                  ),
                ] else
                  FilledButton(
                    onPressed: controller.retry,
                    child: Text(s.retry),
                  ),
                const SizedBox(height: 8),
                OutlinedButton(
                  onPressed: controller.changeServer,
                  child: Text(s.changeServer),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
