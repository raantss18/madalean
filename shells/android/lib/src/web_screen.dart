import 'dart:async';
import 'dart:collection';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_inappwebview/flutter_inappwebview.dart';
import 'package:madalean_shell/src/address.dart';
import 'package:madalean_shell/src/api.dart';
import 'package:madalean_shell/src/controller.dart';
import 'package:madalean_shell/src/native.dart';
import 'package:url_launcher/url_launcher.dart';

/// Hosts the server's web UI. Only the server's origin is shown in the web
/// view; everything else goes to the system browser.
class WebScreen extends StatefulWidget {
  const WebScreen({
    required this.controller,
    required this.state,
    required this.native,
    required this.version,
    super.key,
  });
  final ShellController controller;
  final WebState state;
  final NativeBridge native;
  final String version;

  @override
  State<WebScreen> createState() => _WebScreenState();
}

/// Network-level failures that mean "server unreachable".
final Set<WebResourceErrorType> _networkErrors = {
  WebResourceErrorType.HOST_LOOKUP,
  WebResourceErrorType.CANNOT_CONNECT_TO_HOST,
  WebResourceErrorType.TIMEOUT,
  WebResourceErrorType.FAILED_SSL_HANDSHAKE,
  WebResourceErrorType.CONNECTION_ABORTED,
  WebResourceErrorType.NETWORK_CONNECTION_LOST,
  WebResourceErrorType.NOT_CONNECTED_TO_INTERNET,
};

class _WebScreenState extends State<WebScreen> {
  InAppWebViewController? _web;
  int _loaded = 0;
  double _progress = 0;

  Uri get _origin => widget.state.server.origin;

  bool _sameOrigin(Uri? u) =>
      u != null &&
      u.scheme == _origin.scheme &&
      u.host == _origin.host &&
      (u.hasPort ? u.port : (u.scheme == 'https' ? 443 : 80)) == _origin.port;

  @override
  void didUpdateWidget(WebScreen old) {
    super.didUpdateWidget(old);
    if (widget.state.n != _loaded && _web != null) {
      _loaded = widget.state.n;
      unawaited(
        _web!.loadUrl(
          urlRequest: URLRequest(url: WebUri.uri(widget.state.url)),
        ),
      );
    }
  }

  String get _bridgeScript {
    final v = jsonEncode(widget.version);
    return '''
(function () {
  if (window.madaleanShell) return;
  function call(a, b) {
    return window.flutter_inappwebview.callHandler('madaleanShell', a, b);
  }
  Object.defineProperty(window, 'madaleanShell', {
    value: Object.freeze({
      kind: 'android',
      version: $v,
      changeServer: function () { return call('changeServer'); },
      openExternal: function (url) { return call('openExternal', String(url)); }
    }),
    writable: false, configurable: false
  });
})();
''';
  }

  Future<void> _external(Uri url) async {
    if (url.scheme == 'http' ||
        url.scheme == 'https' ||
        url.scheme == 'mailto') {
      await launchUrl(url, mode: LaunchMode.externalApplication);
    }
  }

  Future<NavigationActionPolicy> _onNavigate(NavigationAction action) async {
    final url = action.request.url;
    if (url == null) return NavigationActionPolicy.CANCEL;
    if (_sameOrigin(url)) {
      if (action.isForMainFrame && url.path.startsWith('/pair')) {
        // 401 in the web UI, expired cookie or bad ticket: new session
        // if the token is still valid, else back to the pairing screen.
        await widget.controller.reauth();
        return NavigationActionPolicy.CANCEL;
      }
      return NavigationActionPolicy.ALLOW;
    }
    if (url.scheme == 'about' || url.scheme == 'data' || url.scheme == 'blob') {
      return action.isForMainFrame
          ? NavigationActionPolicy.CANCEL
          : NavigationActionPolicy.ALLOW;
    }
    if (action.isForMainFrame) await _external(url);
    return NavigationActionPolicy.CANCEL;
  }

  void _snack(String text, {SnackBarAction? action}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(text),
          action: action,
          persist: false,
          duration: const Duration(seconds: 8),
        ),
      );
  }

  Future<void> _save(String name, String mime, Uint8List bytes) async {
    final s = widget.controller.s;
    try {
      final uri = await widget.native.saveDownload(name, mime, bytes);
      if (uri == null) return; // user cancelled the picker (Android 8–9)
      _snack(
        s.downloaded(name),
        action: SnackBarAction(
          label: s.open,
          onPressed: () => widget.native.openUri(uri, mime),
        ),
      );
    } on PlatformException {
      _snack(s.downloadFailed);
    }
  }

  Future<void> _download(DownloadStartRequest req) async {
    final s = widget.controller.s;
    final url = req.url;
    if (url.scheme == 'data') {
      final data = UriData.fromUri(url);
      await _save(
        sanitiseFilename(req.suggestedFilename ?? '') ?? 'madalean-export',
        data.mimeType,
        data.contentAsBytes(),
      );
      return;
    }
    if (url.scheme == 'blob') {
      // Best effort: read the blob in the page, send it back as a data URL.
      final name = jsonEncode(req.suggestedFilename ?? 'madalean-export');
      await _web?.evaluateJavascript(
        source:
            '''
fetch(${jsonEncode(url.toString())}).then(r => r.blob()).then(b => {
  const f = new FileReader();
  f.onload = () => window.flutter_inappwebview.callHandler('madaleanShell', 'blob', f.result, $name);
  f.readAsDataURL(b);
}).catch(() => window.flutter_inappwebview.callHandler('madaleanShell', 'blob', '', $name));
''',
      );
      return;
    }
    if (!_sameOrigin(url)) {
      await _external(url);
      return;
    }
    _snack(s.downloading);
    try {
      // Native re-download with the Bearer token (the cookie is HttpOnly).
      final token = await widget.controller.currentToken();
      final r = await widget.controller.api.download(url, token);
      if (r.statusCode != 200) throw const ApiException(ApiFailure.protocol);
      final name =
          filenameFromDisposition(r.headers['content-disposition']) ??
          sanitiseFilename(req.suggestedFilename ?? '') ??
          sanitiseFilename(
            url.pathSegments.isEmpty ? '' : url.pathSegments.last,
          ) ??
          'madalean-export';
      final mime =
          (r.headers['content-type'] ??
                  req.mimeType ??
                  'application/octet-stream')
              .split(';')
              .first
              .trim();
      await _save(name, mime, r.bodyBytes);
    } on ApiException {
      _snack(s.downloadFailed);
    }
  }

  Future<Object?> _bridge(List<dynamic> args) async {
    final action = args.isEmpty ? '' : '${args[0]}';
    switch (action) {
      case 'changeServer':
        widget.controller.changeServer();
      case 'openExternal':
        final u = Uri.tryParse(args.length > 1 ? '${args[1]}' : '');
        if (u != null) await _external(u);
      case 'blob':
        final dataUrl = args.length > 1 ? '${args[1]}' : '';
        final name = sanitiseFilename(args.length > 2 ? '${args[2]}' : '');
        final u = Uri.tryParse(dataUrl);
        if (u == null || u.scheme != 'data') {
          _snack(widget.controller.s.downloadFailed);
        } else {
          final data = UriData.fromUri(u);
          await _save(
            name ?? 'madalean-export',
            data.mimeType,
            data.contentAsBytes(),
          );
        }
    }
    return null;
  }

  Future<void> _back() async {
    final web = _web;
    if (web != null && await web.canGoBack()) {
      await web.goBack();
      return;
    }
    if (!mounted) return;
    final s = widget.controller.s;
    final choice = await showDialog<String>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text(s.exitTitle),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, 'server'),
            child: Text(s.changeServer),
          ),
          TextButton(onPressed: () => Navigator.pop(c), child: Text(s.cancel)),
          FilledButton(
            onPressed: () => Navigator.pop(c, 'quit'),
            child: Text(s.quit),
          ),
        ],
      ),
    );
    if (choice == 'server') widget.controller.changeServer();
    if (choice == 'quit') await SystemNavigator.pop();
  }

  @override
  Widget build(BuildContext context) {
    final origin = originKey(_origin);
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) unawaited(_back());
      },
      child: Scaffold(
        body: SafeArea(
          child: Stack(
            children: [
              InAppWebView(
                initialUrlRequest: URLRequest(
                  url: WebUri.uri(widget.state.url),
                ),
                initialUserScripts: UnmodifiableListView([
                  UserScript(
                    source: _bridgeScript,
                    injectionTime: UserScriptInjectionTime.AT_DOCUMENT_START,
                    allowedOriginRules: {origin},
                  ),
                ]),
                initialSettings: InAppWebViewSettings(
                  useShouldOverrideUrlLoading: true,
                  useOnDownloadStart: true,
                  supportMultipleWindows: true,
                  javaScriptCanOpenWindowsAutomatically: true,
                  mixedContentMode: MixedContentMode.MIXED_CONTENT_NEVER_ALLOW,
                  allowFileAccess: false,
                  allowContentAccess: false,
                  thirdPartyCookiesEnabled: false,
                  safeBrowsingEnabled: false,
                  geolocationEnabled: false,
                  applicationNameForUserAgent:
                      'MadaleanShell/${widget.version} (android)',
                ),
                onWebViewCreated: (c) {
                  _web = c;
                  _loaded = widget.state.n;
                  c.addJavaScriptHandler(
                    handlerName: 'madaleanShell',
                    callback: _bridge,
                  );
                },
                shouldOverrideUrlLoading: (c, action) => _onNavigate(action),
                onCreateWindow: (c, action) async {
                  final url = action.request.url;
                  if (url != null) {
                    if (_sameOrigin(url)) {
                      await c.loadUrl(urlRequest: URLRequest(url: url));
                    } else {
                      await _external(url);
                    }
                  }
                  return false;
                },
                onDownloadStartRequest: (c, req) => _download(req),
                onReceivedError: (c, request, error) {
                  if ((request.isForMainFrame ?? false) &&
                      _networkErrors.contains(error.type)) {
                    widget.controller.webLoadFailed(error.description);
                  }
                },
                // Camera, microphone, MIDI…: always denied (default action).
                onPermissionRequest: (c, request) async =>
                    PermissionResponse(resources: request.resources),
                onProgressChanged: (c, p) =>
                    setState(() => _progress = p / 100),
              ),
              if (_progress < 1)
                LinearProgressIndicator(
                  value: _progress == 0 ? null : _progress,
                ),
            ],
          ),
        ),
      ),
    );
  }
}
