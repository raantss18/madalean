import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:madalean_shell/src/api.dart';
import 'package:madalean_shell/src/controller.dart';
import 'package:madalean_shell/src/storage.dart';
import 'package:madalean_shell/src/strings.dart';

/// Minimal in-memory server following docs/SHELLS.md.
class FakeServer {
  String code = '123456';
  final Set<String> tokens = {};
  bool up = true;
  int n = 0;

  Future<http.Response> handle(http.Request r) async {
    if (!up) throw http.ClientException('connection refused');
    final auth = r.headers['Authorization'] ?? '';
    final tok = auth.startsWith('Bearer ') ? auth.substring(7) : null;
    final valid = tok != null && tokens.contains(tok);
    switch (r.url.path) {
      case '/api/hello':
        return http.Response(
          jsonEncode({
            'name': 'madalean',
            'version': 't',
            'paired': valid,
            'local': false,
            'host_name': 'host-pc',
          }),
          200,
        );
      case '/api/pair':
        final b = jsonDecode(r.body) as Map<String, dynamic>;
        if (b['code'] != code) {
          return http.Response('{"error":"bad_code"}', 401);
        }
        final t = 'token-${++n}-${'x' * 20}';
        tokens.add(t);
        return http.Response(jsonEncode({'token': t}), 200);
      case '/api/session/ticket':
        if (!valid) return http.Response('{"error":"unauthorized"}', 401);
        return http.Response(jsonEncode({'ticket': 'tk${++n}'}), 200);
    }
    return http.Response('', 404);
  }
}

void main() {
  late FakeServer server;
  late MemoryTokenStore tokens;
  late MemoryPrefs prefs;
  late DateTime now;

  ShellController make({bool cleartext = false}) => ShellController(
    api: MadaleanApi(MockClient(server.handle)),
    tokens: tokens,
    prefs: prefs,
    defaultDeviceName: 'Pixel 9',
    allowCleartext: cleartext,
    now: () => now,
  );

  String msg(ShellState st, [Lang l = Lang.en]) =>
      (st as ConnectState).message!(S(l));

  setUp(() {
    server = FakeServer();
    tokens = MemoryTokenStore();
    prefs = MemoryPrefs();
    now = DateTime(2026, 11, 21, 12);
  });

  test(
    'saved *.ts.net:10500 servers migrate to 443 with their token',
    () async {
      final old = Uri.parse('https://pc.tail.ts.net:10500');
      prefs.values['servers'] =
          '[{"origin":"https://pc.tail.ts.net:10500","host_name":"pc",'
          '"device_name":"Tab","last_used":1}]';
      final tok = server.tokens.isEmpty ? 'tok-legacy' : server.tokens.first;
      server.tokens.add(tok);
      await tokens.write(old, tok);
      final c = make();
      await c.init();
      expect(
        c.servers.servers.single.origin,
        Uri.parse('https://pc.tail.ts.net'),
      );
      expect(tokens.values.keys, ['token:https://pc.tail.ts.net']);
      expect(prefs.values['servers'], contains('"https://pc.tail.ts.net"'));
      expect(c.state, isA<WebState>());
    },
  );

  test('first start shows the connect screen', () async {
    final c = make();
    await c.init();
    expect(c.state, isA<ConnectState>());
    expect((c.state as ConnectState).message, isNull);
  });

  test('pairing stores the token securely and opens the web view', () async {
    final c = make();
    await c.init();
    await c.pair(address: 'pc.tail.ts.net', code: '123456', deviceName: '');
    final st = c.state as WebState;
    expect(st.url.path, '/api/session');
    expect(st.url.queryParameters['ticket'], startsWith('tk'));
    expect(st.url.queryParameters['next'], '/');
    expect(st.server.deviceName, 'Pixel 9');
    expect(st.server.hostName, 'host-pc');
    expect(tokens.values.keys, ['token:https://pc.tail.ts.net']);
    // The server list (shared_preferences) holds no secret.
    expect(prefs.values['servers'], isNot(contains('token-')));
    expect(prefs.values['servers'], contains('pc.tail.ts.net'));
  });

  test('wrong code keeps the form with an error and the input', () async {
    final c = make();
    await c.init();
    await c.pair(address: 'pc.tail.ts.net', code: '000000', deviceName: 'x');
    final st = c.state as ConnectState;
    expect(msg(st), contains('Wrong or expired code'));
    expect(st.address, 'pc.tail.ts.net');
    expect(st.code, '000000');
    expect(tokens.values, isEmpty);
  });

  test('invalid inputs are rejected before any network call', () async {
    server.up = false;
    final c = make();
    await c.init();
    await c.pair(
      address: 'http://pc.tail.ts.net',
      code: '123456',
      deviceName: '',
    );
    expect(msg(c.state), contains('https://'));
    await c.pair(address: 'pc.tail.ts.net', code: '12', deviceName: '');
    expect(msg(c.state, Lang.fr), contains('6 chiffres'));
  });

  test(
    'restart reopens last server; revoked token returns to pairing',
    () async {
      final c = make();
      await c.init();
      await c.pair(address: 'pc.tail.ts.net', code: '123456', deviceName: '');
      final c2 = make();
      await c2.init();
      expect(c2.state, isA<WebState>());

      server.tokens.clear(); // revoked on the host
      final c3 = make();
      await c3.init();
      expect(msg(c3.state), contains('no longer authorised'));
      expect((c3.state as ConnectState).address, 'pc.tail.ts.net');
      expect(tokens.values, isEmpty);
    },
  );

  test('server down at start → unreachable, retry recovers', () async {
    final c = make();
    await c.init();
    await c.pair(address: 'pc.tail.ts.net', code: '123456', deviceName: '');
    server.up = false;
    final c2 = make();
    await c2.init();
    expect(c2.state, isA<UnreachableState>());
    server.up = true;
    await c2.retry();
    expect(c2.state, isA<WebState>());
    c2.changeServer();
    expect(c2.state, isA<ConnectState>());
  });

  test('reauth (/pair navigation): fresh ticket if token valid', () async {
    final c = make();
    await c.init();
    await c.pair(address: 'pc.tail.ts.net', code: '123456', deviceName: '');
    final first = c.state as WebState;
    await c.reauth();
    final second = c.state as WebState;
    expect(second.url, isNot(first.url));
    expect(second.n, greaterThan(first.n));
    server.tokens.clear();
    await c.reauth();
    expect(c.state, isA<ConnectState>());
  });

  test('reauth loop is broken after 3 attempts within a minute', () async {
    final c = make();
    await c.init();
    await c.pair(address: 'pc.tail.ts.net', code: '123456', deviceName: '');
    for (var i = 0; i < 3; i++) {
      await c.reauth();
      expect(c.state, isA<WebState>());
    }
    await c.reauth();
    expect(c.state, isA<ConnectState>());
    expect(msg(c.state), isNotEmpty);
    expect(await tokens.read(Uri.parse('https://pc.tail.ts.net')), isNotNull);
  });

  test('web load failure → unreachable', () async {
    final c = make();
    await c.init();
    await c.pair(address: 'pc.tail.ts.net', code: '123456', deviceName: '');
    c.webLoadFailed('net::ERR_NAME_NOT_RESOLVED');
    expect((c.state as UnreachableState).detail, contains('NAME'));
  });

  test('resume after >30 s detects outage and revocation', () async {
    final c = make();
    await c.init();
    await c.pair(address: 'pc.tail.ts.net', code: '123456', deviceName: '');
    server.up = false;
    c.paused();
    now = now.add(const Duration(seconds: 10));
    await c.resumed();
    expect(c.state, isA<WebState>());
    c.paused();
    now = now.add(const Duration(seconds: 31));
    await c.resumed();
    expect(c.state, isA<UnreachableState>());
    server.up = true;
    await c.retry();
    expect(c.state, isA<WebState>());
    server.tokens.clear();
    c.paused();
    now = now.add(const Duration(minutes: 5));
    await c.resumed();
    expect(c.state, isA<ConnectState>());
  });

  test('pair links prefill the form; multiple servers are kept', () async {
    final c = make(cleartext: true);
    await c.init(
      initialLink: 'madalean://pair?host=10.0.2.2:11621&code=654321',
    );
    var st = c.state as ConnectState;
    expect(st.address, 'http://10.0.2.2:11621');
    expect(st.code, '654321');
    expect(c.handleLink('nothing here'), isFalse);
    expect(
      c.handleLink('madalean://pair?host=b.tail.ts.net&code=123456'),
      isTrue,
    );
    st = c.state as ConnectState;
    expect(st.address, 'b.tail.ts.net');

    await c.pair(address: 'a.tail.ts.net', code: '123456', deviceName: '');
    now = now.add(const Duration(minutes: 1));
    await c.pair(address: 'b.tail.ts.net', code: '123456', deviceName: '');
    expect(c.servers.servers.map((s) => s.origin.host), [
      'b.tail.ts.net',
      'a.tail.ts.net',
    ]);
    await c.forgetServer(c.servers.servers.first);
    expect(c.servers.servers.map((s) => s.origin.host), ['a.tail.ts.net']);
    expect(tokens.values.keys, ['token:https://a.tail.ts.net']);
  });

  test('release mode refuses an http pair link', () async {
    final c = make();
    await c.init(initialLink: 'madalean://pair?host=10.0.2.2:1&code=123456');
    expect(msg(c.state), contains('https://'));
  });

  test('language choice persists', () async {
    final c = make();
    await c.init();
    expect(c.lang, Lang.fr);
    await c.setLang(Lang.en);
    final c2 = make();
    await c2.init();
    expect(c2.lang, Lang.en);
  });
}
