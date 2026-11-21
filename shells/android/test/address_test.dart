import 'package:flutter_test/flutter_test.dart';
import 'package:madalean_shell/src/address.dart';

Matcher throwsAddress(AddressError e) =>
    throwsA(isA<AddressException>().having((x) => x.error, 'error', e));

void main() {
  group('normaliseAddress', () {
    test('tailnet name gets https on the default port 443', () {
      final o = normaliseAddress(' madalean.tail804764.ts.net ');
      expect(o, Uri.parse('https://madalean.tail804764.ts.net'));
      expect(o.port, 443);
      expect(originKey(o), 'https://madalean.tail804764.ts.net');
      expect(
        originKey(normaliseAddress('https://madalean.t.ts.net:443/x')),
        'https://madalean.t.ts.net',
      );
    });
    test('explicit port and https URL with path are reduced to origin', () {
      expect(
        normaliseAddress('host.tail.ts.net:8443'),
        Uri.parse('https://host.tail.ts.net:8443'),
      );
      expect(
        normaliseAddress('HTTPS://Host.Tail.ts.net:10500/some/page?x=1'),
        Uri.parse('https://host.tail.ts.net:10500'),
      );
    });
    test('IP addresses are accepted over https', () {
      expect(
        normaliseAddress('100.101.102.103'),
        Uri.parse('https://100.101.102.103'),
      );
    });
    test('http is refused in release mode, even for loopback', () {
      expect(
        () => normaliseAddress('http://host.tail.ts.net:10500'),
        throwsAddress(AddressError.cleartextForbidden),
      );
      expect(
        () => normaliseAddress('http://127.0.0.1:11621'),
        throwsAddress(AddressError.cleartextForbidden),
      );
      expect(
        () => normaliseAddress('http://203.0.113.5:11502'),
        throwsAddress(AddressError.cleartextForbidden),
      );
      expect(
        () => normaliseAddress('http://100.74.179.13:11502'),
        throwsAddress(AddressError.cleartextForbidden),
      );
      // Without scheme a loopback host is treated as https in release.
      expect(
        normaliseAddress('127.0.0.1:11621'),
        Uri.parse('https://127.0.0.1:11621'),
      );
    });
    test('debug builds accept http to loopback hosts only', () {
      expect(
        normaliseAddress('10.0.2.2:11621', allowCleartext: true),
        Uri.parse('http://10.0.2.2:11621'),
      );
      expect(
        normaliseAddress('http://127.0.0.1:11601', allowCleartext: true),
        Uri.parse('http://127.0.0.1:11601'),
      );
      expect(
        () => normaliseAddress('http://evil.example:80', allowCleartext: true),
        throwsAddress(AddressError.cleartextForbidden),
      );
    });
    test('private LAN addresses use http (LAN listener, port 11502)', () {
      expect(
        normaliseAddress('192.168.1.20:11502'),
        Uri.parse('http://192.168.1.20:11502'),
      );
      expect(
        normaliseAddress('192.168.1.20'),
        Uri.parse('http://192.168.1.20:11502'),
      );
      expect(
        normaliseAddress('http://10.1.2.3:8080/x'),
        Uri.parse('http://10.1.2.3:8080'),
      );
      expect(
        normaliseAddress('172.16.0.9:11502'),
        Uri.parse('http://172.16.0.9:11502'),
      );
      // 172.32/12 is not private: https as any other address.
      expect(
        normaliseAddress('172.32.0.9:11502'),
        Uri.parse('https://172.32.0.9:11502'),
      );
    });
    test('address classes', () {
      expect(isLanIPv4('192.168.0.1'), isTrue);
      expect(isLanIPv4('10.0.0.1'), isTrue);
      expect(isLanIPv4('172.31.255.1'), isTrue);
      expect(isLanIPv4('100.74.179.13'), isFalse);
      expect(isLanIPv4('127.0.0.1'), isFalse);
      expect(isLanIPv4('192.168.1.256'), isFalse);
      expect(isLanIPv4('h.ts.net'), isFalse);
      expect(isTailnetIPv4('100.74.179.13'), isTrue);
      expect(isTailnetIPv4('100.128.0.1'), isFalse);
      expect(isTailnetIPv4('192.168.1.2'), isFalse);
      expect(parseLanHostPort('192.168.1.20:11502'), '192.168.1.20:11502');
      expect(parseLanHostPort('192.168.1.20'), isNull);
      expect(parseLanHostPort('8.8.8.8:11502'), isNull);
      expect(parseLanHostPort('192.168.1.20:70000'), isNull);
    });
    test('short MagicDNS names are refused (certificate is for FQDN)', () {
      expect(
        () => normaliseAddress('antsa-nitroanv1541'),
        throwsAddress(AddressError.needFullName),
      );
    });
    test('garbage', () {
      expect(() => normaliseAddress('  '), throwsAddress(AddressError.empty));
      expect(
        () => normaliseAddress('a b.ts.net'),
        throwsAddress(AddressError.invalid),
      );
      expect(
        () => normaliseAddress('ftp://x.ts.net'),
        throwsAddress(AddressError.invalid),
      );
      expect(
        () => normaliseAddress('https://user:pw@x.ts.net'),
        throwsAddress(AddressError.invalid),
      );
    });
  });

  group('display / key', () {
    test('default port hidden, explicit ports kept', () {
      final o = normaliseAddress('h.t.ts.net');
      expect(displayAddress(o), 'h.t.ts.net');
      expect(originKey(o), 'https://h.t.ts.net');
      final legacy = Uri.parse('https://h.t.ts.net:10500');
      expect(displayAddress(legacy), 'h.t.ts.net:10500');
      expect(originKey(legacy), 'https://h.t.ts.net:10500');
      expect(displayAddress(Uri.parse('https://h.t.ts.net:1')), 'h.t.ts.net:1');
    });
    test('legacy 10500 tailnet origins migrate to 443', () {
      expect(
        migrateLegacyOrigin(Uri.parse('https://pc.tail1.ts.net:10500')),
        Uri.parse('https://pc.tail1.ts.net'),
      );
      expect(
        migrateLegacyOrigin(Uri.parse('https://pc.example.org:10500')),
        isNull,
      );
      expect(migrateLegacyOrigin(Uri.parse('https://pc.tail1.ts.net')), isNull);
    });
  });

  group('pair links', () {
    test('https form of the QR code', () {
      final l = parsePairLink(
        'https://madalean.tail804764.ts.net/pair?code=654321',
      );
      expect(
        l,
        const PairLink(host: 'madalean.tail804764.ts.net', code: '654321'),
      );
      expect(
        pairLinkOrigin(l!),
        Uri.parse('https://madalean.tail804764.ts.net'),
      );
      expect(parsePairLink('https://m.t.ts.net/pair?code=12'), isNull);
      expect(parsePairLink('https://m.t.ts.net/other?code=123456'), isNull);
      expect(
        parsePairLink('https://m.t.ts.net:8443/pair?code=123456')!.host,
        'm.t.ts.net:8443',
      );
    });
    test('full link', () {
      final l = parsePairLink(
        'madalean://pair?host=antsa-nitroanv1541.tail804764.ts.net:10500&code=123456',
      );
      expect(
        l,
        const PairLink(
          host: 'antsa-nitroanv1541.tail804764.ts.net:10500',
          code: '123456',
        ),
      );
      expect(
        pairLinkOrigin(l!),
        Uri.parse('https://antsa-nitroanv1541.tail804764.ts.net:10500'),
      );
    });
    test('embedded in pasted text, port omitted, bad code dropped', () {
      final l = parsePairLink(
        'Scan: madalean://pair?host=h.t.ts.net&code=12ab56 ok',
      );
      expect(l, const PairLink(host: 'h.t.ts.net'));
      expect(pairLinkOrigin(l!), Uri.parse('https://h.t.ts.net'));
    });
    test('loopback hosts use http (debug only)', () {
      final l = parsePairLink(
        'madalean://pair?host=127.0.0.1:11621&code=123456',
      )!;
      expect(
        pairLinkOrigin(l, allowCleartext: true),
        Uri.parse('http://127.0.0.1:11621'),
      );
      expect(
        () => pairLinkOrigin(l),
        throwsAddress(AddressError.cleartextForbidden),
      );
    });
    test('QR code with fallbacks (tailnet IP, LAN listener)', () {
      const want = PairLink(
        host: 'madalean.tail804764.ts.net',
        code: '123456',
        ip: '100.74.179.13',
        lan: ['192.168.1.20:11502'],
      );
      expect(
        parsePairLink(
          'https://madalean.tail804764.ts.net/pair?code=123456'
          '&ip=100.74.179.13&lan=192.168.1.20%3A11502',
        ),
        want,
      );
      expect(
        parsePairLink(
          'madalean://pair?host=madalean.tail804764.ts.net&code=123456'
          '&ip=100.74.179.13&lan=192.168.1.20:11502',
        ),
        want,
      );
      // Bad fallbacks are dropped, the link stays usable.
      expect(
        parsePairLink(
          'https://m.t.ts.net/pair?code=123456&ip=8.8.8.8'
          '&lan=8.8.8.8:80,10.0.0.2:11502,junk',
        ),
        const PairLink(
          host: 'm.t.ts.net',
          code: '123456',
          lan: ['10.0.0.2:11502'],
        ),
      );
    });
    test('plain-http QR code: LAN listener only', () {
      final l = parsePairLink('http://192.168.1.20:11502/pair?code=123456')!;
      expect(l, const PairLink(host: '192.168.1.20:11502', code: '123456'));
      expect(pairLinkOrigin(l), Uri.parse('http://192.168.1.20:11502'));
      expect(parsePairLink('http://evil.example/pair?code=123456'), isNull);
      expect(parsePairLink('http://100.74.179.13/pair?code=123456'), isNull);
    });
    test('rejects links without host or with path/userinfo', () {
      expect(parsePairLink('madalean://pair?code=123456'), isNull);
      expect(parsePairLink('madalean://pair?host=a/b&code=123456'), isNull);
      expect(parsePairLink('madalean://pair?host=u@h.ts.net'), isNull);
      expect(parsePairLink('https://example.com'), isNull);
    });
    test('code validation', () {
      expect(isValidCode('012345'), isTrue);
      expect(isValidCode('12345'), isFalse);
      expect(isValidCode('1234567'), isFalse);
      expect(isValidCode('١٢٣٤٥٦'), isFalse); // non-ASCII digits
    });
  });
}
