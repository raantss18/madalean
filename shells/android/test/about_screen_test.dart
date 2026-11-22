import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:madalean_shell/src/about_screen.dart';
import 'package:madalean_shell/src/strings.dart';

void main() {
  Widget page(Lang lang, List<Uri> opened, {bool canOpen = true}) =>
      MaterialApp(
        home: AboutScreen(
          strings: S(lang),
          version: '2.0.2',
          openLink: (u) async {
            opened.add(u);
            return canOpen;
          },
        ),
      );

  testWidgets('French: author, contacts, licence and version', (t) async {
    final opened = <Uri>[];
    await t.pumpWidget(page(Lang.fr, opened));
    expect(find.text('À propos'), findsOneWidget);
    expect(find.text('RANIRIAMANJAKA Antsa'), findsOneWidget);
    expect(find.text('Courriel'), findsOneWidget);
    expect(
      find.text('antsa.raniriamanjaka@univ-antananarivo.mg'),
      findsOneWidget,
    );
    expect(find.text('github.com/raantss18'), findsOneWidget);
    expect(find.text('Apache-2.0'), findsOneWidget);
    expect(find.text('2.0.2'), findsOneWidget);

    await t.tap(find.byKey(const Key('about-email')));
    await t.tap(find.byKey(const Key('about-github')));
    expect(opened, [
      Uri.parse('mailto:antsa.raniriamanjaka@univ-antananarivo.mg'),
      Uri.parse('https://github.com/raantss18'),
    ]);
  });

  testWidgets('English labels; copy button and link failure', (t) async {
    final opened = <Uri>[];
    String? copied;
    t.binding.defaultBinaryMessenger.setMockMethodCallHandler(
      SystemChannels.platform,
      (call) async {
        if (call.method == 'Clipboard.setData') {
          copied = (call.arguments as Map)['text'] as String?;
        }
        return null;
      },
    );
    await t.pumpWidget(page(Lang.en, opened, canOpen: false));
    expect(find.text('About'), findsOneWidget);
    expect(find.text('E-mail'), findsOneWidget);
    expect(find.text('Licence'), findsOneWidget);

    await t.tap(find.byTooltip('Copy: E-mail'));
    await t.pump();
    expect(copied, 'antsa.raniriamanjaka@univ-antananarivo.mg');

    await t.tap(find.byKey(const Key('about-github')));
    await t.pumpAndSettle();
    expect(find.text('Could not open this link.'), findsOneWidget);
  });

  testWidgets('tap targets are at least 48 dp', (t) async {
    await t.pumpWidget(page(Lang.fr, []));
    await expectLater(t, meetsGuideline(androidTapTargetGuideline));
    await expectLater(t, meetsGuideline(labeledTapTargetGuideline));
  });
}
