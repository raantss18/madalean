/// In-app QR scanner for the host's pairing code (camera only while this
/// screen is open; nothing is saved or sent). Returns the scanned pairing
/// link text, or null.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:madalean_shell/src/address.dart';
import 'package:madalean_shell/src/strings.dart';
import 'package:mobile_scanner/mobile_scanner.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({required this.strings, this.openAppSettings, super.key});
  final S strings;
  final Future<bool> Function()? openAppSettings;

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final _controller = MobileScannerController(
    formats: const [BarcodeFormat.qrCode],
    detectionSpeed: DetectionSpeed.noDuplicates,
  );
  bool _done = false;
  DateTime _lastWrong = DateTime.fromMillisecondsSinceEpoch(0);

  @override
  void dispose() {
    unawaited(_controller.dispose());
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_done) return;
    for (final b in capture.barcodes) {
      final raw = b.rawValue;
      if (raw == null) continue;
      if (parsePairLink(raw) != null) {
        _done = true;
        Navigator.of(context).pop(raw);
        return;
      }
    }
    final now = DateTime.now();
    if (now.difference(_lastWrong).inSeconds >= 3) {
      _lastWrong = now;
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(content: Text(widget.strings.notMadaleanQr)));
    }
  }

  Widget _error(BuildContext context, MobileScannerException e) {
    final s = widget.strings;
    final denied = e.errorCode == MobileScannerErrorCode.permissionDenied;
    return ColoredBox(
      color: Colors.black,
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(
                Icons.no_photography_outlined,
                color: Colors.white,
                size: 48,
              ),
              const SizedBox(height: 16),
              Text(
                denied ? s.cameraDenied : s.cameraError,
                style: const TextStyle(color: Colors.white),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 16),
              if (denied && widget.openAppSettings != null)
                FilledButton(
                  onPressed: () => unawaited(widget.openAppSettings!()),
                  child: Text(s.openSettings),
                ),
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: Text(
                  s.cancel,
                  style: const TextStyle(color: Colors.white),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.strings;
    final size = MediaQuery.sizeOf(context);
    final box = (size.shortestSide * 0.7).clamp(200.0, 320.0);
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: Text(s.scanQr),
        actions: [
          IconButton(
            tooltip: s.torch,
            icon: const Icon(Icons.flashlight_on_outlined),
            onPressed: () => unawaited(_controller.toggleTorch()),
          ),
        ],
      ),
      body: Stack(
        children: [
          MobileScanner(
            controller: _controller,
            onDetect: _onDetect,
            errorBuilder: _error,
          ),
          Center(
            child: Container(
              width: box,
              height: box,
              decoration: BoxDecoration(
                border: Border.all(color: Colors.white, width: 3),
                borderRadius: BorderRadius.circular(16),
              ),
            ),
          ),
          Positioned(
            left: 16,
            right: 16,
            bottom: 32,
            child: Text(
              s.scanAim,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Colors.white,
                fontSize: 16,
                shadows: [Shadow(blurRadius: 4)],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
