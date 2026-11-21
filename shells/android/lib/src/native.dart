/// Small platform channel to MainActivity.kt (device name, version,
/// saving downloads to the public Downloads folder, opening a file).
library;

import 'package:flutter/services.dart';

class NativeBridge {
  static const _ch = MethodChannel('mg.madalean.app/native');

  Future<String> deviceName() async {
    try {
      return await _ch.invokeMethod<String>('deviceName') ?? 'Android';
    } on PlatformException {
      return 'Android';
    } on MissingPluginException {
      return 'Android';
    }
  }

  Future<String> appVersion() async {
    try {
      return await _ch.invokeMethod<String>('appVersion') ?? '';
    } on PlatformException {
      return '';
    } on MissingPluginException {
      return '';
    }
  }

  /// Saves [bytes] as [name] in Downloads (MediaStore on Android 10+, a
  /// "save as" document picker on 8–9). Returns a content URI, or null if
  /// the user cancelled.
  Future<String?> saveDownload(String name, String mime, Uint8List bytes) =>
      _ch.invokeMethod<String>('saveDownload', {
        'name': name,
        'mime': mime,
        'bytes': bytes,
      });

  Future<bool> openUri(String uri, String mime) async =>
      await _ch.invokeMethod<bool>('openUri', {'uri': uri, 'mime': mime}) ??
      false;
}
