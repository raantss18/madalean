import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:madalean_shell/src/api.dart';
import 'package:madalean_shell/src/connect_screen.dart';
import 'package:madalean_shell/src/controller.dart';
import 'package:madalean_shell/src/storage.dart';
import 'package:madalean_shell/src/strings.dart';

ShellController controller() => ShellController(
  api: MadaleanApi(
    MockClient(
      (r) async =>
          throw http.ClientException("Failed host lookup: '${r.url.host}'"),
    ),
  ),
  tokens: MemoryTokenStore(),
  prefs: MemoryPrefs(),
  defaultDeviceName: 'Poco F8 Pro',
  allowCleartext: false,
);

Widget app(ShellController c, {Future<String> Function()? openTailscale}) =>
    ListenableBuilder(
      listenable: c,
      builder: (_, _) => MaterialApp(
        home: switch (c.state) {
          final ConnectState st => ConnectScreen(
            controller: c,
            state: st,
            openTailscale: openTailscale,
          ),
          final UnreachableState st => UnreachableScreen(
            controller: c,
            state: st,
            openTailscale: openTailscale,
          ),
          _ => const SizedBox(),
        },
      ),
    );

void main() {
  testWidgets('French by default; scanning is the primary action', (t) async {
    final c = controller();
    await c.init();
    await t.pumpWidget(app(c));
    expect(find.text('Scanner le QR code'), findsOneWidget);
    expect(find.text('Ou saisir l’adresse et le code'), findsOneWidget);
    // The scan button comes before the manual form.
    final scanY = t.getTopLeft(find.byKey(const Key('scan'))).dy;
    final formY = t.getTopLeft(find.byType(TextField).first).dy;
    expect(scanY, lessThan(formY));
    // The selector shows the *current* language.
    expect(find.text('Français'), findsOneWidget);
    await t.tap(find.text('Français'));
    await t.pumpAndSettle();
    await t.tap(find.byType(CheckedPopupMenuItem<Lang>).last);
    await t.pumpAndSettle();
    expect(find.text('Scan the QR code'), findsOneWidget);
    expect(find.text('English'), findsOneWidget);
  });

  testWidgets('Tailscale off: French message and « Ouvrir Tailscale »', (
    t,
  ) async {
    var opened = 0;
    final c = controller();
    await c.init();
    await t.pumpWidget(
      app(
        c,
        openTailscale: () async {
          opened++;
          return 'app';
        },
      ),
    );
    await c.scanned('https://madalean.tail804764.ts.net/pair?code=123456');
    await t.pumpAndSettle();
    expect(
      find.text(
        'Tailscale n’est pas connecté sur ce téléphone. Ouvrez l’app '
        'Tailscale et activez-la, puis réessayez.',
      ),
      findsOneWidget,
    );
    await t.tap(find.text('Ouvrir Tailscale'));
    expect(opened, 1);
  });

  testWidgets('unreachable screen explains the failure', (t) async {
    final c = controller();
    await c.init();
    final server = SavedServer(
      origin: Uri.parse('https://pc.tail.ts.net'),
      hostName: 'pc',
      deviceName: 'x',
      lastUsed: DateTime(2026),
    );
    await t.pumpWidget(
      MaterialApp(
        home: UnreachableScreen(
          controller: c,
          state: UnreachableState(
            server: server,
            net: NetError.refused,
            detail: 'Connection refused',
          ),
        ),
      ),
    );
    expect(
      find.text(
        'L’ordinateur refuse la connexion. Vérifiez que Madalean est lancé.',
      ),
      findsOneWidget,
    );
    expect(find.text('Ouvrir Tailscale'), findsNothing);
    expect(find.text('Réessayer'), findsOneWidget);
  });
}
