/// Loading overlay shown while a label photo is uploaded and checked.
///
/// Reports only what the app actually knows: upload progress, then that the
/// server is reading the label. No simulated pipeline steps.
library;

import 'package:flutter/material.dart';

import '../config/theme.dart';

class LoadingOverlay extends StatelessWidget {
  /// Upload progress from 0 to 1, or null when unknown.
  final double? progress;

  const LoadingOverlay({super.key, this.progress});

  @override
  Widget build(BuildContext context) {
    final p = progress;
    final uploading = p != null && p < 1;
    final title = uploading ? 'Uploading photo' : 'Reading the label';
    final detail = uploading
        ? '${(p * 100).round()}%'
        : 'Text recognition and rule checks usually take a few seconds.';

    return Positioned.fill(
      child: ColoredBox(
        color: LL.paper.withValues(alpha: 0.96),
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                SizedBox(
                  width: 28,
                  height: 28,
                  child: CircularProgressIndicator(
                    strokeWidth: 2.5,
                    color: LL.accent,
                    value: uploading ? p : null,
                    backgroundColor: uploading ? LL.line : null,
                  ),
                ),
                const SizedBox(height: 18),
                Text(title, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500, color: LL.text)),
                const SizedBox(height: 6),
                Text(detail, textAlign: TextAlign.center, style: const TextStyle(fontSize: 13, color: LL.muted)),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
