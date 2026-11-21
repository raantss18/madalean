/// HTTP client for the shell-facing endpoints (docs/SHELLS.md, "Required
/// server endpoints"). Pure Dart, tested against a fake `http.Client`.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

/// Response of `GET /api/hello`.
class Hello {
  const Hello({
    required this.version,
    required this.paired,
    required this.local,
    required this.hostName,
  });
  final String version;
  final bool paired;
  final bool local;
  final String hostName;
}

/// Failure categories the UI knows how to explain.
enum ApiFailure {
  /// Network error, timeout, TLS failure, 5xx.
  unreachable,

  /// Something answered, but it is not a Madalean server.
  notMadalean,

  /// 401 on /api/pair.
  badCode,

  /// 429 on /api/pair (see [ApiException.retryAfter]).
  locked,

  /// 401 on an authenticated call: token revoked.
  unauthorized,

  /// Anything else (400, unexpected JSON…).
  protocol,
}

class ApiException implements Exception {
  const ApiException(this.failure, {this.retryAfter, this.detail});
  final ApiFailure failure;

  /// Seconds before pairing may be retried (429).
  final int? retryAfter;

  /// Technical detail for the "details" line (never contains secrets).
  final String? detail;
  @override
  String toString() => 'ApiException($failure, $detail)';
}

/// Result of a successful `POST /api/pair`.
class PairResult {
  const PairResult({required this.token, this.deviceId});
  final String token;
  final String? deviceId;
}

class MadaleanApi {
  MadaleanApi(this._client, {this.timeout = const Duration(seconds: 10)});
  final http.Client _client;
  final Duration timeout;

  Map<String, String> _headers(String? token, {bool json = false}) => {
    'Accept': 'application/json',
    if (json) 'Content-Type': 'application/json',
    if (token != null) 'Authorization': 'Bearer $token',
  };

  Future<http.Response> _send(Future<http.Response> Function() call) async {
    try {
      final r = await call().timeout(timeout);
      if (r.statusCode >= 500) {
        throw ApiException(
          ApiFailure.unreachable,
          detail: 'HTTP ${r.statusCode}',
        );
      }
      return r;
    } on ApiException {
      rethrow;
    } on TimeoutException {
      throw const ApiException(ApiFailure.unreachable, detail: 'timeout');
    } on HandshakeException catch (e) {
      throw ApiException(ApiFailure.unreachable, detail: 'TLS: ${e.message}');
    } on SocketException catch (e) {
      throw ApiException(ApiFailure.unreachable, detail: e.message);
    } on http.ClientException catch (e) {
      throw ApiException(ApiFailure.unreachable, detail: e.message);
    }
  }

  Map<String, dynamic>? _json(http.Response r) {
    try {
      final v = jsonDecode(utf8.decode(r.bodyBytes));
      return v is Map<String, dynamic> ? v : null;
    } on FormatException {
      return null;
    }
  }

  /// `GET /api/hello`, optionally with the Bearer token (revocation check).
  Future<Hello> hello(Uri origin, {String? token}) async {
    final r = await _send(
      () => _client.get(
        origin.replace(path: '/api/hello'),
        headers: _headers(token),
      ),
    );
    final j = _json(r);
    if (r.statusCode != 200 || j == null || j['name'] != 'madalean') {
      throw ApiException(
        ApiFailure.notMadalean,
        detail: 'HTTP ${r.statusCode}',
      );
    }
    return Hello(
      version: '${j['version'] ?? ''}',
      paired: j['paired'] == true,
      local: j['local'] == true,
      hostName: '${j['host_name'] ?? ''}',
    );
  }

  /// `POST /api/pair {code, device_name}`.
  Future<PairResult> pair(
    Uri origin, {
    required String code,
    required String deviceName,
  }) async {
    final r = await _send(
      () => _client.post(
        origin.replace(path: '/api/pair'),
        headers: _headers(null, json: true),
        body: jsonEncode({'code': code, 'device_name': deviceName}),
      ),
    );
    final j = _json(r);
    switch (r.statusCode) {
      case 200:
        final token = j?['token'];
        if (token is! String || token.length < 16) {
          throw const ApiException(ApiFailure.protocol, detail: 'no token');
        }
        final dev = j?['device'];
        return PairResult(
          token: token,
          deviceId:
              (j?['device_id'] ??
                      (dev is Map<String, dynamic> ? dev['id'] : null))
                  as String?,
        );
      // 401 bad_code (contract) or 403 wrong/expired/no_code (current server).
      case 401 || 403:
        throw const ApiException(ApiFailure.badCode);
      case 429:
        final ra =
            int.tryParse(r.headers['retry-after'] ?? '') ??
            (j?['retry_after'] is int ? j!['retry_after'] as int : null) ??
            (j?['error'] == 'rate_limited' ? 60 : null);
        throw ApiException(ApiFailure.locked, retryAfter: ra);
      default:
        throw ApiException(ApiFailure.protocol, detail: 'HTTP ${r.statusCode}');
    }
  }

  /// `POST /api/session/ticket` with Bearer → one-time ticket.
  Future<String> ticket(Uri origin, String token) async {
    final r = await _send(
      () => _client.post(
        origin.replace(path: '/api/session/ticket'),
        headers: _headers(token),
      ),
    );
    if (r.statusCode == 401) {
      throw const ApiException(ApiFailure.unauthorized);
    }
    final t = _json(r)?['ticket'];
    if (r.statusCode != 200 || t is! String || t.isEmpty) {
      throw ApiException(ApiFailure.protocol, detail: 'HTTP ${r.statusCode}');
    }
    return t;
  }

  /// Ask the server to revoke this device (best effort): optional
  /// `POST /api/devices/self/forget`, else the current server's
  /// `POST /api/logout` with Bearer.
  Future<void> forget(Uri origin, String token) async {
    try {
      final r = await _send(
        () => _client.post(
          origin.replace(path: '/api/devices/self/forget'),
          headers: _headers(token),
        ),
      );
      if (r.statusCode == 404 || r.statusCode == 405) {
        await _send(
          () => _client.post(
            origin.replace(path: '/api/logout'),
            headers: _headers(token),
          ),
        );
      }
    } on ApiException {
      // Best effort: the token is deleted locally anyway.
    }
  }

  /// Authenticated download of an export (Bearer), returns body + headers.
  Future<http.Response> download(Uri url, String? token) => _send(
    () => _client.get(
      url,
      headers: {if (token != null) 'Authorization': 'Bearer $token'},
    ),
  );
}

/// URL the web view loads to swap the ticket for the HttpOnly cookie.
Uri sessionUrl(Uri origin, String ticket, {String next = '/'}) =>
    origin.replace(
      path: '/api/session',
      queryParameters: {'ticket': ticket, 'next': next},
    );

/// Filename from a Content-Disposition header (`filename*=` or `filename=`),
/// sanitised (no path separators, no control characters).
String? filenameFromDisposition(String? header) {
  if (header == null) return null;
  String? name;
  final star = RegExp(
    r"filename\*\s*=\s*([^']*)'[^']*'([^;]+)",
    caseSensitive: false,
  ).firstMatch(header);
  if (star != null) {
    try {
      name = Uri.decodeComponent(star.group(2)!.trim());
    } on Object {
      name = null;
    }
  }
  if (name == null) {
    final plain = RegExp(
      r'filename\s*=\s*("([^"]*)"|[^;]+)',
      caseSensitive: false,
    ).firstMatch(header);
    name = plain?.group(2) ?? plain?.group(1)?.trim();
  }
  return name == null ? null : sanitiseFilename(name);
}

/// Keeps only a safe base name.
String? sanitiseFilename(String name) {
  var n = name.split(RegExp(r'[/\\]')).last;
  n = n.replaceAll(RegExp(r'[\x00-\x1f<>:"|?*]'), '_').trim();
  if (n.isEmpty || n == '.' || n == '..') return null;
  return n.length > 120 ? n.substring(n.length - 120) : n;
}
