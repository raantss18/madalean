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
        () => normaliseAddress('http://10.0.2.2:11621'),
        throwsAddress(AddressError.cleartextForbidden),
      );
      // Without scheme a loopback host is treated as https in release.
      expect(
        normaliseAddress('10.0.2.2:11621'),
        Uri.parse('https://10.0.2.2:11621'),
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
        'madalean://pair?host=10.0.2.2:11621&code=123456',
      )!;
      expect(
        pairLinkOrigin(l, allowCleartext: true),
        Uri.parse('http://10.0.2.2:11621'),
      );
      expect(
        () => pairLinkOrigin(l),
        throwsAddress(AddressError.cleartextForbidden),
      );
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
