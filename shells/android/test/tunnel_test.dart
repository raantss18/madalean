import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:madalean_shell/src/tunnel.dart';

/// Reads from [s] until [want] has been received.
Future<String> readUntil(
  Stream<List<int>> s,
  String want, {
  StringBuffer? into,
}) async {
  final b = into ?? StringBuffer();
  await for (final chunk in s) {
    b.write(latin1.decode(chunk));
    if (b.toString().contains(want)) break;
  }
  return b.toString();
}

void main() {
  test(
    'only CONNECT to the routed name is forwarded, bytes both ways',
    () async {
      final upstream = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
      upstream.listen((s) {
        s.listen((d) => s.add([...ascii.encode('echo:'), ...d]));
      });
      final hooks = <int?>[];
      final t = TunnelProxy(
        webView: (p) async {
          hooks.add(p);
          return true;
        },
      );
      const host = 'madalean.tail1.ts.net';
      expect(await t.activate(host, upstream.port, '127.0.0.1'), isTrue);
      expect(hooks, [t.port]);
      expect(
        t.findProxy(Uri.parse('https://$host:${upstream.port}/api/hello')),
        'PROXY 127.0.0.1:${t.port}',
      );
      expect(t.findProxy(Uri.parse('https://other.ts.net/')), 'DIRECT');

      // Allowed tunnel.
      final c = await Socket.connect('127.0.0.1', t.port!);
      final rx = c.asBroadcastStream();
      c.add(
        ascii.encode(
          'CONNECT $host:${upstream.port} HTTP/1.1\r\n'
          'Host: $host\r\n\r\nhello',
        ),
      );
      final buf = StringBuffer();
      final got = await readUntil(
        rx,
        'echo:hello',
        into: buf,
      ).timeout(const Duration(seconds: 5));
      expect(got, startsWith('HTTP/1.1 200'));
      c.destroy();

      // Any other target is refused.
      final d = await Socket.connect('127.0.0.1', t.port!);
      d.add(ascii.encode('CONNECT evil.example:443 HTTP/1.1\r\n\r\n'));
      expect(
        await readUntil(d, '\r\n\r\n').timeout(const Duration(seconds: 5)),
        startsWith('HTTP/1.1 403'),
      );
      final e = await Socket.connect('127.0.0.1', t.port!);
      e.add(ascii.encode('GET http://$host/ HTTP/1.1\r\n\r\n'));
      expect(
        await readUntil(e, '\r\n\r\n').timeout(const Duration(seconds: 5)),
        startsWith('HTTP/1.1 403'),
      );

      await t.deactivate();
      expect(hooks, [t.port, null]);
      expect(
        t.findProxy(Uri.parse('https://$host:${upstream.port}/')),
        'DIRECT',
      );
      await t.close();
      await upstream.close();
    },
  );

  test('activation fails when the tailnet IP does not answer', () async {
    final s = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
    final port = s.port;
    await s.close(); // nothing listens there any more
    final t = TunnelProxy(webView: (_) async => true);
    expect(await t.activate('m.t.ts.net', port, '127.0.0.1'), isFalse);
    await t.close();
  });

  test('activation fails when the web view cannot use a proxy', () async {
    final up = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
    final t = TunnelProxy(webView: (p) async => p == null);
    expect(await t.activate('m.t.ts.net', up.port, '127.0.0.1'), isFalse);
    expect(t.findProxy(Uri.parse('https://m.t.ts.net:${up.port}/')), 'DIRECT');
    await t.close();
    await up.close();
  });
}
