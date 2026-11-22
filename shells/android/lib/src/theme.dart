import 'package:flutter/material.dart';

/// Neutral, quiet theme for the shell screens (the main UI is the web UI).
/// Brand navy of shells/branding (docs/BRAND.md); orange accent #FE7B01 is decorative only.
const Color brandColor = Color(0xFF002B5C);

ThemeData shellTheme(Brightness b) {
  final scheme = ColorScheme.fromSeed(
    seedColor: brandColor,
    brightness: b,
    dynamicSchemeVariant: DynamicSchemeVariant.neutral,
  );
  return ThemeData(
    colorScheme: scheme,
    useMaterial3: true,
    visualDensity: VisualDensity.standard,
    inputDecorationTheme: const InputDecorationTheme(
      border: OutlineInputBorder(),
    ),
  );
}
