import 'package:flutter/material.dart';

/// LegalLens mark: an "L" drawn as a viewfinder corner, with a lime dot as the lens.
///
/// With [tile] the mark sits on the aubergine app-icon tile; without it the glyph
/// is drawn straight onto a dark background (the sidebar).
class LegalLensLogo extends StatelessWidget {
  final double size;
  final bool tile;
  final bool showText;
  final Color? textColor;
  final String? subtitle;

  const LegalLensLogo({
    super.key,
    this.size = 38,
    this.tile = true,
    this.showText = false,
    this.textColor,
    this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    final emblem = SizedBox(
      width: size,
      height: size,
      child: CustomPaint(painter: _LegalLensMarkPainter(tile: tile)),
    );

    if (!showText) {
      return emblem;
    }

    return Row(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        emblem,
        const SizedBox(width: 12),
        Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'LegalLens',
              style: TextStyle(
                fontSize: size * 0.46,
                fontWeight: FontWeight.w500,
                color: textColor ?? const Color(0xFF1E1A2B),
                letterSpacing: -0.4,
                height: 1.1,
              ),
            ),
            if (subtitle != null) ...[
              const SizedBox(height: 2),
              Text(
                subtitle!,
                style: TextStyle(
                  fontSize: (size * 0.28).clamp(9.0, 12.0),
                  fontWeight: FontWeight.w500,
                  color: (textColor ?? const Color(0xFF1E1A2B)).withValues(alpha: 0.65),
                  height: 1.1,
                ),
              ),
            ],
          ],
        ),
      ],
    );
  }
}

class _LegalLensMarkPainter extends CustomPainter {
  final bool tile;

  const _LegalLensMarkPainter({required this.tile});

  static const _aubergine = Color(0xFF2A2140);
  static const _cream = Color(0xFFF5F2EC);
  static const _lime = Color(0xFFD8F36B);

  @override
  void paint(Canvas canvas, Size size) {
    // Drawn on a 48-unit grid and scaled to the widget size.
    final s = size.width / 48;
    canvas.scale(s);

    if (tile) {
      canvas.drawRRect(
        RRect.fromRectAndRadius(const Rect.fromLTWH(0, 0, 48, 48), const Radius.circular(11)),
        Paint()..color = _aubergine,
      );
    }

    final stroke = Paint()
      ..color = _cream
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round
      ..strokeJoin = StrokeJoin.round;
    canvas.drawPath(
      Path()
        ..moveTo(14, 13)
        ..lineTo(14, 35)
        ..lineTo(35, 35),
      stroke,
    );

    canvas.drawCircle(const Offset(31.5, 17), 4.2, Paint()..color = _lime);
  }

  @override
  bool shouldRepaint(covariant _LegalLensMarkPainter oldDelegate) => oldDelegate.tile != tile;
}
