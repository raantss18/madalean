/// Saved servers (no secrets, shared_preferences) and device tokens
/// (flutter_secure_storage = Android Keystore-backed encryption).
library;

import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:madalean_shell/src/address.dart';
import 'package:shared_preferences/shared_preferences.dart';

class SavedServer {
  const SavedServer({
    required this.origin,
    required this.hostName,
    required this.deviceName,
    required this.lastUsed,
    this.ip,
    this.lan = const [],
    this.route,
  });

  factory SavedServer.fromJson(Map<String, dynamic> j) => SavedServer(
    origin: Uri.parse(j['origin'] as String),
    hostName: (j['host_name'] as String?) ?? '',
    deviceName: (j['device_name'] as String?) ?? '',
    lastUsed: DateTime.fromMillisecondsSinceEpoch(
      (j['last_used'] as int?) ?? 0,
    ),
    ip: j['ip'] is String && isTailnetIPv4(j['ip'] as String)
        ? j['ip'] as String
        : null,
    lan: [
      if (j['lan'] is List)
        for (final l in j['lan'] as List<dynamic>)
          if (l is String) ?parseLanHostPort(l),
    ],
    route: j['route'] as String?,
  );

  /// Canonical origin (key of the token): the tailnet name, or the LAN
  /// address for a host without one.
  final Uri origin;
  final String hostName;
  final String deviceName;
  final DateTime lastUsed;

  /// Fallbacks from the pairing QR code: tailnet IPv4, LAN listener(s).
  final String? ip;
  final List<String> lan;

  /// Id of the route that worked last time (see routes.dart).
  final String? route;

  String get key => originKey(origin);

  Map<String, dynamic> toJson() => {
    'origin': key,
    'host_name': hostName,
    'device_name': deviceName,
    'last_used': lastUsed.millisecondsSinceEpoch,
    if (ip != null) 'ip': ip,
    if (lan.isNotEmpty) 'lan': lan,
    if (route != null) 'route': route,
  };

  SavedServer copyWith({String? hostName, DateTime? lastUsed, String? route}) =>
      SavedServer(
        origin: origin,
        hostName: hostName ?? this.hostName,
        deviceName: deviceName,
        lastUsed: lastUsed ?? this.lastUsed,
        ip: ip,
        lan: lan,
        route: route ?? this.route,
      );
}

/// Ordered list of saved servers, most recently used first (pure logic).
class ServerList {
  ServerList([List<SavedServer> servers = const []])
    : _servers = [...servers]..sort((a, b) => b.lastUsed.compareTo(a.lastUsed));

  factory ServerList.decode(String? raw) {
    if (raw == null || raw.isEmpty) return ServerList();
    try {
      final list = jsonDecode(raw) as List<dynamic>;
      return ServerList([
        for (final e in list)
          if (e is Map<String, dynamic> && e['origin'] is String)
            SavedServer.fromJson(e),
      ]);
    } on Object {
      return ServerList();
    }
  }

  final List<SavedServer> _servers;

  List<SavedServer> get servers => List.unmodifiable(_servers);
  SavedServer? get lastUsed => _servers.isEmpty ? null : _servers.first;

  SavedServer? find(Uri origin) {
    final k = originKey(origin);
    for (final s in _servers) {
      if (s.key == k) return s;
    }
    return null;
  }

  /// Inserts or replaces (same origin) and moves it to the front.
  ServerList upsert(SavedServer server) => ServerList([
    for (final s in _servers)
      if (s.key != server.key) s,
    server,
  ]);

  ServerList remove(Uri origin) => ServerList([
    for (final s in _servers)
      if (s.key != originKey(origin)) s,
  ]);

  String encode() => jsonEncode([for (final s in _servers) s.toJson()]);
}

/// Where device tokens live. Never logged, never in shared_preferences.
abstract class TokenStore {
  Future<String?> read(Uri origin);
  Future<void> write(Uri origin, String token);
  Future<void> delete(Uri origin);
}

String _tokenKey(Uri origin) => 'token:${originKey(origin)}';

class SecureTokenStore implements TokenStore {
  SecureTokenStore([FlutterSecureStorage? storage])
    : _s = storage ?? const FlutterSecureStorage();
  final FlutterSecureStorage _s;

  @override
  Future<String?> read(Uri origin) => _s.read(key: _tokenKey(origin));
  @override
  Future<void> write(Uri origin, String token) =>
      _s.write(key: _tokenKey(origin), value: token);
  @override
  Future<void> delete(Uri origin) => _s.delete(key: _tokenKey(origin));
}

class MemoryTokenStore implements TokenStore {
  final Map<String, String> values = {};
  @override
  Future<String?> read(Uri origin) async => values[_tokenKey(origin)];
  @override
  Future<void> write(Uri origin, String token) async =>
      values[_tokenKey(origin)] = token;
  @override
  Future<void> delete(Uri origin) async => values.remove(_tokenKey(origin));
}

/// Persistence of the server list and of the UI language choice.
abstract class Prefs {
  Future<String?> getString(String key);
  Future<void> setString(String key, String value);
}

class SharedPrefs implements Prefs {
  final SharedPreferencesAsync _p = SharedPreferencesAsync();
  @override
  Future<String?> getString(String key) => _p.getString(key);
  @override
  Future<void> setString(String key, String value) => _p.setString(key, value);
}

class MemoryPrefs implements Prefs {
  final Map<String, String> values = {};
  @override
  Future<String?> getString(String key) async => values[key];
  @override
  Future<void> setString(String key, String value) async => values[key] = value;
}
