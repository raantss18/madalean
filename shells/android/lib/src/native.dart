/// Small platform channel to MainActivity.kt (device name, version,
/// saving downloads to the public Downloads folder, opening a file).
library;

import 'package:flutter/services.dart';
import 'package:madalean_shell/src/update.dart';

class NativeBridge implements UpdatePlatform {
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

  /// Opens the Tailscale app, or its store page: 'app' | 'store' | 'none'.
  Future<String> openTailscale() async {
    try {
      return await _ch.invokeMethod<String>('openTailscale') ?? 'none';
    } on PlatformException {
      return 'none';
    } on MissingPluginException {
      return 'none';
    }
  }

  /// Opens this app's system settings (permissions).
  Future<bool> openAppSettings() async {
    try {
      return await _ch.invokeMethod<bool>('openAppSettings') ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  // ---------------------------------------------------------------- updates
  @override
  Future<String> installedVersion() => appVersion();

  @override
  Future<List<String>> abis() async =>
      (await _ch.invokeListMethod<String>('abis')) ?? const [];

  @override
  Future<String> cacheDir() async =>
      await _ch.invokeMethod<String>('cacheDir') ?? '';

  @override
  Future<bool> apkMatchesInstalled(String path) async =>
      await _ch.invokeMethod<bool>('apkMatchesInstalled', {'path': path}) ??
      false;

  @override
  Future<bool> canInstall() async =>
      await _ch.invokeMethod<bool>('canInstall') ?? false;

  @override
  Future<void> openInstallSettings() =>
      _ch.invokeMethod<void>('openInstallSettings');

  @override
  Future<void> install(String path) =>
      _ch.invokeMethod<void>('installApk', {'path': path});
}
