/// Update banner (non-intrusive bar at the bottom of every screen) and the
/// small settings sheet (« Mises à jour automatiques »,
/// « Vérifier maintenant »).
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:madalean_shell/src/strings.dart';
import 'package:madalean_shell/src/update.dart';

class UpdateBanner extends StatefulWidget {
  const UpdateBanner({
    required this.updater,
    required this.strings,
    required this.child,
    super.key,
  });
  final Updater updater;
  final S Function() strings;
  final Widget child;

  @override
  State<UpdateBanner> createState() => _UpdateBannerState();
}

class _UpdateBannerState extends State<UpdateBanner> {
  bool _needPermission = false;

  Future<void> _install() async {
    final ok = await widget.updater.install();
    if (mounted) setState(() => _needPermission = !ok);
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.updater,
      builder: (context, _) {
        final u = widget.updater;
        final st = u.status;
        final s = widget.strings();
        final show = u.bannerVisible && st is UpdateReady;
        return Column(
          children: [
            Expanded(child: widget.child),
            if (show)
              Material(
                color: Theme.of(context).colorScheme.secondaryContainer,
                child: SafeArea(
                  top: false,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(16, 8, 8, 8),
                    child: Row(
                      children: [
                        Icon(
                          Icons.system_update_outlined,
                          color: Theme.of(context)
                              .colorScheme
                              .onSecondaryContainer,
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Semantics(
                            liveRegion: true,
                            child: Text(
                              _needPermission
                                  ? s.allowInstall
                                  : (st.required
                                        ? s.updateRequired(st.version)
                                        : s.updateReady(st.version)),
                              style: TextStyle(
                                color: Theme.of(context)
                                    .colorScheme
                                    .onSecondaryContainer,
                              ),
                            ),
                          ),
                        ),
                        if (!st.required)
                          TextButton(
                            onPressed: u.dismiss,
                            child: Text(s.later),
                          ),
                        FilledButton(
                          onPressed: () => unawaited(_install()),
                          child: Text(s.install),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}

String updateStatusText(UpdateStatus st, S s) => switch (st) {
  UpdateIdle() => '',
  UpdateChecking() => s.checking,
  UpdateUpToDate(:final version) => s.upToDate(version),
  UpdateDownloading(:final version, :final received, :final total) =>
    s.downloadingUpdate(version, total == 0 ? 0 : (received * 100) ~/ total),
  UpdateReady(:final version) => s.updateReady(version),
  UpdateFailed(:final error) => s.updateError(error.name),
};

Future<void> showUpdateSettings(BuildContext context, Updater updater, S s) =>
    showModalBottomSheet<void>(
      context: context,
      showDragHandle: true,
      builder: (context) => ListenableBuilder(
        listenable: updater,
        builder: (context, _) {
          final text = updateStatusText(updater.status, s);
          final busy =
              updater.status is UpdateChecking ||
              updater.status is UpdateDownloading;
          return SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(8, 0, 8, 16),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  SwitchListTile(
                    title: Text(s.autoUpdates),
                    subtitle: Text(s.autoUpdatesHelp),
                    value: updater.automatic,
                    onChanged: (v) => unawaited(updater.setAutomatic(v)),
                  ),
                  if (text.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                      child: Semantics(liveRegion: true, child: Text(text)),
                    ),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16),
                    child: OutlinedButton(
                      onPressed: busy ? null : () => unawaited(updater.check()),
                      child: Text(s.checkNow),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
