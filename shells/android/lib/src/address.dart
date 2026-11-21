/// Server addresses and `madalean://pair` links (pure logic, unit-tested).
library;

import 'package:flutter/foundation.dart';

/// Default HTTPS port of the remote listener published by `tailscale serve`.
const int defaultRemotePort = 10500;

/// Hosts that are reached over plain HTTP. Only accepted when cleartext is
/// allowed (debug builds, for the mock-server smoke test on the emulator).
const Set<String> loopbackHosts = {'127.0.0.1', 'localhost', '10.0.2.2'};

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
    text = (allowCleartext && loopbackHosts.contains(hostPart))
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

/// Canonical text form of an origin (`https://host:10500`).
String originKey(Uri origin) =>
    '${origin.scheme}://${origin.host}:${origin.port}';

/// Display form: drops the default port.
String displayAddress(Uri origin) {
  if (origin.scheme == 'https' && origin.port == defaultRemotePort) {
    return origin.host;
  }
  return '${origin.host}:${origin.port}';
}

/// Content of a `madalean://pair?host=…&code=…` link.
@immutable
class PairLink {
  const PairLink({required this.host, this.code});

  /// Host as written in the link (`name.tailnet.ts.net[:port]`).
  final String host;

  /// Six-digit code, or null if absent/invalid.
  final String? code;

  @override
  bool operator ==(Object other) =>
      other is PairLink && other.host == host && other.code == code;
  @override
  int get hashCode => Object.hash(host, code);
}

final RegExp _sixDigits = RegExp(r'^\d{6}$');

/// True if [code] is exactly six ASCII digits.
bool isValidCode(String code) => _sixDigits.hasMatch(code);

/// Parses a pair link (also accepts it embedded in pasted text).
/// Returns null when the text holds no usable `madalean://pair` link.
PairLink? parsePairLink(String text) {
  final match = RegExp(
    r'madalean://pair\?\S+',
    caseSensitive: false,
  ).firstMatch(text.trim());
  if (match == null) return null;
  final Uri uri;
  try {
    uri = Uri.parse(match.group(0)!);
  } on FormatException {
    return null;
  }
  final host = (uri.queryParameters['host'] ?? '').trim();
  if (host.isEmpty || host.contains('/') || host.contains('@')) return null;
  final code = (uri.queryParameters['code'] ?? '').trim();
  return PairLink(host: host, code: isValidCode(code) ? code : null);
}

/// Origin of a pair-link host, using the contract's scheme rule: `https`
/// (port 10500 by default) except loopback hosts, which use `http`.
Uri pairLinkOrigin(PairLink link, {bool allowCleartext = false}) {
  final hostOnly = link.host.split(':').first.toLowerCase();
  final prefix = loopbackHosts.contains(hostOnly) ? 'http://' : 'https://';
  return normaliseAddress(
    '$prefix${link.host}',
    allowCleartext: allowCleartext,
  );
}
