import 'dart:async';
import 'dart:ui';

import 'package:app_links/app_links.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:madalean_shell/src/api.dart';
import 'package:madalean_shell/src/connect_screen.dart';
import 'package:madalean_shell/src/controller.dart';
import 'package:madalean_shell/src/native.dart';
import 'package:madalean_shell/src/storage.dart';
import 'package:madalean_shell/src/strings.dart';
import 'package:madalean_shell/src/theme.dart';
import 'package:madalean_shell/src/web_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final native = NativeBridge();
  final lang = PlatformDispatcher.instance.locale.languageCode == 'en'
      ? Lang.en
      : Lang.fr;
  final controller = ShellController(
    api: MadaleanApi(http.Client()),
    tokens: SecureTokenStore(),
    prefs: SharedPrefs(),
    defaultDeviceName: await native.deviceName(),
    // Release builds: HTTPS only (also enforced by network_security_config).
    allowCleartext: kDebugMode,
    systemLang: lang,
  );
  final version = await native.appVersion();
  final links = AppLinks();
  String? initial;
  try {
    initial = await links.getInitialLinkString();
  } on Object {
    initial = null;
  }
  runApp(MadaleanApp(controller: controller, native: native, version: version));
  unawaited(controller.init(initialLink: initial));
  links.stringLinkStream.listen((l) {
    if (l != initial) controller.handleLink(l);
    initial = null;
  });
}

class MadaleanApp extends StatefulWidget {
  const MadaleanApp({
    required this.controller,
    required this.native,
    required this.version,
    super.key,
  });
  final ShellController controller;
  final NativeBridge native;
  final String version;

  @override
  State<MadaleanApp> createState() => _MadaleanAppState();
}

class _MadaleanAppState extends State<MadaleanApp> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused) widget.controller.paused();
    if (state == AppLifecycleState.resumed) {
      unawaited(widget.controller.resumed());
    }
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.controller;
    return ListenableBuilder(
      listenable: c,
      builder: (context, _) => MaterialApp(
        title: 'Madalean',
        debugShowCheckedModeBanner: false,
        theme: shellTheme(Brightness.light),
        darkTheme: shellTheme(Brightness.dark),
        locale: Locale(c.lang.name),
        home: switch (c.state) {
          LoadingState() => const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          ),
          final ConnectState st => ConnectScreen(controller: c, state: st),
          final UnreachableState st => UnreachableScreen(
            controller: c,
            state: st,
          ),
          final WebState st => WebScreen(
            key: ValueKey(st.server.key),
            controller: c,
            state: st,
            native: widget.native,
            version: widget.version,
          ),
        },
      ),
    );
  }
}
