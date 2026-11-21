import 'package:flutter/material.dart';

/// Neutral, quiet theme for the shell screens (the main UI is the web UI).
/// Brand colour from shells/branding/colors.json.
const Color brandColor = Color(0xFF1F4E5F);

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
