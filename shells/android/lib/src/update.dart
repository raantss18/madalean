/// Signed, automatic updates of the Android shell (docs/SHELLS.md,
/// "Update channel").
///
/// Channel: `stable.json` + `stable.json.sig` (base64 Ed25519 signature of the
/// exact bytes of the JSON, by the release key kept outside git; the public
/// key is injected at build time). The manifest is verified BEFORE anything
/// is downloaded; the APK is then checked for size, SHA-256 and signing
/// certificate (must equal the installed app's) before the user is offered
/// the system installer — Android always requires that tap.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:crypto/crypto.dart' as hash;
import 'package:cryptography/cryptography.dart';
import 'package:cryptography/dart.dart';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:madalean_shell/src/storage.dart';

/// Fixed channel of release builds (HTTPS only).
const String stableChannelUrl =
    'https://raantss18.github.io/madalean/updates/stable.json';

/// Public key (base64, 32 bytes), from the release key at build time:
/// `--dart-define=MADALEAN_UPDATE_PUBKEY=…` (scripts/build_apk.sh).
const String buildPublicKey = String.fromEnvironment('MADALEAN_UPDATE_PUBKEY');

/// Debug builds only: alternative channel URL for tests.
const String debugChannelOverride = String.fromEnvironment(
  'MADALEAN_UPDATE_CHANNEL',
);

const Duration checkInterval = Duration(hours: 12);
const int maxApkBytes = 200 * 1024 * 1024;

enum UpdateError {
  network,
  unsigned,
  badSignature,
  badManifest,
  wrongChannel,
  noFile,
  checksum,
  certificate,
  notConfigured,
  install,
}

class UpdateException implements Exception {
  const UpdateException(this.error, [this.detail]);
  final UpdateError error;
  final String? detail;
  @override
  String toString() =>
      'UpdateException($error${detail == null ? '' : ': $detail'})';
}

// ------------------------------------------------------------------ versions

List<int> _nums(String v) => [
  for (final p in v.split(RegExp('[-+]')).first.trim().split('.'))
    int.tryParse(p) ?? 0,
];

/// Dotted numeric comparison; a pre-release suffix sorts before the release
/// (`2.0.0-rc1` < `2.0.0`).
int compareVersions(String a, String b) {
  final x = _nums(a);
  final y = _nums(b);
  for (var i = 0; i < (x.length > y.length ? x.length : y.length); i++) {
    final d = (i < x.length ? x[i] : 0) - (i < y.length ? y[i] : 0);
    if (d != 0) return d.sign;
  }
  final pa = a.contains('-');
  final pb = b.contains('-');
  if (pa == pb) return 0;
  return pa ? -1 : 1;
}

// ------------------------------------------------------------------ manifest

@immutable
class UpdateFile {
  const UpdateFile({
    required this.name,
    required this.url,
    required this.sha256,
    required this.size,
    required this.kind,
  });
  final String name;
  final Uri url;
  final String sha256;
  final int size;
  final String kind;
}

@immutable
class Manifest {
  const Manifest({
    required this.channel,
    required this.version,
    required this.published,
    required this.notesUrl,
    required this.minVersion,
    required this.files,
  });
  final String channel;
  final String version;
  final String published;
  final String notesUrl;
  final String minVersion;
  final List<UpdateFile> files;
}

/// Base name of the channel file (`stable` for …/stable.json).
String channelNameOf(Uri url) {
  final last = url.pathSegments.isEmpty ? '' : url.pathSegments.last;
  return last.endsWith('.json') ? last.substring(0, last.length - 5) : last;
}

Manifest parseManifest(Uint8List bytes) {
  final Object? decoded;
  try {
    decoded = jsonDecode(utf8.decode(bytes));
  } on Object {
    throw const UpdateException(UpdateError.badManifest);
  }
  if (decoded is! Map<String, dynamic>) {
    throw const UpdateException(UpdateError.badManifest);
  }
  final j = decoded;
  String str(String k) => j[k] is String ? j[k] as String : '';
  final files = <UpdateFile>[];
  final raw = j['files'];
  if (raw is! List) throw const UpdateException(UpdateError.badManifest);
  for (final f in raw) {
    if (f is! Map<String, dynamic>) continue;
    final url = Uri.tryParse(f['url'] is String ? f['url'] as String : '');
    final sha = (f['sha256'] is String ? f['sha256'] as String : '')
        .toLowerCase();
    final size = f['size'];
    if (url == null ||
        !RegExp(r'^[0-9a-f]{64}$').hasMatch(sha) ||
        size is! int ||
        size <= 0) {
      continue;
    }
    files.add(
      UpdateFile(
        name: f['name'] is String ? f['name'] as String : '',
        url: url,
        sha256: sha,
        size: size,
        kind: f['kind'] is String ? f['kind'] as String : '',
      ),
    );
  }
  if (str('version').isEmpty) {
    throw const UpdateException(UpdateError.badManifest);
  }
  return Manifest(
    channel: str('channel'),
    version: str('version'),
    published: str('published'),
    notesUrl: str('notes_url'),
    minVersion: str('min_version'),
    files: files,
  );
}

/// Verifies the Ed25519 signature of the exact manifest bytes, then parses
/// it and checks that it was signed for [expectedChannel].
Future<Manifest> verifyManifest({
  required Uint8List bytes,
  required String? signatureText,
  required List<int> publicKey,
  required String expectedChannel,
}) async {
  if (signatureText == null || signatureText.trim().isEmpty) {
    throw const UpdateException(UpdateError.unsigned);
  }
  final List<int> sig;
  try {
    sig = base64.decode(signatureText.replaceAll(RegExp(r'\s'), ''));
  } on FormatException {
    throw const UpdateException(UpdateError.badSignature);
  }
  if (sig.length != 64 || publicKey.length != 32) {
    throw const UpdateException(UpdateError.badSignature);
  }
  final ok = await DartEd25519().verify(
    bytes,
    signature: Signature(
      sig,
      publicKey: SimplePublicKey(publicKey, type: KeyPairType.ed25519),
    ),
  );
  if (!ok) throw const UpdateException(UpdateError.badSignature);
  final m = parseManifest(bytes);
  if (m.channel != expectedChannel) {
    throw const UpdateException(UpdateError.wrongChannel);
  }
  return m;
}

/// The APK for this device: kind `apk`, the primary ABI's file first, else a
/// universal one.
UpdateFile? chooseApk(List<UpdateFile> files, List<String> abis) {
  final apks = [
    for (final f in files)
      if (f.kind == 'apk') f,
  ];
  for (final abi in abis) {
    for (final f in apks) {
      if (f.name.contains(abi)) return f;
    }
  }
  for (final f in apks) {
    if (f.name.contains('universal')) return f;
  }
  return null;
}

/// What to do with a verified manifest.
enum Offer { none, optional, required }

Offer offerFor(Manifest m, String installed) {
  if (compareVersions(m.version, installed) <= 0) return Offer.none;
  if (m.minVersion.isNotEmpty && compareVersions(installed, m.minVersion) < 0) {
    return Offer.required;
  }
  return Offer.optional;
}

String sha256Hex(List<int> bytes) => hash.sha256.convert(bytes).toString();

// ------------------------------------------------------------------ runtime

/// Platform side (MainActivity.kt), mockable in tests.
abstract class UpdatePlatform {
  Future<String> installedVersion();
  Future<List<String>> abis();
  Future<String> cacheDir();

  /// Signing certificates of the APK at [path] equal the installed app's,
  /// and it is the same package.
  Future<bool> apkMatchesInstalled(String path);
  Future<bool> canInstall();
  Future<void> openInstallSettings();
  Future<void> install(String path);
}

sealed class UpdateStatus {
  const UpdateStatus();
}

class UpdateIdle extends UpdateStatus {
  const UpdateIdle();
}

class UpdateChecking extends UpdateStatus {
  const UpdateChecking();
}

class UpdateUpToDate extends UpdateStatus {
  const UpdateUpToDate(this.version);
  final String version;
}

class UpdateDownloading extends UpdateStatus {
  const UpdateDownloading(this.version, this.received, this.total);
  final String version;
  final int received;
  final int total;
}

class UpdateReady extends UpdateStatus {
  const UpdateReady({
    required this.version,
    required this.path,
    required this.required,
  });
  final String version;
  final String path;
  final bool required;
}

class UpdateFailed extends UpdateStatus {
  const UpdateFailed(this.error, {this.detail});
  final UpdateError error;
  final String? detail;
}

const _kAuto = 'update.auto';
const _kLast = 'update.last_check';

class Updater extends ChangeNotifier {
  Updater({
    required this.client,
    required this.platform,
    required this.prefs,
    required this.channelUrl,
    required this.publicKeyB64,
    DateTime Function()? now,
  }) : _now = now ?? DateTime.now;

  final http.Client client;
  final UpdatePlatform platform;
  final Prefs prefs;
  final Uri channelUrl;
  final String publicKeyB64;
  final DateTime Function() _now;

  UpdateStatus status = const UpdateIdle();
  bool automatic = true;

  /// The user tapped "Later" for this version: keep quiet until next start.
  String? _dismissed;
  bool _busy = false;

  bool get configured => publicKeyB64.isNotEmpty;

  /// Whether the bottom banner should show [status].
  bool get bannerVisible => switch (status) {
    final UpdateReady r => r.required || r.version != _dismissed,
    _ => false,
  };

  void _set(UpdateStatus s) {
    status = s;
    notifyListeners();
  }

  Future<void> init() async {
    automatic = (await prefs.getString(_kAuto)) != 'off';
    // Leftovers of a previous run (installed or abandoned): start clean.
    try {
      final dir = Directory('${await platform.cacheDir()}/updates');
      if (dir.existsSync()) dir.deleteSync(recursive: true);
    } on Object {
      // Best effort.
    }
    notifyListeners();
  }

  // The switch's onChanged hands a positional bool.
  // ignore: avoid_positional_boolean_parameters
  Future<void> setAutomatic(bool on) async {
    automatic = on;
    await prefs.setString(_kAuto, on ? 'on' : 'off');
    notifyListeners();
    if (on) await maybeCheck();
  }

  void dismiss() {
    final s = status;
    if (s is UpdateReady) _dismissed = s.version;
    notifyListeners();
  }

  /// On start / resume: at most once per 12 h, only when automatic.
  Future<void> maybeCheck() async {
    if (!automatic || !configured || _busy || status is UpdateReady) return;
    final last = int.tryParse(await prefs.getString(_kLast) ?? '') ?? 0;
    final now = _now().millisecondsSinceEpoch;
    if (now - last < checkInterval.inMilliseconds && now >= last) return;
    await check(manual: false);
  }

  /// Full check; [manual] = « Vérifier maintenant » (errors are shown).
  Future<void> check({bool manual = true}) async {
    if (_busy) return;
    if (!configured) {
      _set(const UpdateFailed(UpdateError.notConfigured));
      return;
    }
    _busy = true;
    try {
      if (manual) _set(const UpdateChecking());
      await _check();
    } on UpdateException catch (e) {
      debugPrint('update: ${e.error}');
      _set(UpdateFailed(e.error, detail: e.detail));
    } on Object catch (e) {
      debugPrint('update: $e');
      _set(UpdateFailed(UpdateError.network, detail: e.runtimeType.toString()));
    } finally {
      _busy = false;
    }
  }

  Future<http.Response> _get(Uri url) async {
    final r = await client.get(url).timeout(const Duration(seconds: 20));
    return r;
  }

  Future<void> _check() async {
    final m = await _fetchManifest();
    await prefs.setString(_kLast, '${_now().millisecondsSinceEpoch}');
    final installed = await platform.installedVersion();
    final offer = offerFor(m, installed);
    if (offer == Offer.none) {
      _set(UpdateUpToDate(installed));
      return;
    }
    final file = chooseApk(m.files, await platform.abis());
    if (file == null) throw const UpdateException(UpdateError.noFile);
    if (file.size > maxApkBytes) {
      throw const UpdateException(UpdateError.checksum, 'too large');
    }
    final path = await _download(m.version, file);
    if (!await platform.apkMatchesInstalled(path)) {
      _delete(path);
      throw const UpdateException(UpdateError.certificate);
    }
    _set(
      UpdateReady(
        version: m.version,
        path: path,
        required: offer == Offer.required,
      ),
    );
  }

  Future<Manifest> _fetchManifest() async {
    final http.Response jr;
    final http.Response sr;
    try {
      jr = await _get(channelUrl);
      sr = await _get(channelUrl.replace(path: '${channelUrl.path}.sig'));
    } on Object catch (e) {
      throw UpdateException(UpdateError.network, e.runtimeType.toString());
    }
    if (jr.statusCode != 200) {
      throw UpdateException(UpdateError.network, 'HTTP ${jr.statusCode}');
    }
    return await verifyManifest(
      bytes: jr.bodyBytes,
      signatureText: sr.statusCode == 200 ? sr.body : null,
      publicKey: base64.decode(publicKeyB64),
      expectedChannel: channelNameOf(channelUrl),
    );
  }

  Future<String> _download(String version, UpdateFile f) async {
    final dir = Directory('${await platform.cacheDir()}/updates');
    await dir.create(recursive: true);
    final path = '${dir.path}/madalean-$version.apk';
    final tmp = File('$path.part');
    final req = http.Request('GET', f.url);
    final http.StreamedResponse resp;
    try {
      resp = await client.send(req).timeout(const Duration(seconds: 30));
    } on Object catch (e) {
      throw UpdateException(UpdateError.network, e.runtimeType.toString());
    }
    if (resp.statusCode != 200) {
      throw UpdateException(UpdateError.network, 'HTTP ${resp.statusCode}');
    }
    final sink = tmp.openWrite();
    final digest = _DigestSink();
    final hasher = hash.sha256.startChunkedConversion(digest);
    var received = 0;
    var lastNotify = 0;
    try {
      await for (final chunk in resp.stream.timeout(
        const Duration(seconds: 60),
      )) {
        received += chunk.length;
        if (received > f.size) {
          throw const UpdateException(UpdateError.checksum, 'size');
        }
        hasher.add(chunk);
        sink.add(chunk);
        if (received - lastNotify > 512 * 1024) {
          lastNotify = received;
          _set(UpdateDownloading(version, received, f.size));
        }
      }
      await sink.close();
    } on UpdateException {
      await sink.close();
      _delete(tmp.path);
      rethrow;
    } on Object catch (e) {
      await sink.close();
      _delete(tmp.path);
      throw UpdateException(UpdateError.network, e.runtimeType.toString());
    }
    hasher.close();
    if (received != f.size || digest.value?.toString() != f.sha256) {
      _delete(tmp.path);
      throw const UpdateException(UpdateError.checksum);
    }
    await tmp.rename(path);
    return path;
  }

  void _delete(String path) {
    try {
      File(path).deleteSync();
    } on Object {
      // Best effort.
    }
  }

  /// « Installer »: system installer (one tap from the user, Android rule).
  Future<bool> install() async {
    final s = status;
    if (s is! UpdateReady) return false;
    if (!await platform.canInstall()) {
      await platform.openInstallSettings();
      return false;
    }
    try {
      await platform.install(s.path);
      return true;
    } on Object catch (e) {
      _set(UpdateFailed(UpdateError.install, detail: e.runtimeType.toString()));
      return false;
    }
  }
}

class _DigestSink implements Sink<hash.Digest> {
  hash.Digest? value;
  @override
  void add(hash.Digest data) => value = data;
  @override
  void close() {}
}
