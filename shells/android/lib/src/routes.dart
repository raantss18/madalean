/// Ways to reach one host (pure logic, unit-tested): its tailnet name over
/// HTTPS, the same HTTPS name through its tailnet IP (when MagicDNS does not
/// resolve), and its LAN listener over plain HTTP.
library;

import 'package:flutter/foundation.dart';
import 'package:madalean_shell/src/address.dart';

enum RouteKind {
  /// `https://<name>` resolved by DNS (MagicDNS).
  name,

  /// `https://<name>`, TCP to the tailnet IP; TLS still checked for the name.
  tailnetIp,

  /// `http://<LAN IPv4>:<port>` (LAN listener).
  lan,
}

@immutable
class ServerRoute {
  const ServerRoute(this.kind, this.origin, {this.ip});

  final RouteKind kind;

  /// Origin the app and the web view talk to.
  final Uri origin;

  /// Tailnet IP to connect to ([RouteKind.tailnetIp] only).
  final String? ip;

  /// Stable id, remembered as the preferred route of a saved server.
  String get id => switch (kind) {
    RouteKind.name => 'name',
    RouteKind.tailnetIp => 'ip',
    RouteKind.lan => 'lan:${origin.host}:${origin.port}',
  };

  bool get encrypted => kind != RouteKind.lan;

  @override
  bool operator ==(Object other) =>
      other is ServerRoute &&
      other.kind == kind &&
      other.origin == origin &&
      other.ip == ip;
  @override
  int get hashCode => Object.hash(kind, origin, ip);

  @override
  String toString() => 'ServerRoute($id)';
}

/// Candidate routes, in the order they are tried: encrypted routes first
/// (the name, then its tailnet IP), then the LAN listener; within each group
/// the route that worked last time ([preferred]) comes first.
List<ServerRoute> candidateRoutes(
  Uri origin, {
  String? ip,
  List<String> lan = const [],
  String? preferred,
}) {
  final tls = <ServerRoute>[];
  final plain = <ServerRoute>[];
  if (origin.scheme == 'https') {
    tls.add(ServerRoute(RouteKind.name, origin));
    if (ip != null && isTailnetIPv4(ip) && !isTailnetIPv4(origin.host)) {
      tls.add(ServerRoute(RouteKind.tailnetIp, origin, ip: ip));
    }
  } else if (isLanIPv4(origin.host)) {
    plain.add(ServerRoute(RouteKind.lan, origin));
  } else {
    // Loopback (debug builds, mock server).
    tls.add(ServerRoute(RouteKind.name, origin));
  }
  for (final l in lan) {
    final hp = parseLanHostPort(l);
    if (hp == null) continue;
    final i = hp.lastIndexOf(':');
    final r = ServerRoute(
      RouteKind.lan,
      Uri(
        scheme: 'http',
        host: hp.substring(0, i),
        port: int.parse(hp.substring(i + 1)),
      ),
    );
    if (!plain.contains(r)) plain.add(r);
  }
  int rank(ServerRoute r) => r.id == preferred ? 0 : 1;
  // List.sort is not stable: sort on (rank, original index).
  List<ServerRoute> order(List<ServerRoute> l) {
    final idx = {for (var i = 0; i < l.length; i++) l[i]: i};
    return [...l]..sort((a, b) {
      final c = rank(a).compareTo(rank(b));
      return c != 0 ? c : idx[a]!.compareTo(idx[b]!);
    });
  }

  return [...order(tls), ...order(plain)];
}
