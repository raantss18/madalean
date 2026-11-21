import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:madalean_shell/src/api.dart';
import 'package:madalean_shell/src/controller.dart';
import 'package:madalean_shell/src/routes.dart';
import 'package:madalean_shell/src/storage.dart';
import 'package:madalean_shell/src/strings.dart';
import 'package:madalean_shell/src/tunnel.dart';

const name = 'madalean.tail804764.ts.net';
const qr =
    'https://$name/pair?code=123456&ip=100.74.179.13&lan=192.168.1.20:11502';

/// Tunnels that just record what the controller asked.
class FakeTunnels implements Tunnels {
  bool ipAnswers = true;
  String? active;
  final List<String> log = [];
  @override
  Future<bool> activate(String host, int port, String ip) async {
    log.add('on $host:$port→$ip');
    if (!ipAnswers) return false;
    active = host;
    return true;
  }

  @override
  Future<void> deactivate() async => active = null;
}

/// One Madalean host reachable by name (MagicDNS), tailnet IP (through the
/// tunnel) and LAN listener; each path can be cut.
class Host {
  Host(this.tunnels);
  final FakeTunnels tunnels;
  String? nameError = "Failed host lookup: '$name'";
  bool lanUp = true;
  String lang = 'fr';
  final Set<String> tokens = {};
  final List<String> seen = [];

  Future<http.Response> handle(http.Request r) async {
    final host = r.url.host;
    if (host == name && tunnels.active != name && nameError != null) {
      throw http.ClientException(nameError!, r.url);
    }
    if (host == '192.168.1.20' && !lanUp) {
      throw http.ClientException('Connection timed out', r.url);
    }
    seen.add(
      '${r.url.scheme}://$host${tunnels.active == host ? ' (ip)' : ''}'
      ' ${r.url.path}',
    );
    final auth = r.headers['Authorization'] ?? '';
    final valid =
        auth.startsWith('Bearer ') && tokens.contains(auth.substring(7));
    switch (r.url.path) {
      case '/api/hello':
        return http.Response(
          jsonEncode({
            'name': 'madalean',
            'version': 't',
            'paired': valid,
            'local': false,
            'host_name': 'pc',
            'lang': lang,
          }),
          200,
        );
      case '/api/pair':
        final b = jsonDecode(r.body) as Map<String, dynamic>;
        if (b['code'] != '123456') return http.Response('{}', 403);
        tokens.add('tok-${'x' * 20}');
        return http.Response(jsonEncode({'token': 'tok-${'x' * 20}'}), 200);
      case '/api/session/ticket':
        if (!valid) return http.Response('{}', 401);
        return http.Response(jsonEncode({'ticket': 'tk'}), 200);
    }
    return http.Response('', 404);
  }
}

void main() {
  group('candidateRoutes', () {
    final o = Uri.parse('https://$name');
    test('TLS first, then LAN; preferred first within its group', () {
      final r = candidateRoutes(
        o,
        ip: '100.74.179.13',
        lan: ['192.168.1.20:11502', 'junk'],
      );
      expect(r.map((x) => x.id), ['name', 'ip', 'lan:192.168.1.20:11502']);
      expect(r[1].origin, o);
      expect(r[2].origin, Uri.parse('http://192.168.1.20:11502'));
      expect(r[2].encrypted, isFalse);
      // Remembered LAN route never jumps before the encrypted ones.
      expect(
        candidateRoutes(
          o,
          ip: '100.74.179.13',
          lan: ['192.168.1.20:11502'],
          preferred: 'lan:192.168.1.20:11502',
        ).map((x) => x.id),
        ['name', 'ip', 'lan:192.168.1.20:11502'],
      );
      expect(
        candidateRoutes(
          o,
          ip: '100.74.179.13',
          preferred: 'ip',
        ).map((x) => x.id),
        ['ip', 'name'],
      );
    });
    test('a non-tailnet ip is ignored; LAN-only host', () {
      expect(candidateRoutes(o, ip: '8.8.8.8').length, 1);
      final lan = Uri.parse('http://192.168.1.20:11502');
      expect(
        candidateRoutes(lan, lan: ['192.168.1.20:11502']).map((x) => x.id),
        ['lan:192.168.1.20:11502'],
      );
    });
  });

  group('controller with fallbacks', () {
    late FakeTunnels tunnels;
    late Host host;
    late MemoryPrefs prefs;
    late MemoryTokenStore tokens;

    ShellController make() => ShellController(
      api: MadaleanApi(MockClient(host.handle)),
      tokens: tokens,
      prefs: prefs,
      defaultDeviceName: 'Poco F8 Pro',
      allowCleartext: false,
      tunnels: tunnels,
      now: () => DateTime(2026, 11, 22),
    );

    setUp(() {
      tunnels = FakeTunnels();
      host = Host(tunnels);
      prefs = MemoryPrefs();
      tokens = MemoryTokenStore();
    });

    test(
      'scan: Tailscale off → LAN listener, remembered, token by name',
      () async {
        tunnels.ipAnswers = false; // Tailscale off: 100.x does not answer
        final c = make();
        await c.init();
        expect(await c.scanned(qr), isTrue);
        final st = c.state as WebState;
        expect(st.origin, Uri.parse('http://192.168.1.20:11502'));
        expect(
          st.url.toString(),
          startsWith('http://192.168.1.20:11502/api/session'),
        );
        expect(tokens.values.keys, ['token:https://$name']);
        final saved = c.servers.servers.single;
        expect(saved.ip, '100.74.179.13');
        expect(saved.lan, ['192.168.1.20:11502']);
        expect(saved.route, 'lan:192.168.1.20:11502');
        expect(saved.deviceName, 'Poco F8 Pro');
        // Tailscale switched on later: the next start uses the name again.
        host.nameError = null;
        final c2 = make();
        await c2.init();
        expect((c2.state as WebState).origin, Uri.parse('https://$name'));
        expect(c2.servers.servers.single.route, 'name');
      },
    );

    test(
      'MagicDNS broken but tailnet up → name through its tailnet IP',
      () async {
        final c = make();
        await c.init();
        await c.scanned(qr);
        final st = c.state as WebState;
        expect(st.origin, Uri.parse('https://$name'));
        expect(tunnels.active, name);
        expect(tunnels.log, everyElement('on $name:443→100.74.179.13'));
        expect(host.seen.last, 'https://$name (ip) /api/session/ticket');
        expect(c.servers.servers.single.route, 'ip');
      },
    );

    test('nothing reachable: Tailscale message in French + flag', () async {
      tunnels.ipAnswers = false;
      host.lanUp = false;
      final c = make();
      await c.init();
      await c.scanned(qr);
      final st = c.state as ConnectState;
      expect(st.tailscale, isTrue);
      expect(st.code, '123456');
      expect(
        st.message!(const S(Lang.fr)),
        'Tailscale n’est pas connecté sur ce téléphone. Ouvrez l’app '
        'Tailscale et activez-la, puis réessayez.',
      );
    });

    test(
      'saved server unreachable → unreachable screen with Tailscale flag',
      () async {
        host.nameError = null;
        final c = make();
        await c.init();
        await c.scanned('https://$name/pair?code=123456');
        expect(c.state, isA<WebState>());
        host.nameError = "Failed host lookup: '$name'";
        final c2 = make();
        await c2.init();
        final st = c2.state as UnreachableState;
        expect(st.tailscale, isTrue);
        expect(st.net, NetError.hostLookup);
      },
    );

    test('a scanned QR code without code only prefills', () async {
      final c = make();
      await c.init();
      expect(await c.scanned('madalean://pair?host=$name'), isTrue);
      expect(c.state, isA<ConnectState>());
      expect((c.state as ConnectState).address, name);
      expect(await c.scanned('https://example.com/'), isFalse);
    });

    test('language: host language unless chosen in the app', () async {
      host
        ..nameError = null
        ..lang = 'en';
      final c = make();
      await c.init();
      expect(c.lang, Lang.fr); // French by default
      await c.scanned('https://$name/pair?code=123456');
      expect(c.lang, Lang.en); // follows the host
      await c.setLang(Lang.fr);
      final c2 = make();
      await c2.init();
      expect(c2.lang, Lang.fr); // explicit choice wins
      // The former toggle's key is ignored (it was often hit by mistake).
      final p = MemoryPrefs()..values['lang'] = 'en';
      final c3 = ShellController(
        api: MadaleanApi(MockClient(host.handle)),
        tokens: MemoryTokenStore(),
        prefs: p,
        defaultDeviceName: 'x',
        allowCleartext: false,
      );
      await c3.init();
      expect(c3.lang, Lang.fr);
    });
  });

  group('error messages', () {
    test('classifyNetError', () {
      expect(
        classifyNetError("Failed host lookup: 'madalean.tail804764.ts.net'"),
        NetError.hostLookup,
      );
      expect(
        classifyNetError('Connection refused (OS Error: errno = 111)'),
        NetError.refused,
      );
      expect(classifyNetError('Connection timed out'), NetError.timeout);
      expect(
        classifyNetError('Network is unreachable (errno = 101)'),
        NetError.noNetwork,
      );
      expect(classifyNetError('TLS: CERTIFICATE_VERIFY_FAILED'), NetError.tls);
      expect(classifyNetError('boom'), NetError.other);
    });
    test('netMessage (French)', () {
      const s = S(Lang.fr);
      expect(
        netMessage(s, NetError.hostLookup, tailscale: true),
        startsWith('Tailscale n’est pas connecté'),
      );
      expect(
        netMessage(s, NetError.refused, tailscale: false),
        contains('refuse la connexion'),
      );
      expect(
        netMessage(s, NetError.timeout, tailscale: false),
        startsWith('Pas de réponse'),
      );
      expect(
        netMessage(s, NetError.noNetwork, tailscale: false),
        contains('pas de réseau'),
      );
      expect(
        netMessage(s, NetError.hostLookup, tailscale: false),
        startsWith('Adresse introuvable'),
      );
    });
  });
}
