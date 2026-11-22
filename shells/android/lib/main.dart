import 'dart:async';
import 'dart:io';

import 'package:app_links/app_links.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';
import 'package:madalean_shell/src/address.dart';
import 'package:madalean_shell/src/api.dart';
import 'package:madalean_shell/src/connect_screen.dart';
import 'package:madalean_shell/src/controller.dart';
import 'package:madalean_shell/src/native.dart';
import 'package:madalean_shell/src/storage.dart';
import 'package:madalean_shell/src/theme.dart';
import 'package:madalean_shell/src/tunnel.dart';
import 'package:madalean_shell/src/update.dart';
import 'package:madalean_shell/src/update_ui.dart';
import 'package:madalean_shell/src/web_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final native = NativeBridge();
  // Tailnet-IP fallback (MagicDNS not resolving): CONNECT proxy on
  // 127.0.0.1 used by the Dart client and, through ProxyController, by the
  // web view. TLS stays end to end and is checked for the tailnet name.
  final tunnel = TunnelProxy(webView: _webViewProxy);
  final httpClient = HttpClient()
    ..findProxy = tunnel.findProxy
    ..connectionTimeout = const Duration(seconds: 5);
  final controller = ShellController(
    api: MadaleanApi(IOClient(httpClient)),
    tokens: SecureTokenStore(),
    prefs: SharedPrefs(),
    defaultDeviceName: await native.deviceName(),
    // Release builds: HTTPS, or plain HTTP to a private LAN address (the
    // host's LAN listener); loopback http only in debug builds.
    allowCleartext: kDebugMode,
    tunnels: tunnel,
  );
  final version = await native.appVersion();
  // Signed updates: fixed HTTPS channel; debug builds may point to a test
  // channel (--dart-define=MADALEAN_UPDATE_CHANNEL=…, see docs/SHELLS.md).
  final updater = Updater(
    client: http.Client(),
    platform: native,
    prefs: SharedPrefs(),
    channelUrl: Uri.parse(
      kDebugMode && debugChannelOverride.isNotEmpty
          ? debugChannelOverride
          : stableChannelUrl,
    ),
    publicKeyB64: buildPublicKey,
  );
  await updater.init();
  final links = AppLinks();
  String? initial;
  try {
    initial = await links.getInitialLinkString();
  } on Object {
    initial = null;
  }
  runApp(
    MadaleanApp(
      controller: controller,
      native: native,
      version: version,
      updater: updater,
    ),
  );
  unawaited(updater.maybeCheck());
  unawaited(controller.init(initialLink: initial));
  links.stringLinkStream.listen((l) {
    if (l != initial) controller.handleLink(l);
    initial = null;
  });
}

/// Points the web view at the tunnel proxy (port) or back to direct (null).
Future<bool> _webViewProxy(int? port) async {
  try {
    final proxy = ProxyController.instance();
    if (port == null) {
      await proxy.clearProxyOverride();
      return true;
    }
    if (!await WebViewFeature.isFeatureSupported(
      WebViewFeature.PROXY_OVERRIDE,
    )) {
      return false;
    }
    await proxy.setProxyOverride(
      settings: ProxySettings(
        proxyRules: [ProxyRule(url: 'http://127.0.0.1:$port')],
        bypassRules: [],
      ),
    );
    return true;
  } on Object {
    return false;
  }
}

class MadaleanApp extends StatefulWidget {
  const MadaleanApp({
    required this.controller,
    required this.native,
    required this.version,
    required this.updater,
    super.key,
  });
  final ShellController controller;
  final NativeBridge native;
  final String version;
  final Updater updater;

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
      unawaited(widget.updater.maybeCheck());
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
        supportedLocales: const [Locale('fr'), Locale('en')],
        localizationsDelegates: GlobalMaterialLocalizations.delegates,
        builder: (context, child) => UpdateBanner(
          updater: widget.updater,
          strings: () => c.s,
          child: child ?? const SizedBox.shrink(),
        ),
        home: switch (c.state) {
          LoadingState() => const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          ),
          final ConnectState st => ConnectScreen(
            controller: c,
            state: st,
            updater: widget.updater,
            openTailscale: widget.native.openTailscale,
            openAppSettings: widget.native.openAppSettings,
            version: widget.version,
          ),
          final UnreachableState st => UnreachableScreen(
            controller: c,
            state: st,
            openTailscale: widget.native.openTailscale,
            version: widget.version,
          ),
          final WebState st => WebScreen(
            key: ValueKey(originKey(st.origin)),
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
