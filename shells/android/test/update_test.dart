import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';
import 'package:cryptography/dart.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:madalean_shell/src/storage.dart';
import 'package:madalean_shell/src/update.dart';

class FakePlatform implements UpdatePlatform {
  FakePlatform(this.dir);
  final String dir;
  String version = '2.0.0';
  bool certOk = true;
  bool canInstallValue = true;
  String? installed;
  bool settingsOpened = false;
  @override
  Future<String> installedVersion() async => version;
  @override
  Future<List<String>> abis() async => ['arm64-v8a', 'armeabi-v7a'];
  @override
  Future<String> cacheDir() async => dir;
  @override
  Future<bool> apkMatchesInstalled(String path) async => certOk;
  @override
  Future<bool> canInstall() async => canInstallValue;
  @override
  Future<void> openInstallSettings() async => settingsOpened = true;
  @override
  Future<void> install(String path) async => installed = path;
}

void main() {
  late SimpleKeyPair kp;
  late List<int> pub;
  final apk = Uint8List.fromList(List.generate(3000, (i) => i % 251));

  setUpAll(() async {
    kp = await DartEd25519().newKeyPair();
    pub = (await kp.extractPublicKey()).bytes;
  });

  Map<String, dynamic> manifestJson({
    String channel = 'stable',
    String version = '2.0.1',
    String min = '',
    String? sha,
    int? size,
  }) => {
    'channel': channel,
    'version': version,
    'published': '2026-11-21T10:00:00+00:00',
    'notes_url': 'https://example.org/notes',
    'min_version': min,
    'files': [
      {
        'name': 'madalean-server-$version.tar.gz',
        'url': 'https://example.org/s.tgz',
        'sha256': 'a' * 64,
        'size': 10,
        'kind': 'server',
      },
      {
        'name': 'madalean-universal-release.apk',
        'url': 'https://example.org/u.apk',
        'sha256': 'b' * 64,
        'size': 10,
        'kind': 'apk',
      },
      {
        'name': 'madalean-arm64-v8a-release.apk',
        'url': 'https://example.org/a.apk',
        'sha256': sha ?? sha256Hex(apk),
        'size': size ?? apk.length,
        'kind': 'apk',
      },
    ],
  };

  Future<String> sign(List<int> bytes) async =>
      base64.encode((await DartEd25519().sign(bytes, keyPair: kp)).bytes);

  group('versions', () {
    test('compare', () {
      expect(compareVersions('2.0.1', '2.0.0'), 1);
      expect(compareVersions('2.0.0', '2.0.0'), 0);
      expect(compareVersions('2.0', '2.0.0'), 0);
      expect(compareVersions('2.10.0', '2.9.9'), 1);
      expect(compareVersions('2.0.0-rc1', '2.0.0'), -1);
      expect(compareVersions('1.9.9', '2.0.0'), -1);
    });
  });

  group('manifest signature', () {
    test('good manifest verifies', () async {
      final b = utf8.encode(jsonEncode(manifestJson()));
      final m = await verifyManifest(
        bytes: b,
        signatureText: '${await sign(b)}\n',
        publicKey: pub,
        expectedChannel: 'stable',
      );
      expect(m.version, '2.0.1');
      expect(m.files.length, 3);
    });

    test('tampered manifest, tampered/missing signature, other key', () async {
      final b = utf8.encode(jsonEncode(manifestJson()));
      final sig = await sign(b);
      final tampered = utf8.encode(jsonEncode(manifestJson(version: '9.9.9')));
      Future<void> expectErr(
        List<int> bytes,
        String? s,
        UpdateError e, {
        List<int>? key,
        String channel = 'stable',
      }) => expectLater(
        verifyManifest(
          bytes: Uint8List.fromList(bytes),
          signatureText: s,
          publicKey: key ?? pub,
          expectedChannel: channel,
        ),
        throwsA(isA<UpdateException>().having((x) => x.error, 'e', e)),
      );
      await expectErr(tampered, sig, UpdateError.badSignature);
      final badSig = base64.decode(sig)..[5] ^= 1;
      await expectErr(b, base64.encode(badSig), UpdateError.badSignature);
      await expectErr(b, null, UpdateError.unsigned);
      await expectErr(b, '  ', UpdateError.unsigned);
      await expectErr(b, 'not base64!', UpdateError.badSignature);
      final other = await (await DartEd25519().newKeyPair()).extractPublicKey();
      await expectErr(b, sig, UpdateError.badSignature, key: other.bytes);
      // Signed for "stable" but requested as "test" (and vice versa).
      await expectErr(b, sig, UpdateError.wrongChannel, channel: 'test');
    });

    test('channel name of the URL', () {
      expect(
        channelNameOf(
          Uri.parse('https://raantss18.github.io/madalean/updates/stable.json'),
        ),
        'stable',
      );
      expect(channelNameOf(Uri.parse('http://10.0.2.2:8/test.json')), 'test');
    });
  });

  group('decisions', () {
    test('offer: downgrade / same / newer / min_version', () {
      Manifest m(String v, [String min = '']) => parseManifest(
        utf8.encode(jsonEncode(manifestJson(version: v, min: min))),
      );
      expect(offerFor(m('1.9.0'), '2.0.0'), Offer.none);
      expect(offerFor(m('2.0.0'), '2.0.0'), Offer.none);
      expect(offerFor(m('2.0.1'), '2.0.0'), Offer.optional);
      expect(offerFor(m('2.1.0', '2.0.5'), '2.0.0'), Offer.manual);
      expect(offerFor(m('2.1.0', '2.0.0'), '2.0.0'), Offer.optional);
    });

    test('APK choice by ABI, universal fallback, server ignored', () {
      final files = parseManifest(utf8.encode(jsonEncode(manifestJson())))
          .files;
      expect(chooseApk(files, ['arm64-v8a'])!.name, contains('arm64-v8a'));
      expect(chooseApk(files, ['x86_64'])!.name, contains('universal'));
      expect(chooseApk([files.first], ['x86_64']), isNull);
    });
  });

  group('Updater end to end (fake HTTP)', () {
    late Directory tmp;
    setUp(() => tmp = Directory.systemTemp.createTempSync('upd'));
    tearDown(() => tmp.deleteSync(recursive: true));

    Future<Updater> make(
      FakePlatform p,
      Map<String, dynamic> manifest, {
      bool signed = true,
      List<int>? apkBody,
      bool tamper = false,
    }) async {
      final body = utf8.encode(jsonEncode(manifest));
      final sig = await sign(body);
      final served = tamper
          ? utf8.encode(jsonEncode({...manifest, 'notes_url': 'x'}))
          : body;
      final client = MockClient((r) async {
        final path = r.url.path;
        if (path.endsWith('stable.json')) {
          return http.Response.bytes(served, 200);
        }
        if (path.endsWith('stable.json.sig')) {
          return signed ? http.Response(sig, 200) : http.Response('', 404);
        }
        if (path.endsWith('a.apk')) {
          return http.Response.bytes(apkBody ?? apk, 200);
        }
        return http.Response('', 404);
      });
      final u = Updater(
        client: client,
        platform: p,
        prefs: MemoryPrefs(),
        channelUrl: Uri.parse('https://example.org/updates/stable.json'),
        publicKeyB64: base64.encode(pub),
      );
      await u.init();
      return u;
    }

    test('good update → ready → install', () async {
      final p = FakePlatform(tmp.path);
      final u = await make(p, manifestJson());
      await u.check();
      final st = u.status;
      expect(st, isA<UpdateReady>());
      st as UpdateReady;
      expect(st.version, '2.0.1');
      expect(File(st.path).readAsBytesSync(), apk);
      expect(u.bannerVisible, isTrue);
      expect(await u.install(), isTrue);
      expect(p.installed, st.path);
      u.dismiss();
      expect(u.bannerVisible, isFalse);
    });

    test('no install permission → settings opened', () async {
      final p = FakePlatform(tmp.path)..canInstallValue = false;
      final u = await make(p, manifestJson());
      await u.check();
      expect(await u.install(), isFalse);
      expect(p.settingsOpened, isTrue);
      expect(p.installed, isNull);
    });

    test('refusals', () async {
      Future<UpdateStatus> run(
        Map<String, dynamic> m, {
        bool signed = true,
        bool tamper = false,
        bool cert = true,
        List<int>? body,
        String version = '2.0.0',
      }) async {
        final p = FakePlatform(tmp.path)
          ..certOk = cert
          ..version = version;
        final u = await make(
          p,
          m,
          signed: signed,
          tamper: tamper,
          apkBody: body,
        );
        await u.check();
        return u.status;
      }

      Matcher failed(UpdateError e) =>
          isA<UpdateFailed>().having((f) => f.error, 'error', e);
      expect(
        await run(manifestJson(), signed: false),
        failed(UpdateError.unsigned),
      );
      expect(
        await run(manifestJson(), tamper: true),
        failed(UpdateError.badSignature),
      );
      expect(
        await run(manifestJson(), cert: false),
        failed(UpdateError.certificate),
      );
      expect(
        await run(manifestJson(), body: [...apk, 1]),
        failed(UpdateError.checksum),
      );
      expect(
        await run(manifestJson(sha: 'c' * 64)),
        failed(UpdateError.checksum),
      );
      expect(
        await run(manifestJson(channel: 'test')),
        failed(UpdateError.wrongChannel),
      );
      expect(await run(manifestJson(version: '1.0.0')), isA<UpdateUpToDate>());
      expect(
        await run(manifestJson(), version: '2.0.1'),
        isA<UpdateUpToDate>(),
      );
      // Nothing left behind after refusals.
      final left = Directory('${tmp.path}/updates');
      expect(
        left.existsSync() ? left.listSync().whereType<File>().length : 0,
        0,
      );
    });

    test('automatic check: at most once per 12 h, off switch', () async {
      var now = DateTime(2026, 11, 21, 8);
      var calls = 0;
      final p = FakePlatform(tmp.path)..version = '2.0.1';
      final body = utf8.encode(jsonEncode(manifestJson()));
      final sig = await sign(body);
      final prefs = MemoryPrefs();
      final u = Updater(
        client: MockClient((r) async {
          if (r.url.path.endsWith('.json')) calls++;
          return r.url.path.endsWith('.sig')
              ? http.Response(sig, 200)
              : http.Response.bytes(body, 200);
        }),
        platform: p,
        prefs: prefs,
        channelUrl: Uri.parse('https://example.org/updates/stable.json'),
        publicKeyB64: base64.encode(pub),
        now: () => now,
      );
      await u.init();
      await u.maybeCheck();
      expect(calls, 1);
      now = now.add(const Duration(hours: 6));
      await u.maybeCheck();
      expect(calls, 1);
      now = now.add(const Duration(hours: 7));
      await u.maybeCheck();
      expect(calls, 2);
      await u.setAutomatic(false);
      now = now.add(const Duration(days: 2));
      await u.maybeCheck();
      expect(calls, 2);
      expect(prefs.values['update.auto'], 'off');
    });

    test('not configured (no public key in this build)', () async {
      final u = Updater(
        client: MockClient((r) async => http.Response('', 500)),
        platform: FakePlatform(tmp.path),
        prefs: MemoryPrefs(),
        channelUrl: Uri.parse('https://example.org/updates/stable.json'),
        publicKeyB64: '',
      );
      await u.check();
      expect(
        u.status,
        isA<UpdateFailed>().having(
          (f) => f.error,
          'e',
          UpdateError.notConfigured,
        ),
      );
    });
  });
}
