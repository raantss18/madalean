import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:madalean_shell/src/api.dart';

final Uri origin = Uri.parse('https://h.t.ts.net:10500');

http.Response j(Object body, int status, {Map<String, String>? headers}) =>
    http.Response(
      jsonEncode(body),
      status,
      headers: {'content-type': 'application/json', ...?headers},
    );

Matcher fails(ApiFailure f) =>
    throwsA(isA<ApiException>().having((e) => e.failure, 'failure', f));

void main() {
  test('hello sends Bearer when given and parses fields', () async {
    late http.Request seen;
    final api = MadaleanApi(
      MockClient((r) async {
        seen = r;
        return j({
          'name': 'madalean',
          'version': '2.0.0',
          'paired': true,
          'local': false,
          'host_name': 'pc',
        }, 200);
      }),
    );
    final h = await api.hello(origin, token: 'tok');
    expect(seen.url.toString(), 'https://h.t.ts.net:10500/api/hello');
    expect(seen.headers['Authorization'], 'Bearer tok');
    expect(h.paired, isTrue);
    expect(h.hostName, 'pc');
    await api.hello(origin);
    expect(seen.headers.containsKey('Authorization'), isFalse);
  });

  test('hello: not madalean / unreachable / 5xx', () async {
    final other = MadaleanApi(MockClient((r) async => j({'name': 'x'}, 200)));
    await expectLater(other.hello(origin), fails(ApiFailure.notMadalean));
    final down = MadaleanApi(
      MockClient((r) async => throw http.ClientException('refused')),
    );
    await expectLater(down.hello(origin), fails(ApiFailure.unreachable));
    final err = MadaleanApi(MockClient((r) async => http.Response('', 502)));
    await expectLater(err.hello(origin), fails(ApiFailure.unreachable));
  });

  test('pair 200 / 401 / 429 / 400', () async {
    late http.Request seen;
    var status = 200;
    final api = MadaleanApi(
      MockClient((r) async {
        seen = r;
        return switch (status) {
          200 => j({'token': 'A' * 43, 'device_id': 'd1'}, 200),
          401 => j({'error': 'bad_code'}, 401),
          403 => j({'error': 'expired', 'message': 'x'}, 403),
          201 => j({
            'token': 'B' * 43,
            'device': {'id': 'dv9', 'name': 'x'},
          }, 200),
          430 => j({'error': 'rate_limited'}, 429),
          429 => j(
            {'error': 'locked', 'retry_after': 600},
            429,
            headers: {'retry-after': '599'},
          ),
          _ => j({'error': 'bad_request'}, 400),
        };
      }),
    );
    final r = await api.pair(origin, code: '123456', deviceName: 'Pixel');
    expect(r.token, 'A' * 43);
    expect(r.deviceId, 'd1');
    expect(seen.method, 'POST');
    expect(seen.url.path, '/api/pair');
    expect(jsonDecode(seen.body), {'code': '123456', 'device_name': 'Pixel', 'client': 'app-android'});
    expect(seen.headers['Authorization'], isNull);

    status = 401;
    await expectLater(
      api.pair(origin, code: '000000', deviceName: 'x'),
      fails(ApiFailure.badCode),
    );
    // Shapes of the current server (docs/API.md): 403, device object, rate_limited.
    status = 403;
    await expectLater(
      api.pair(origin, code: '000000', deviceName: 'x'),
      fails(ApiFailure.badCode),
    );
    status = 201;
    expect(
      (await api.pair(origin, code: '123456', deviceName: 'x')).deviceId,
      'dv9',
    );
    status = 430;
    await expectLater(
      api.pair(origin, code: '000000', deviceName: 'x'),
      throwsA(
        isA<ApiException>().having((e) => e.retryAfter, 'retry', 60),
      ),
    );
    status = 429;
    await expectLater(
      api.pair(origin, code: '000000', deviceName: 'x'),
      throwsA(
        isA<ApiException>()
            .having((e) => e.failure, 'f', ApiFailure.locked)
            .having((e) => e.retryAfter, 'retry', 599),
      ),
    );
    status = 400;
    await expectLater(
      api.pair(origin, code: '000000', deviceName: 'x'),
      fails(ApiFailure.protocol),
    );
  });

  test('ticket uses Bearer; 401 = unauthorized; session URL', () async {
    late http.Request seen;
    var ok = true;
    final api = MadaleanApi(
      MockClient((r) async {
        seen = r;
        return ok
            ? j({'ticket': 'tkt', 'expires_in': 60}, 200)
            : j({'error': 'unauthorized'}, 401);
      }),
    );
    expect(await api.ticket(origin, 'tok'), 'tkt');
    expect(seen.method, 'POST');
    expect(seen.url.path, '/api/session/ticket');
    expect(seen.headers['Authorization'], 'Bearer tok');
    ok = false;
    await expectLater(
      api.ticket(origin, 'tok'),
      fails(ApiFailure.unauthorized),
    );
    expect(
      sessionUrl(origin, 'a+b/c').toString(),
      'https://h.t.ts.net:10500/api/session?ticket=a%2Bb%2Fc&next=%2F',
    );
  });

  test('Content-Disposition filenames are sanitised', () {
    expect(
      filenameFromDisposition('attachment; filename="theoreme-demo.pdf"'),
      'theoreme-demo.pdf',
    );
    expect(
      filenameFromDisposition(
        "attachment; filename*=UTF-8''th%C3%A9or%C3%A8me.pdf",
      ),
      'théorème.pdf',
    );
    expect(
      filenameFromDisposition('attachment; filename="../../etc/passwd"'),
      'passwd',
    );
    expect(filenameFromDisposition('attachment; filename=".."'), isNull);
    expect(filenameFromDisposition(null), isNull);
  });
}
