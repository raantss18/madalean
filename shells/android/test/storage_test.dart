import 'package:flutter_test/flutter_test.dart';
import 'package:madalean_shell/src/storage.dart';

SavedServer srv(String host, int minute) => SavedServer(
  origin: Uri.parse('https://$host:10500'),
  hostName: 'pc',
  deviceName: 'phone',
  lastUsed: DateTime(2026, 1, 1, 0, minute),
);

void main() {
  test('server list: most recent first, upsert replaces, round trip', () {
    var l = ServerList()
        .upsert(srv('a.t.ts.net', 1))
        .upsert(srv('b.t.ts.net', 2))
        .upsert(srv('a.t.ts.net', 3));
    expect(l.servers.map((s) => s.origin.host), ['a.t.ts.net', 'b.t.ts.net']);
    expect(l.lastUsed!.origin.host, 'a.t.ts.net');
    final decoded = ServerList.decode(l.encode());
    expect(decoded.servers.length, 2);
    expect(decoded.find(Uri.parse('https://b.t.ts.net:10500'))!.hostName, 'pc');
    l = l.remove(Uri.parse('https://a.t.ts.net:10500'));
    expect(l.servers.map((s) => s.origin.host), ['b.t.ts.net']);
  });

  test('corrupt preferences do not crash', () {
    expect(ServerList.decode('not json').servers, isEmpty);
    expect(ServerList.decode('[{"x":1}]').servers, isEmpty);
    expect(ServerList.decode(null).servers, isEmpty);
  });

  test('memory token store is keyed by origin', () async {
    final t = MemoryTokenStore();
    final a = Uri.parse('https://a.t.ts.net:10500');
    await t.write(a, 'secret');
    expect(await t.read(a), 'secret');
    expect(await t.read(Uri.parse('https://a.t.ts.net:10501')), isNull);
    await t.delete(a);
    expect(await t.read(a), isNull);
  });
}
