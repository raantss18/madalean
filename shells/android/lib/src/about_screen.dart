/// « À propos / About » page of the Android shell: author, contacts,
/// licence and app version (same content as the web UI and desktop shell).
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:madalean_shell/src/strings.dart';
import 'package:url_launcher/url_launcher.dart';

/// Author details shown in every Madalean app.
abstract final class AboutInfo {
  static const String author = 'RANIRIAMANJAKA Antsa';
  static const String email = 'antsa.raniriamanjaka@univ-antananarivo.mg';
  static const String github = 'github.com/raantss18';
  static const String githubUrl = 'https://github.com/raantss18';
  static const String licence = 'Apache-2.0';
}

/// Opens [url] outside the app; returns false if nothing could handle it.
typedef LinkOpener = Future<bool> Function(Uri url);

Future<bool> _launchExternal(Uri url) async {
  try {
    return await launchUrl(url, mode: LaunchMode.externalApplication);
  } on Object {
    return false;
  }
}

class AboutScreen extends StatelessWidget {
  const AboutScreen({
    required this.strings,
    required this.version,
    this.openLink = _launchExternal,
    super.key,
  });
  final S strings;
  final String version;

  /// Injected in tests; defaults to url_launcher.
  final LinkOpener openLink;

  /// Pushes the About page on top of the current route.
  static Future<void> open(
    BuildContext context, {
    required S strings,
    required String version,
  }) => Navigator.of(context).push<void>(
    MaterialPageRoute(
      builder: (_) => AboutScreen(strings: strings, version: version),
    ),
  );

  Future<void> _open(BuildContext context, Uri url) async {
    final messenger = ScaffoldMessenger.of(context);
    if (!await openLink(url)) {
      messenger
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(strings.cannotOpenLink)));
    }
  }

  Future<void> _copy(BuildContext context, String text) async {
    final messenger = ScaffoldMessenger.of(context);
    await Clipboard.setData(ClipboardData(text: text));
    messenger
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(strings.copied)));
  }

  @override
  Widget build(BuildContext context) {
    final s = strings;
    final theme = Theme.of(context);
    final linkStyle = TextStyle(
      color: theme.colorScheme.primary,
      decoration: TextDecoration.underline,
    );
    Widget copyButton(String label, String value) => IconButton(
      tooltip: s.copy(label),
      icon: const Icon(Icons.copy_outlined),
      onPressed: () => unawaited(_copy(context, value)),
    );
    return Scaffold(
      appBar: AppBar(title: Text(s.about)),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: ListView(
              padding: const EdgeInsets.symmetric(vertical: 16),
              children: [
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Text('Madalean', style: theme.textTheme.headlineSmall),
                ),
                const SizedBox(height: 8),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Text(s.aboutWhat, style: theme.textTheme.bodyMedium),
                ),
                const SizedBox(height: 8),
                ListTile(
                  leading: const Icon(Icons.person_outline),
                  title: Text(s.author),
                  subtitle: const SelectableText(AboutInfo.author),
                ),
                ListTile(
                  key: const Key('about-email'),
                  leading: const Icon(Icons.mail_outline),
                  title: Text(s.email),
                  subtitle: Text(AboutInfo.email, style: linkStyle),
                  onTap: () => unawaited(
                    _open(
                      context,
                      Uri(scheme: 'mailto', path: AboutInfo.email),
                    ),
                  ),
                  trailing: copyButton(s.email, AboutInfo.email),
                ),
                ListTile(
                  key: const Key('about-github'),
                  leading: const Icon(Icons.code),
                  title: Text(s.github),
                  subtitle: Text(AboutInfo.github, style: linkStyle),
                  onTap: () =>
                      unawaited(_open(context, Uri.parse(AboutInfo.githubUrl))),
                  trailing: copyButton(s.github, AboutInfo.githubUrl),
                ),
                ListTile(
                  leading: const Icon(Icons.gavel_outlined),
                  title: Text(s.licence),
                  subtitle: const Text(AboutInfo.licence),
                ),
                ListTile(
                  leading: const Icon(Icons.info_outline),
                  title: Text(s.version),
                  subtitle: SelectableText(version.isEmpty ? '—' : version),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// App-bar button opening the About page (48 dp target via IconButton).
class AboutButton extends StatelessWidget {
  const AboutButton({required this.strings, required this.version, super.key});
  final S strings;
  final String version;

  @override
  Widget build(BuildContext context) => IconButton(
    key: const Key('about'),
    tooltip: strings.about,
    icon: const Icon(Icons.info_outline),
    onPressed: () => unawaited(
      AboutScreen.open(context, strings: strings, version: version),
    ),
  );
}
