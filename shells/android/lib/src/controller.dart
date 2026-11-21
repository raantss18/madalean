/// Shell state machine: connect → (pair) → ticket → web view, plus
/// revocation, unreachable server and resume handling. UI-free and tested.
library;

import 'package:flutter/foundation.dart';
import 'package:madalean_shell/src/address.dart';
import 'package:madalean_shell/src/api.dart';
import 'package:madalean_shell/src/storage.dart';
import 'package:madalean_shell/src/strings.dart';

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
  });

  /// Error / information line (localised lazily).
  final Msg? message;

  /// Prefilled address and code (from the last server or a pair link).
  final String address;
  final String code;
  final bool busy;

  /// Bumped when the prefill changes so the form re-reads it.
  final int revision;
}

class WebState extends ShellState {
  const WebState({required this.server, required this.url, required this.n});
  final SavedServer server;

  /// `…/api/session?ticket=…` (single use, 60 s).
  final Uri url;

  /// Load counter, forces a new web view load even with the same server.
  final int n;
}

class UnreachableState extends ShellState {
  const UnreachableState({required this.server, this.detail});
  final SavedServer server;
  final String? detail;
}

const _kServers = 'servers';
const _kLang = 'lang';

class ShellController extends ChangeNotifier {
  ShellController({
    required this.api,
    required this.tokens,
    required this.prefs,
    required this.defaultDeviceName,
    required this.allowCleartext,
    Lang? systemLang,
    DateTime Function()? now,
  }) : lang = systemLang ?? Lang.fr,
       _now = now ?? DateTime.now;

  final MadaleanApi api;
  final TokenStore tokens;
  final Prefs prefs;
  final String defaultDeviceName;
  final bool allowCleartext;
  final DateTime Function() _now;

  Lang lang;
  ServerList servers = ServerList();
  ShellState state = const LoadingState();
  int _loads = 0;
  int _rev = 0;
  DateTime? _pausedAt;

  S get s => S(lang);

  void _set(ShellState st) {
    state = st;
    notifyListeners();
  }

  Future<void> init({String? initialLink}) async {
    final l = await prefs.getString(_kLang);
    if (l == 'en') lang = Lang.en;
    if (l == 'fr') lang = Lang.fr;
    servers = ServerList.decode(await prefs.getString(_kServers));
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

  Future<void> setLang(Lang l) async {
    lang = l;
    await prefs.setString(_kLang, l.name);
    notifyListeners();
  }

  void _connect({Msg? message, String? address, String code = ''}) {
    final last = servers.lastUsed;
    _set(
      ConnectState(
        message: message,
        address: address ?? (last == null ? '' : displayAddress(last.origin)),
        code: code,
        revision: ++_rev,
      ),
    );
  }

  /// "Change server" (from the bridge, the unreachable screen, back button).
  void changeServer() => _connect();

  /// A `madalean://pair?...` link (deep link or pasted).
  bool handleLink(String text) {
    final link = parsePairLink(text);
    if (link == null) return false;
    try {
      final origin = pairLinkOrigin(link, allowCleartext: allowCleartext);
      _connect(
        address: origin.scheme == 'http'
            ? originKey(origin)
            : displayAddress(origin),
        code: link.code ?? '',
      );
    } on AddressException catch (e) {
      _connect(message: _addressMsg(e.error), address: link.host);
    }
    return true;
  }

  Msg _addressMsg(AddressError e) => switch (e) {
    AddressError.empty => (s) => s.errEmpty,
    AddressError.invalid => (s) => s.errInvalid,
    AddressError.cleartextForbidden => (s) => s.errCleartext,
    AddressError.needFullName => (s) => s.errFullName,
  };

  Msg _apiMsg(ApiException e) => switch (e.failure) {
    ApiFailure.unreachable =>
      (s) =>
          '${s.unreachableTitle}.'
          '${e.detail != null ? ' (${e.detail})' : ''}',
    ApiFailure.notMadalean => (s) => s.errNotMadalean,
    ApiFailure.badCode => (s) => s.errBadCode,
    ApiFailure.locked => (s) => s.errLocked(e.retryAfter),
    ApiFailure.unauthorized => (s) => s.revoked,
    ApiFailure.protocol =>
      (s) =>
          '${s.errProtocol}'
          '${e.detail != null ? ' (${e.detail})' : ''}',
  };

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
    try {
      final hello = await api.hello(origin);
      final r = await api.pair(origin, code: c, deviceName: name);
      await tokens.write(origin, r.token);
      final server = SavedServer(
        origin: origin,
        hostName: hello.hostName,
        deviceName: name,
        lastUsed: _now(),
      );
      await _saveServer(server);
      await openServer(server);
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
          address: displayAddress(server.origin),
          busy: true,
          revision: _rev,
        ),
      );
    }
    try {
      final hello = await api.hello(server.origin, token: token);
      if (!hello.paired) {
        await _revoked(server);
        return;
      }
      final ticket = await api.ticket(server.origin, token);
      await _saveServer(
        server.copyWith(hostName: hello.hostName, lastUsed: _now()),
      );
      _set(
        WebState(
          server: servers.find(server.origin)!,
          url: sessionUrl(server.origin, ticket),
          n: ++_loads,
        ),
      );
    } on ApiException catch (e) {
      switch (e.failure) {
        case ApiFailure.unauthorized:
          await _revoked(server);
        case ApiFailure.unreachable:
          _set(UnreachableState(server: server, detail: e.detail));
        case ApiFailure.notMadalean ||
            ApiFailure.protocol ||
            ApiFailure.badCode ||
            ApiFailure.locked:
          _connect(message: _apiMsg(e), address: displayAddress(server.origin));
      }
    }
  }

  Future<void> _revoked(SavedServer server) async {
    await tokens.delete(server.origin);
    _connect(message: (s) => s.revoked, address: displayAddress(server.origin));
  }

  /// The web view navigated to `<origin>/pair…` (401 in the web UI, expired
  /// cookie, bad ticket): new session if the token is valid, else pairing.
  Future<void> reauth() async {
    final st = state;
    if (st is WebState) await openServer(st.server);
  }

  /// The main frame failed to load (network lost).
  void webLoadFailed(String detail) {
    final st = state;
    if (st is WebState) {
      _set(UnreachableState(server: st.server, detail: detail));
    }
  }

  Future<void> retry() async {
    final st = state;
    if (st is UnreachableState) await openServer(st.server);
  }

  Future<void> forgetServer(SavedServer server) async {
    final token = await tokens.read(server.origin);
    if (token != null) await api.forget(server.origin, token);
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
      final hello = await api.hello(st.server.origin, token: token);
      if (!hello.paired) await _revoked(st.server);
    } on ApiException catch (e) {
      if (e.failure == ApiFailure.unreachable) {
        _set(UnreachableState(server: st.server, detail: e.detail));
      }
    }
  }

  /// Token for native re-downloads of exports (Bearer).
  Future<String?> currentToken() async {
    final st = state;
    return st is WebState ? await tokens.read(st.server.origin) : null;
  }
}
