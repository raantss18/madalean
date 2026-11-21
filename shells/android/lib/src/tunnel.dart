/// Reaching `https://<name>.ts.net` through its tailnet IP when MagicDNS does
/// not resolve the name (Android "Private DNS", DNS of another VPN…).
///
/// A tiny CONNECT proxy on 127.0.0.1 forwards `CONNECT <name>:443` — and
/// nothing else — to `<tailnet IP>:443`. TLS stays end to end between the
/// app (Dart HTTP client, web view) and Madalean, and the certificate is
/// still checked against the name: only the DNS lookup is skipped.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

/// What the controller needs (fake in tests).
abstract class Tunnels {
  /// Routes `host:port` to `ip:port` from now on. False when the IP does not
  /// answer or the web view cannot use a proxy.
  Future<bool> activate(String host, int port, String ip);

  /// Back to direct connections.
  Future<void> deactivate();
}

class NoTunnels implements Tunnels {
  const NoTunnels();
  @override
  Future<bool> activate(String host, int port, String ip) async => false;
  @override
  Future<void> deactivate() async {}
}

/// Hook to point the web view at the proxy (ProxyController, Android).
typedef WebViewProxyHook = Future<bool> Function(int? port);

class TunnelProxy implements Tunnels {
  TunnelProxy({
    this.webView,
    this.probeTimeout = const Duration(seconds: 2),
    this.connectTimeout = const Duration(seconds: 5),
  });

  /// Called with the proxy port on activation, null on deactivation.
  final WebViewProxyHook? webView;
  final Duration probeTimeout;
  final Duration connectTimeout;

  ServerSocket? _server;
  String? _target; // "host:port", lower case
  String? _ip;
  bool _webViewOn = false;

  int? get port => _server?.port;

  /// For `HttpClient.findProxy`.
  String findProxy(Uri uri) {
    final p = _server?.port;
    if (p != null && _target == '${uri.host.toLowerCase()}:${uri.port}') {
      return 'PROXY 127.0.0.1:$p';
    }
    return 'DIRECT';
  }

  @override
  Future<bool> activate(String host, int port, String ip) async {
    // Cheap check first: does the tailnet IP answer at all?
    try {
      final s = await Socket.connect(ip, port, timeout: probeTimeout);
      s.destroy();
    } on Object {
      return false;
    }
    _server ??= await ServerSocket.bind(InternetAddress.loopbackIPv4, 0)
      ..listen(_handle);
    _target = '${host.toLowerCase()}:$port';
    _ip = ip;
    final hook = webView;
    if (hook != null) {
      _webViewOn = await hook(_server!.port);
      if (!_webViewOn) {
        _target = null;
        _ip = null;
        return false;
      }
    }
    return true;
  }

  @override
  Future<void> deactivate() async {
    _target = null;
    _ip = null;
    final hook = webView;
    if (hook != null && _webViewOn) {
      _webViewOn = false;
      await hook(null);
    }
  }

  Future<void> close() async {
    await deactivate();
    await _server?.close();
    _server = null;
  }

  void _handle(Socket client) {
    final head = BytesBuilder(copy: false);
    Socket? upstream;
    var connecting = false;
    // Ends with the client socket (destroy / cancelOnError).
    // ignore: cancel_subscriptions
    late final StreamSubscription<Uint8List> sub;
    void fail(String status) {
      try {
        client.add(
          ascii.encode('HTTP/1.1 $status\r\nConnection: close\r\n\r\n'),
        );
      } on Object {
        // closed already
      }
      upstream?.destroy();
      client.destroy();
    }

    sub = client.listen(
      (data) {
        final up = upstream;
        if (up != null) {
          up.add(data);
          return;
        }
        if (connecting) return;
        head.add(data);
        final bytes = head.toBytes();
        final end = _headerEnd(bytes);
        if (end < 0) {
          if (bytes.length > 8192) fail('431 Request Header Fields Too Large');
          return;
        }
        final line = latin1.decode(bytes.sublist(0, end)).split('\r\n').first;
        final parts = line.split(' ');
        final target = _target;
        final ip = _ip;
        if (parts.length != 3 ||
            parts[0] != 'CONNECT' ||
            target == null ||
            ip == null ||
            parts[1].toLowerCase() != target) {
          fail('403 Forbidden');
          return;
        }
        final rest = bytes.sublist(end + 4);
        final port = int.parse(target.substring(target.lastIndexOf(':') + 1));
        connecting = true;
        sub.pause();
        unawaited(
          Socket.connect(ip, port, timeout: connectTimeout).then(
            (s) {
              upstream = s;
              client.add(
                ascii.encode('HTTP/1.1 200 Connection Established\r\n\r\n'),
              );
              if (rest.isNotEmpty) s.add(rest);
              s.listen(
                client.add,
                onDone: client.destroy,
                onError: (Object _) => client.destroy(),
                cancelOnError: true,
              );
              sub.resume();
            },
            onError: (Object _) {
              fail('502 Bad Gateway');
            },
          ),
        );
      },
      onDone: () => upstream?.destroy(),
      onError: (Object _) => upstream?.destroy(),
      cancelOnError: true,
    );
  }

  static int _headerEnd(Uint8List b) {
    for (var i = 0; i + 3 < b.length; i++) {
      if (b[i] == 13 && b[i + 1] == 10 && b[i + 2] == 13 && b[i + 3] == 10) {
        return i;
      }
    }
    return -1;
  }
}
