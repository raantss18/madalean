/// Server addresses and `madalean://pair` links (pure logic, unit-tested).
library;

import 'package:flutter/foundation.dart';

/// Madalean's embedded Tailscale node (tsnet) serves HTTPS on the standard
/// port: `https://madalean.<tailnet>.ts.net`.
const int defaultRemotePort = 443;

/// Port of the former `tailscale serve --https=10500` design: saved
/// `*.ts.net:10500` servers are migrated to 443 (see [migrateLegacyOrigin]).
const int legacyRemotePort = 10500;

/// Hosts that are reached over plain HTTP. Only accepted when cleartext is
/// allowed (debug builds, for the mock-server smoke test on the emulator).
const Set<String> loopbackHosts = {'127.0.0.1', 'localhost', '10.0.2.2'};

/// Default port of the host's optional LAN listener (plain HTTP, docs/SHELLS.md).
const int defaultLanPort = 11502;

List<int>? _ipv4(String host) {
  final parts = host.split('.');
  if (parts.length != 4) return null;
  final out = <int>[];
  for (final p in parts) {
    if (!RegExp(r'^\d{1,3}$').hasMatch(p)) return null;
    final v = int.parse(p);
    if (v > 255) return null;
    out.add(v);
  }
  return out;
}

/// Private IPv4 of a home/office network (RFC 1918): where the host's LAN
/// listener can be reached over plain HTTP (accepted risk D32).
bool isLanIPv4(String host) {
  final a = _ipv4(host);
  if (a == null) return false;
  return a[0] == 10 ||
      (a[0] == 172 && a[1] >= 16 && a[1] <= 31) ||
      (a[0] == 192 && a[1] == 168);
}

/// Tailscale address (100.64.0.0/10, CGNAT range).
bool isTailnetIPv4(String host) {
  final a = _ipv4(host);
  return a != null && a[0] == 100 && a[1] >= 64 && a[1] <= 127;
}

/// `a.b.c.d:port` with a private LAN address → normalised, else null.
String? parseLanHostPort(String text) {
  final m = RegExp(r'^(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})$')
      .firstMatch(text.trim());
  if (m == null || !isLanIPv4(m.group(1)!)) return null;
  final port = int.parse(m.group(2)!);
  if (port < 1 || port > 65535) return null;
  return '${_ipv4(m.group(1)!)!.join('.')}:$port';
}

/// Why an address was rejected.
enum AddressError { empty, invalid, cleartextForbidden, needFullName }

class AddressException implements Exception {
  const AddressException(this.error);
  final AddressError error;
  @override
  String toString() => 'AddressException($error)';
}

/// Normalises what the user typed ("host.tailnet.ts.net", "host:port",
/// "https://host:port/anything") into an origin `scheme://host:port`.
///
/// HTTPS is the only scheme accepted unless [allowCleartext] is true, in which
/// case `http://` is accepted for [loopbackHosts] only.
Uri normaliseAddress(String input, {bool allowCleartext = false}) {
  var text = input.trim();
  if (text.isEmpty) throw const AddressException(AddressError.empty);
  if (text.contains(RegExp(r'\s'))) {
    throw const AddressException(AddressError.invalid);
  }
  if (!text.contains('://')) {
    final hostPart = text.split('/').first.split(':').first.toLowerCase();
    // Madalean only has HTTPS on its tailnet name; a private LAN address is
    // its LAN listener, which speaks plain HTTP.
    text =
        (allowCleartext && loopbackHosts.contains(hostPart)) ||
            isLanIPv4(hostPart)
        ? 'http://$text'
        : 'https://$text';
  }
  final Uri uri;
  try {
    uri = Uri.parse(text);
  } on FormatException {
    throw const AddressException(AddressError.invalid);
  }
  final scheme = uri.scheme.toLowerCase();
  final host = uri.host.toLowerCase();
  if (host.isEmpty || uri.userInfo.isNotEmpty) {
    throw const AddressException(AddressError.invalid);
  }
  if (scheme == 'http') {
    if (isLanIPv4(host) && !(allowCleartext && loopbackHosts.contains(host))) {
      // LAN listener (plain HTTP, private address only; code + token as
      // for any LAN client).
      return Uri(
        scheme: 'http',
        host: host,
        port: uri.hasPort ? uri.port : defaultLanPort,
      );
    }
    if (!allowCleartext || !loopbackHosts.contains(host)) {
      throw const AddressException(AddressError.cleartextForbidden);
    }
    if (!uri.hasPort) throw const AddressException(AddressError.invalid);
    return Uri(scheme: 'http', host: host, port: uri.port);
  }
  if (scheme != 'https') throw const AddressException(AddressError.invalid);
  // A MagicDNS short name resolves, but the Let's Encrypt certificate is for
  // the full name (host.tailnet.ts.net): require a dotted name or an IP.
  if (!host.contains('.') && !host.contains(':')) {
    throw const AddressException(AddressError.needFullName);
  }
  return Uri(
    scheme: 'https',
    host: host,
    port: uri.hasPort ? uri.port : defaultRemotePort,
  );
}

/// Canonical text form of an origin: `https://host` for the default 443,
/// `scheme://host:port` otherwise.
String originKey(Uri origin) => origin.scheme == 'https' && origin.port == 443
    ? 'https://${origin.host}'
    : '${origin.scheme}://${origin.host}:${origin.port}';

/// Saved origin of the former design (`https://<x>.ts.net:10500`) → its new
/// canonical form (`https://<x>.ts.net`), or null.
Uri? migrateLegacyOrigin(Uri origin) =>
    origin.scheme == 'https' &&
        origin.port == legacyRemotePort &&
        origin.host.endsWith('.ts.net')
    ? Uri(scheme: 'https', host: origin.host, port: 443)
    : null;

/// Display form: drops the default port.
String displayAddress(Uri origin) {
  if (origin.scheme == 'https' && origin.port == defaultRemotePort) {
    return origin.host;
  }
  return '${origin.host}:${origin.port}';
}

/// Content of a pairing link: `madalean://pair?host=…&code=…[&ip=…][&lan=…]`
/// or the host's QR code `https://<host>/pair?code=…[&ip=…][&lan=…]`
/// (`http://<LAN address>/pair?code=…` when the host has no tailnet name).
@immutable
class PairLink {
  const PairLink({required this.host, this.code, this.ip, this.lan = const []});

  /// Host as written in the link (`name.tailnet.ts.net[:port]`).
  final String host;

  /// Six-digit code, or null if absent/invalid.
  final String? code;

  /// Tailnet IPv4 of the host (used when MagicDNS does not resolve the name;
  /// TLS is still checked against the name).
  final String? ip;

  /// LAN listener addresses `a.b.c.d:port` (plain HTTP, private addresses).
  final List<String> lan;

  @override
  bool operator ==(Object other) =>
      other is PairLink &&
      other.host == host &&
      other.code == code &&
      other.ip == ip &&
      listEquals(other.lan, lan);
  @override
  int get hashCode => Object.hash(host, code, ip, Object.hashAll(lan));
}

final RegExp _sixDigits = RegExp(r'^\d{6}$');

/// True if [code] is exactly six ASCII digits.
bool isValidCode(String code) => _sixDigits.hasMatch(code);

String? _ipParam(Map<String, String> q) {
  final ip = (q['ip'] ?? '').trim();
  return isTailnetIPv4(ip) ? ip : null;
}

List<String> _lanParam(Map<String, String> q) => [
  for (final part in (q['lan'] ?? '').split(',').take(3))
    ?parseLanHostPort(part),
];

/// Parses a pairing link (also embedded in pasted or scanned text).
/// Returns null when the text holds no usable link.
PairLink? parsePairLink(String text) {
  final match = RegExp(
    r'madalean://pair\?\S+',
    caseSensitive: false,
  ).firstMatch(text.trim());
  if (match == null) return _parseWebPairLink(text);
  final Uri uri;
  try {
    uri = Uri.parse(match.group(0)!);
  } on FormatException {
    return null;
  }
  final host = (uri.queryParameters['host'] ?? '').trim();
  if (host.isEmpty || host.contains('/') || host.contains('@')) return null;
  final code = (uri.queryParameters['code'] ?? '').trim();
  return PairLink(
    host: host,
    code: isValidCode(code) ? code : null,
    ip: _ipParam(uri.queryParameters),
    lan: _lanParam(uri.queryParameters),
  );
}

PairLink? _parseWebPairLink(String text) {
  final m = RegExp(
    r'https?://\S+',
    caseSensitive: false,
  ).firstMatch(text.trim());
  if (m == null) return null;
  final Uri uri;
  try {
    uri = Uri.parse(m.group(0)!);
  } on FormatException {
    return null;
  }
  if (uri.path != '/pair' || uri.userInfo.isNotEmpty || uri.host.isEmpty) {
    return null;
  }
  final code = (uri.queryParameters['code'] ?? '').trim();
  if (!isValidCode(code)) return null;
  if (uri.scheme.toLowerCase() == 'http') {
    // Plain-HTTP QR code: only the host's LAN listener.
    final lan = parseLanHostPort('${uri.host}:${uri.port}');
    if (lan == null) return null;
    return PairLink(host: lan, code: code);
  }
  final host = uri.hasPort && uri.port != 443
      ? '${uri.host}:${uri.port}'
      : uri.host;
  return PairLink(
    host: host,
    code: code,
    ip: _ipParam(uri.queryParameters),
    lan: _lanParam(uri.queryParameters),
  );
}

/// Origin of a pair-link host: `https`, except loopback hosts (debug only)
/// and private LAN addresses (the LAN listener), which use `http`.
Uri pairLinkOrigin(PairLink link, {bool allowCleartext = false}) {
  final hostOnly = link.host.split(':').first.toLowerCase();
  final prefix = loopbackHosts.contains(hostOnly) || isLanIPv4(hostOnly)
      ? 'http://'
      : 'https://';
  return normaliseAddress(
    '$prefix${link.host}',
    allowCleartext: allowCleartext,
  );
}
