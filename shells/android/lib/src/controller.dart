/// Shell state machine: connect → (pair) → ticket → web view, plus
/// revocation, unreachable server and resume handling. UI-free and tested.
library;

import 'package:flutter/foundation.dart';
import 'package:madalean_shell/src/address.dart';
import 'package:madalean_shell/src/api.dart';
import 'package:madalean_shell/src/routes.dart';
import 'package:madalean_shell/src/storage.dart';
import 'package:madalean_shell/src/strings.dart';
import 'package:madalean_shell/src/tunnel.dart';

typedef Msg = String Function(S s);

sealed class ShellState {
  const ShellState();
}

class LoadingState extends ShellState {
  const LoadingState();
}

class ConnectState extends ShellState {
  const ConnectState({
    this.message,
    this.address = '',
    this.code = '',
    this.busy = false,
    this.revision = 0,
    this.tailscale = false,
  });

  /// Error / information line (localised lazily).
  final Msg? message;

  /// The failure means "Tailscale is off on this phone": offer to open it.
  final bool tailscale;

  /// Prefilled address and code (from the last server or a pair link).
  final String address;
  final String code;
  final bool busy;

  /// Bumped when the prefill changes so the form re-reads it.
  final int revision;
}

class WebState extends ShellState {
  WebState({
    required this.server,
    required this.url,
    required this.n,
    Uri? origin,
  }) : origin = origin ?? server.origin;
  final SavedServer server;

  /// Origin actually used (the server's, or a fallback route's: LAN…).
  final Uri origin;

  /// `…/api/session?ticket=…` (single use, 60 s).
  final Uri url;

  /// Load counter, forces a new web view load even with the same server.
  final int n;
}

class UnreachableState extends ShellState {
  const UnreachableState({
    required this.server,
    this.detail,
    this.net,
    this.tailscale = false,
  });
  final SavedServer server;
  final String? detail;

  /// Kind of network failure, when known.
  final NetError? net;

  /// "Tailscale is off on this phone" (name lookup of *.ts.net failed).
  final bool tailscale;
}

/// Every route failed: [primary] is the first route's error (the most
/// meaningful), [tailscale] whether a *.ts.net name did not resolve.
class _Unreached implements Exception {
  const _Unreached(this.primary, {required this.tailscale});
  final ApiException primary;
  final bool tailscale;
}

const _kServers = 'servers';

/// Explicit language choice in the app (key changed in 2.0.1: the former
/// toggle button showed the *other* language and was often hit by mistake).
const _kLang = 'lang_choice';

/// Language last announced by the host (`/api/hello` → `lang`).
const _kHostLang = 'host_lang';

/// Message for a network failure.
String netMessage(S s, NetError? net, {required bool tailscale}) {
  if (tailscale) return s.errTailscale;
  return switch (net) {
    NetError.hostLookup => s.errLookup,
    NetError.refused => s.errRefused,
    NetError.timeout => s.errTimeout,
    NetError.noNetwork => s.errNoNetwork,
    NetError.tls => s.errTls,
    NetError.other || null => s.unreachableTitle,
  };
}

/// True when [e] is a failed DNS lookup of a Tailscale name.
bool isTailscaleLookup(ApiException e, Uri origin) =>
    e.net == NetError.hostLookup && origin.host.endsWith('.ts.net');

class ShellController extends ChangeNotifier {
  ShellController({
    required this.api,
    required this.tokens,
    required this.prefs,
    required this.defaultDeviceName,
    required this.allowCleartext,
    Tunnels? tunnels,
    this.probeTimeout = const Duration(seconds: 4),
    DateTime Function()? now,
  }) : tunnels = tunnels ?? const NoTunnels(),
       _now = now ?? DateTime.now;

  final MadaleanApi api;
  final TokenStore tokens;
  final Prefs prefs;
  final String defaultDeviceName;
  final bool allowCleartext;
  final Tunnels tunnels;

  /// Per-route timeout of `hello` while several routes are tried.
  final Duration probeTimeout;
  final DateTime Function() _now;

  /// French by default; the host's language once known; the user's explicit
  /// choice wins.
  Lang lang = Lang.fr;
  bool _langChosen = false;

  /// Fallbacks of the last pairing link (tailnet IP, LAN listeners).
  PairLink? _link;
  ServerList servers = ServerList();
  ShellState state = const LoadingState();
  int _loads = 0;
  int _rev = 0;
  DateTime? _pausedAt;
  final List<DateTime> _reauths = [];

  S get s => S(lang);

  void _set(ShellState st) {
    state = st;
    notifyListeners();
  }

  Future<void> init({String? initialLink}) async {
    final chosen = _parseLang(await prefs.getString(_kLang));
    final host = _parseLang(await prefs.getString(_kHostLang));
    _langChosen = chosen != null;
    lang = chosen ?? host ?? Lang.fr;
    servers = ServerList.decode(await prefs.getString(_kServers));
    await _migrateLegacyServers();
    if (initialLink != null && parsePairLink(initialLink) != null) {
      handleLink(initialLink);
      return;
    }
    final last = servers.lastUsed;
    if (last != null && await tokens.read(last.origin) != null) {
      await openServer(last);
    } else {
      _connect();
    }
  }

  /// Saved `https://<x>.ts.net:10500` servers (former `tailscale serve`
  /// design) → `https://<x>.ts.net` (embedded tsnet node, 443), token moved.
  Future<void> _migrateLegacyServers() async {
    var changed = false;
    var list = servers;
    for (final s in servers.servers) {
      final to = migrateLegacyOrigin(s.origin);
      if (to == null) continue;
      final t = await tokens.read(s.origin);
      if (t != null) {
        await tokens.write(to, t);
        await tokens.delete(s.origin);
      }
      list = list
          .remove(s.origin)
          .upsert(
            SavedServer(
              origin: to,
              hostName: s.hostName,
              deviceName: s.deviceName,
              lastUsed: s.lastUsed,
            ),
          );
      changed = true;
    }
    if (changed) {
      servers = list;
      await prefs.setString(_kServers, servers.encode());
    }
  }

  static Lang? _parseLang(String? v) => switch (v) {
    'fr' => Lang.fr,
    'en' => Lang.en,
    _ => null,
  };

  Future<void> setLang(Lang l) async {
    lang = l;
    _langChosen = true;
    await prefs.setString(_kLang, l.name);
    notifyListeners();
  }

  /// Follows the host's language unless the user chose one in the app.
  Future<void> _hostLang(Hello h) async {
    final l = _parseLang(h.lang);
    if (l == null) return;
    await prefs.setString(_kHostLang, l.name);
    if (!_langChosen && l != lang) {
      lang = l;
      notifyListeners();
    }
  }

  void _connect({
    Msg? message,
    String? address,
    String code = '',
    bool tailscale = false,
  }) {
    final last = servers.lastUsed;
    _set(
      ConnectState(
        message: message,
        address: address ?? (last == null ? '' : _formAddress(last.origin)),
        code: code,
        revision: ++_rev,
        tailscale: tailscale,
      ),
    );
  }

  static String _formAddress(Uri origin) =>
      origin.scheme == 'http' ? originKey(origin) : displayAddress(origin);

  /// "Change server" (from the bridge, the unreachable screen, back button).
  void changeServer() => _connect();

  /// A `madalean://pair?...` link (deep link or pasted): prefills the form.
  bool handleLink(String text) {
    final link = parsePairLink(text);
    if (link == null) return false;
    try {
      final origin = pairLinkOrigin(link, allowCleartext: allowCleartext);
      _link = link;
      _connect(address: _formAddress(origin), code: link.code ?? '');
    } on AddressException catch (e) {
      _connect(message: _addressMsg(e.error), address: link.host);
    }
    return true;
  }

  /// A scanned QR code: prefills and, when it holds a code, pairs at once.
  /// False when the text is not a Madalean pairing link.
  Future<bool> scanned(String text, {String? deviceName}) async {
    final link = parsePairLink(text);
    if (link == null) return false;
    handleLink(text);
    final st = state;
    if (link.code != null && st is ConnectState && st.message == null) {
      await pair(
        address: st.address,
        code: link.code!,
        deviceName: deviceName ?? '',
      );
    }
    return true;
  }

  Msg _addressMsg(AddressError e) => switch (e) {
    AddressError.empty => (s) => s.errEmpty,
    AddressError.invalid => (s) => s.errInvalid,
    AddressError.cleartextForbidden => (s) => s.errCleartext,
    AddressError.needFullName => (s) => s.errFullName,
  };

  Msg _apiMsg(ApiException e, {bool tailscale = false}) => switch (e.failure) {
    ApiFailure.unreachable => (s) => netMessage(s, e.net, tailscale: tailscale),
    ApiFailure.notMadalean => (s) => s.errNotMadalean,
    ApiFailure.badCode => (s) => s.errBadCode,
    ApiFailure.locked => (s) => s.errLocked(e.retryAfter),
    ApiFailure.unauthorized => (s) => s.revoked,
    ApiFailure.protocol =>
      (s) =>
          '${s.errProtocol}'
          '${e.detail != null ? ' (${e.detail})' : ''}',
  };

  /// Tries the routes of a host in order (short timeouts when there are
  /// several) and returns the first that answers as a Madalean.
  Future<(ServerRoute, Hello)> _reach(
    Uri origin, {
    String? ip,
    List<String> lan = const [],
    String? preferred,
    String? token,
  }) async {
    final routes = candidateRoutes(
      origin,
      ip: ip,
      lan: lan,
      preferred: preferred,
    );
    ApiException? first;
    ApiException? other;
    var tailscale = false;
    for (final r in routes) {
      if (r.kind == RouteKind.tailnetIp) {
        if (!await tunnels.activate(r.origin.host, r.origin.port, r.ip!)) {
          continue;
        }
      } else {
        await tunnels.deactivate();
      }
      try {
        final h = await api.hello(
          r.origin,
          token: token,
          timeout: routes.length > 1 ? probeTimeout : null,
        );
        return (r, h);
      } on ApiException catch (e) {
        if (isTailscaleLookup(e, r.origin)) tailscale = true;
        first ??= e;
        if (e.failure != ApiFailure.unreachable) other ??= e;
      }
    }
    await tunnels.deactivate();
    // A route that answered "not Madalean" says more than a dead one,
    // except the Tailscale case, which has a clear fix.
    final primary = (tailscale ? null : other) ?? first;
    if (primary == null) {
      throw const _Unreached(
        ApiException(ApiFailure.unreachable, net: NetError.other),
        tailscale: false,
      );
    }
    throw _Unreached(primary, tailscale: tailscale);
  }

  /// Validates the form; returns the error to show, or null and proceeds.
  Future<void> pair({
    required String address,
    required String code,
    required String deviceName,
  }) async {
    final Uri origin;
    try {
      origin = normaliseAddress(address, allowCleartext: allowCleartext);
    } on AddressException catch (e) {
      _connect(message: _addressMsg(e.error), address: address, code: code);
      return;
    }
    final c = code.trim();
    if (!isValidCode(c)) {
      _connect(message: (s) => s.errCode, address: address, code: code);
      return;
    }
    final name = deviceName.trim().isEmpty
        ? defaultDeviceName
        : deviceName.trim();
    _set(
      ConnectState(address: address, code: code, busy: true, revision: _rev),
    );
    final link = _link;
    final extras =
        link != null &&
            originKey(pairLinkOrigin(link, allowCleartext: allowCleartext)) ==
                originKey(origin)
        ? link
        : null;
    try {
      final (route, hello) = await _reach(
        origin,
        ip: extras?.ip,
        lan: extras?.lan ?? const [],
      );
      final r = await api.pair(route.origin, code: c, deviceName: name);
      await tokens.write(origin, r.token);
      final server = SavedServer(
        origin: origin,
        hostName: hello.hostName,
        deviceName: name,
        lastUsed: _now(),
        ip: extras?.ip,
        lan: extras?.lan ?? const [],
        route: route.id,
      );
      _link = null;
      await _saveServer(server);
      await _hostLang(hello);
      await openServer(server);
    } on _Unreached catch (u) {
      _connect(
        message: _apiMsg(u.primary, tailscale: u.tailscale),
        address: address,
        code: code,
        tailscale: u.tailscale,
      );
    } on ApiException catch (e) {
      _connect(message: _apiMsg(e), address: address, code: code);
    }
  }

  Future<void> _saveServer(SavedServer server) async {
    servers = servers.upsert(server);
    await prefs.setString(_kServers, servers.encode());
  }

  /// hello (Bearer) → ticket → web view. Handles revocation and errors.
  Future<void> openServer(SavedServer server) async {
    final token = await tokens.read(server.origin);
    if (token == null) {
      _connect(address: displayAddress(server.origin));
      return;
    }
    if (state is! WebState) {
      _set(
        ConnectState(
          address: _formAddress(server.origin),
          busy: true,
          revision: _rev,
        ),
      );
    }
    try {
      final (route, hello) = await _reach(
        server.origin,
        ip: server.ip,
        lan: server.lan,
        preferred: server.route,
        token: token,
      );
      if (!hello.paired) {
        await _revoked(server);
        return;
      }
      final ticket = await api.ticket(route.origin, token);
      await _saveServer(
        server.copyWith(
          hostName: hello.hostName,
          lastUsed: _now(),
          route: route.id,
        ),
      );
      await _hostLang(hello);
      _set(
        WebState(
          server: servers.find(server.origin)!,
          url: sessionUrl(route.origin, ticket),
          n: ++_loads,
          origin: route.origin,
        ),
      );
    } on _Unreached catch (u) {
      final e = u.primary;
      if (e.failure == ApiFailure.unreachable) {
        _set(
          UnreachableState(
            server: server,
            detail: e.detail,
            net: e.net,
            tailscale: u.tailscale,
          ),
        );
      } else {
        _connect(message: _apiMsg(e), address: _formAddress(server.origin));
      }
    } on ApiException catch (e) {
      switch (e.failure) {
        case ApiFailure.unauthorized:
          await _revoked(server);
        case ApiFailure.unreachable:
          _set(UnreachableState(server: server, detail: e.detail, net: e.net));
        case ApiFailure.notMadalean ||
            ApiFailure.protocol ||
            ApiFailure.badCode ||
            ApiFailure.locked:
          _connect(message: _apiMsg(e), address: _formAddress(server.origin));
      }
    }
  }

  Future<void> _revoked(SavedServer server) async {
    await tokens.delete(server.origin);
    _connect(message: (s) => s.revoked, address: _formAddress(server.origin));
  }

  /// The web view navigated to `<origin>/pair…` (401 in the web UI, expired
  /// cookie, bad ticket): new session if the token is valid, else pairing.
  ///
  /// Guard: three re-authentications within a minute mean the server keeps
  /// refusing fresh sessions (e.g. cookies blocked) — stop looping and show
  /// the pairing screen with an explanation instead.
  Future<void> reauth() async {
    final st = state;
    if (st is! WebState) return;
    final now = _now();
    _reauths.removeWhere((t) => now.difference(t).inSeconds > 60);
    _reauths.add(now);
    if (_reauths.length > 3) {
      _reauths.clear();
      _connect(
        message: (s) => s.errProtocol,
        address: _formAddress(st.server.origin),
      );
      return;
    }
    await openServer(st.server);
  }

  /// The main frame failed to load (network lost).
  void webLoadFailed(String detail, {NetError? net}) {
    final st = state;
    if (st is WebState) {
      _set(
        UnreachableState(
          server: st.server,
          detail: detail,
          net: net,
          tailscale:
              net == NetError.hostLookup && st.origin.host.endsWith('.ts.net'),
        ),
      );
    }
  }

  Future<void> retry() async {
    final st = state;
    if (st is UnreachableState) await openServer(st.server);
  }

  Future<void> forgetServer(SavedServer server) async {
    final token = await tokens.read(server.origin);
    final st = state;
    final via = st is WebState && st.server.key == server.key
        ? st.origin
        : server.origin;
    if (token != null) await api.forget(via, token);
    await tokens.delete(server.origin);
    servers = servers.remove(server.origin);
    await prefs.setString(_kServers, servers.encode());
    _connect();
  }

  void paused() => _pausedAt = _now();

  /// After more than 30 s in background, check the server is still there
  /// and this device still paired. The web UI reconnects its WebSocket.
  Future<void> resumed() async {
    final p = _pausedAt;
    _pausedAt = null;
    final st = state;
    if (p == null || _now().difference(p).inSeconds <= 30) return;
    if (st is UnreachableState) {
      await openServer(st.server);
      return;
    }
    if (st is! WebState) return;
    final token = await tokens.read(st.server.origin);
    if (token == null) {
      await _revoked(st.server);
      return;
    }
    try {
      final hello = await api.hello(st.origin, token: token);
      if (!hello.paired) await _revoked(st.server);
    } on ApiException catch (e) {
      // The route in use is gone (left home Wi-Fi, Tailscale switched on…):
      // try the routes again.
      if (e.failure == ApiFailure.unreachable) await openServer(st.server);
    }
  }

  /// Token for native re-downloads of exports (Bearer).
  Future<String?> currentToken() async {
    final st = state;
    return st is WebState ? await tokens.read(st.server.origin) : null;
  }
}
