/// LenseScan light theme — clean gov-tech Material 3 aesthetic.
///
/// Light surface, teal primary, emerald secondary, Inter typography.
/// Color tokens extracted from Stitch design export tailwind.config.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// Soft monochrome palette: grey canvas, white rounded cards, near-black accent,
/// colour reserved for results (red = violation, amber = needs review) and chart series.
class LL {
  LL._();

  static const Color paper = Color(0xFFF5F2EC); // warm cream canvas
  static const Color surface = Color(0xFFFFFFFF); // cards
  static const Color line = Color(0xFFECE7DF); // hairline borders
  static const Color hover = Color(0xFFF4F1EB); // row hover, icon circles, chips

  static const Color text = Color(0xFF1E1A2B);
  static const Color muted = Color(0xFF6E6880);
  static const Color faint = Color(0xFFA29CB0);

  static const Color accent = Color(0xFF2A2140); // deep aubergine: primary buttons, dark cards
  static const Color onAccent = Color(0xFFFFFFFF);
  static const Color accentSoft = Color(0xFFFFB59A); // peach: secondary bars

  // Sidebar
  static const Color sidebar = Color(0xFF231C35);
  static const Color sidebarText = Color(0xFFB7AFCB);
  static const Color highlight = Color(0xFFD8F36B); // lime: selected nav, key highlights
  static const Color violet = Color(0xFF7C5CFF); // main chart colour

  /// Pastel card backgrounds (lavender, peach, mint, butter, sky) with readable text on top.
  static const List<Color> pastels = [
    Color(0xFFE6DEFF),
    Color(0xFFFFE1D3),
    Color(0xFFD5F2E2),
    Color(0xFFFFF0C2),
    Color(0xFFD9ECFF),
  ];
  static Color pastel(int i) => pastels[i % pastels.length];

  static const Color danger = Color(0xFFC0362C);
  static const Color warning = Color(0xFFA15C07);
  static const Color success = Color(0xFF2E7D4F);

  /// Bundled IBM Plex Sans (see pubspec.yaml), so bold and semibold text use the real weights.
  static const String font = 'IBMPlexSans';

  static const double radius = 22; // cards
  static const double radiusSmall = 12; // inner panels, inputs

  /// Chart series colours (one per model / category), muted so they sit on white cards.
  static const List<Color> series = [
    Color(0xFF7C5CFF),
    Color(0xFFFF7A59),
    Color(0xFF2BB673),
    Color(0xFFFFB800),
    Color(0xFFE5508E),
    Color(0xFF3D9BFF),
    Color(0xFF2A2140),
    Color(0xFFB79B5E),
    Color(0xFF22B8B0),
    Color(0xFFB3A9C9),
  ];

  static TextStyle mono({double size = 12, Color color = muted}) =>
      GoogleFonts.ibmPlexMono(fontSize: size, color: color, letterSpacing: 0);

  /// White rounded card used on every screen.
  static BoxDecoration card({double? r}) => BoxDecoration(
        color: surface,
        borderRadius: BorderRadius.circular(r ?? radius),
      );
}

/// Standard card: white, rounded, with an optional title row.
class LLCard extends StatelessWidget {
  final String? title;
  final String? subtitle;
  final Widget? trailing;
  final Widget child;
  final EdgeInsetsGeometry padding;

  const LLCard({
    super.key,
    this.title,
    this.subtitle,
    this.trailing,
    required this.child,
    this.padding = const EdgeInsets.all(22),
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: LL.card(),
      padding: padding,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (title != null) ...[
            LayoutBuilder(builder: (context, box) {
              final heading = Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title!, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: LL.text)),
                  if (subtitle != null) ...[
                    const SizedBox(height: 3),
                    Text(subtitle!, style: const TextStyle(fontSize: 12.5, color: LL.muted)),
                  ],
                ],
              );
              if (trailing == null) return heading;
              // Narrow cards: legend / controls go under the title so the title never gets squeezed.
              if (box.maxWidth < 560) {
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [heading, const SizedBox(height: 12), trailing!],
                );
              }
              return Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(child: heading),
                  const SizedBox(width: 12),
                  Flexible(child: Align(alignment: Alignment.topRight, child: trailing!)),
                ],
              );
            }),
            const SizedBox(height: 18),
          ],
          child,
        ],
      ),
    );
  }
}

class LenseScanTheme {
  LenseScanTheme._();

  // ── ShipMates Core Palette ──
  static const Color surface = Color(0xFFFAF7F2); // Warm Cream Canvas
  static const Color surfaceDim = Color(0xFFF2ECE4);
  static const Color surfaceContainerLowest = Color(0xFFFFFFFF);
  static const Color surfaceContainerLow = Color(0xFFFAF7F2);
  static const Color surfaceContainer = Color(0xFFF3ECFC); // Soft Lilac Container
  static const Color surfaceContainerHigh = Color(0xFFE8DEF8);
  static const Color surfaceContainerHighest = Color(0xFFDDD2F0);

  static const Color primary = Color(0xFF282038); // Deep Midnight Aubergine
  static const Color primaryContainer = Color(0xFF372C4C);
  static const Color onPrimary = Color(0xFFFFFFFF);
  static const Color onPrimaryContainer = Color(0xFFE4D5F7);
  static const Color primaryFixed = Color(0xFFE4D5F7); // Soft Lilac
  static const Color primaryFixedDim = Color(0xFFD0BDF2);

  static const Color secondary = Color(0xFF5B21B6); // Royal Violet
  static const Color secondaryContainer = Color(0xFFE4D5F7); // Soft Lilac Pill
  static const Color onSecondary = Color(0xFFFFFFFF);
  static const Color onSecondaryContainer = Color(0xFF282038);
  static const Color secondaryFixed = Color(0xFFE4D5F7);

  static const Color error = Color(0xFFDC2626);
  static const Color errorContainer = Color(0xFFFDEEEC); // Warm Coral / Peach Tint
  static const Color onError = Color(0xFFFFFFFF);
  static const Color onErrorContainer = Color(0xFFB91C1C);

  static const Color tertiary = Color(0xFFC2410C); // Warm Terracotta / Apricot
  static const Color tertiaryContainer = Color(0xFFFDF2E9); // Soft Apricot Pill

  static const Color onSurface = Color(0xFF221A30); // Deep Aubergine Text
  static const Color onSurfaceVariant = Color(0xFF7E768F); // Silvery Mauve Slate
  static const Color outline = Color(0xFF9E95AE);
  static const Color outlineVariant = Color(0xFFEDE7F2); // Subtle Lavender Border

  static const Color inverseSurface = Color(0xFF282038);
  static const Color inverseOnSurface = Color(0xFFFAF7F2);
  static const Color inversePrimary = Color(0xFFE4D5F7);

  // ── Semantic Colors ──
  static const Color warningAmber = Color(0xFFF59E0B);
  static const Color warningAmberLight = Color(0xFFFFF7ED); // amber-50
  static const Color warningAmberBorder = Color(0xFFFDE68A); // amber-200

  // ── Legacy aliases (for gradual migration) ──
  static const Color emeraldAccent = secondary;
  static const Color successGreen = secondary;
  static const Color errorRed = error;
  static const Color textPrimary = onSurface;
  static const Color textSecondary = onSurfaceVariant;

  // ── Theme Data ──
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      fontFamily: LL.font,
      scaffoldBackgroundColor: surface,
      colorScheme: const ColorScheme.light(
        primary: primary,
        onPrimary: onPrimary,
        primaryContainer: primaryContainer,
        onPrimaryContainer: onPrimaryContainer,
        secondary: secondary,
        onSecondary: onSecondary,
        secondaryContainer: secondaryContainer,
        onSecondaryContainer: onSecondaryContainer,
        tertiary: tertiary,
        tertiaryContainer: tertiaryContainer,
        error: error,
        onError: onError,
        errorContainer: errorContainer,
        onErrorContainer: onErrorContainer,
        surface: surface,
        onSurface: onSurface,
        onSurfaceVariant: onSurfaceVariant,
        outline: outline,
        outlineVariant: outlineVariant,
        inverseSurface: inverseSurface,
        onInverseSurface: inverseOnSurface,
        inversePrimary: inversePrimary,
      ),
      textTheme: ThemeData.light().textTheme.apply(fontFamily: LL.font).copyWith(
        // display-lg: 36/44, -0.03em, 700
        displayLarge: const TextStyle(fontFamily: LL.font, 
          fontSize: 36,
          fontWeight: FontWeight.w700,
          color: onSurface,
          letterSpacing: -1.08,
          height: 44 / 36,
        ),
        // display-sm: 28/34, -0.02em, 700
        displayMedium: const TextStyle(fontFamily: LL.font, 
          fontSize: 28,
          fontWeight: FontWeight.w700,
          color: onSurface,
          letterSpacing: -0.56,
          height: 34 / 28,
        ),
        // headline-lg: 24/30, -0.015em, 600
        headlineLarge: const TextStyle(fontFamily: LL.font, 
          fontSize: 24,
          fontWeight: FontWeight.w600,
          color: onSurface,
          letterSpacing: -0.36,
          height: 30 / 24,
        ),
        // headline-sm: 20/26, -0.01em, 600
        headlineMedium: const TextStyle(fontFamily: LL.font, 
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: onSurface,
          letterSpacing: -0.2,
          height: 26 / 20,
        ),
        // title-md: 17/22, -0.005em, 600
        titleLarge: const TextStyle(fontFamily: LL.font, 
          fontSize: 17,
          fontWeight: FontWeight.w600,
          color: onSurface,
          letterSpacing: -0.085,
          height: 22 / 17,
        ),
        // body-lg: 15/21, 400
        bodyLarge: const TextStyle(fontFamily: LL.font, 
          fontSize: 15,
          fontWeight: FontWeight.w400,
          color: onSurface,
          height: 21 / 15,
        ),
        // body-md: 13/18, 400
        bodyMedium: const TextStyle(fontFamily: LL.font, 
          fontSize: 13,
          fontWeight: FontWeight.w400,
          color: onSurfaceVariant,
          height: 18 / 13,
        ),
        // label-md: 12/16, 0.01em, 500
        labelLarge: const TextStyle(fontFamily: LL.font, 
          fontSize: 12,
          fontWeight: FontWeight.w500,
          color: onSurfaceVariant,
          letterSpacing: 0.12,
          height: 16 / 12,
        ),
        // label-sm: 11/14, 0.03em, 600
        labelSmall: const TextStyle(fontFamily: LL.font, 
          fontSize: 11,
          fontWeight: FontWeight.w600,
          color: onSurfaceVariant,
          letterSpacing: 0.33,
          height: 14 / 11,
        ),
      ),
      appBarTheme: AppBarTheme(
        backgroundColor: surface.withValues(alpha: 0.9),
        elevation: 0,
        scrolledUnderElevation: 0,
        centerTitle: false,
        titleTextStyle: const TextStyle(fontFamily: LL.font, 
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: onSurface,
          letterSpacing: -0.2,
        ),
        iconTheme: const IconThemeData(color: onSurface),
      ),
      cardTheme: CardThemeData(
        color: surfaceContainerLowest,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(color: outlineVariant.withValues(alpha: 0.2)),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: primaryContainer,
          foregroundColor: onPrimary,
          elevation: 0,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          textStyle: const TextStyle(fontFamily: LL.font, 
            fontSize: 17,
            fontWeight: FontWeight.w600,
            letterSpacing: -0.085,
          ),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: onSurface,
          side: BorderSide(color: outlineVariant.withValues(alpha: 0.2)),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surfaceContainerLow,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: primaryContainer, width: 1),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: error),
        ),
        hintStyle: const TextStyle(fontFamily: LL.font, 
          color: outline,
          fontSize: 15,
        ),
        labelStyle: const TextStyle(fontFamily: LL.font, 
          color: onSurfaceVariant,
          fontSize: 12,
          fontWeight: FontWeight.w500,
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: inverseSurface,
        contentTextStyle: const TextStyle(fontFamily: LL.font, color: inverseOnSurface),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
        ),
        behavior: SnackBarBehavior.floating,
      ),
      dividerTheme: DividerThemeData(
        color: outlineVariant.withValues(alpha: 0.2),
        thickness: 1,
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: surface.withValues(alpha: 0.9),
        indicatorColor: Colors.transparent,
        elevation: 0,
        height: 64,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const TextStyle(fontFamily: LL.font, 
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: primary,
              letterSpacing: 0.33,
            );
          }
          return const TextStyle(fontFamily: LL.font, 
            fontSize: 11,
            fontWeight: FontWeight.w600,
            color: onSurfaceVariant,
            letterSpacing: 0.33,
          );
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return const IconThemeData(color: primary, size: 24);
          }
          return const IconThemeData(color: onSurfaceVariant, size: 24);
        }),
      ),
    );
  }

  // Keep darkTheme as a redirect for backward compat during migration
  static ThemeData get darkTheme => lightTheme;
}
