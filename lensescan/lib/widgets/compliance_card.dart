/// Compliance card widget — single declaration check result row.
///
/// Matches Stitch design: 5._compliance_results_report/code.html
/// One row per declaration: icon + name + status badge. Tap to expand.
library;

import 'package:flutter/material.dart';

import '../config/theme.dart';
import '../models/scan_result_model.dart';

/// Single declaration row with expandable detail section.
class ComplianceCard extends StatefulWidget {
  final DeclarationFieldModel declaration;

  const ComplianceCard({super.key, required this.declaration});

  @override
  State<ComplianceCard> createState() => _ComplianceCardState();
}

class _ComplianceCardState extends State<ComplianceCard> {
  bool _isExpanded = false;

  @override
  Widget build(BuildContext context) {
    final decl = widget.declaration;
    final isCompliant = decl.compliant;
    final isDetected = decl.detected;
    final hasReview = decl.coverageReviewRequired ||
        decl.placementReviewRequired ||
        decl.fontReviewRequired;

    // Status styling
    Color statusColor;
    Color statusBgColor;
    IconData statusIcon;
    String statusLabel;

    if (hasReview) {
      statusColor = const Color(0xFFD97706); // amber-600
      statusBgColor = const Color(0xFFFEF3C7); // amber-100
      statusIcon = Icons.help_rounded;
      statusLabel = 'Review';
    } else if (isCompliant) {
      statusColor = LenseScanTheme.secondary;
      statusBgColor = LenseScanTheme.secondaryFixed.withValues(alpha: 0.4);
      statusIcon = Icons.check_circle_rounded;
      statusLabel = 'Compliant';
    } else if (!isDetected) {
      statusColor = LenseScanTheme.error;
      statusBgColor = LenseScanTheme.errorContainer;
      statusIcon = Icons.cancel_rounded;
      statusLabel = 'Violation';
    } else {
      statusColor = LenseScanTheme.error;
      statusBgColor = LenseScanTheme.errorContainer;
      statusIcon = Icons.cancel_rounded;
      statusLabel = 'Violation';
    }

    return Container(
      decoration: BoxDecoration(
        color: LenseScanTheme.surfaceContainerLowest,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 4,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: () => setState(() => _isExpanded = !_isExpanded),
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Single-line row: icon + name + badge ──
                Row(
                  children: [
                    Icon(statusIcon, color: statusColor, size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        decl.displayName,
                        style: TextStyle(
                          fontSize: 17,
                          fontWeight: FontWeight.w600,
                          letterSpacing: -0.085,
                          color: LenseScanTheme.onSurface,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: statusBgColor,
                        borderRadius: BorderRadius.circular(9999),
                      ),
                      child: Text(
                        statusLabel,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w500,
                          letterSpacing: 0.12,
                          color: statusColor,
                        ),
                      ),
                    ),
                  ],
                ),

                // ── Expanded Details (tap to reveal) ──
                if (_isExpanded) ...[
                  const SizedBox(height: 12),
                  Divider(
                    height: 1,
                    color: LenseScanTheme.outlineVariant.withValues(alpha: 0.3),
                  ),
                  const SizedBox(height: 12),

                  // Detected value
                  if (decl.value != null)
                    _buildDetailRow('Detected Value', decl.value!),

                  // Font height
                  if (decl.fontHeightMm != null)
                    _buildDetailRow(
                      'Font Height',
                      '${decl.fontHeightMm!.toStringAsFixed(1)} mm'
                      '${decl.requiredFontHeightMm != null ? ' (min: ${decl.requiredFontHeightMm!.toStringAsFixed(1)} mm)' : ''}',
                    ),

                  // Confidence
                  if (decl.confidence != null)
                    _buildDetailRow(
                      'OCR Confidence',
                      '${(decl.confidence! * 100).toStringAsFixed(1)}%',
                    ),

                  // Rule 6 Placement
                  if (!decl.placementCompliant)
                    _buildDetailRow(
                      'Placement (Rule 8)',
                      decl.placementViolations.isNotEmpty
                          ? decl.placementViolations.first
                          : 'Non-compliant placement on label',
                    ),

                  // Placement Review Flag
                  if (decl.placementReviewRequired)
                    _buildDetailRow(
                      'Geometry Note',
                      decl.placementReviewReason ??
                          'Flagged for manual officer verification due to surface curvature',
                    ),

                  // Coverage Review Flag
                  if (decl.coverageReviewRequired)
                    _buildDetailRow(
                      'Coverage Note',
                      decl.coverageReviewReason ??
                          'Low spatial coverage. Absence cannot be certified without manual inspection.',
                    ),

                  // Font Review Flag
                  if (decl.fontReviewRequired)
                    _buildDetailRow(
                      'Font Measurement Note',
                      decl.fontReviewReason ??
                          'Measurement uncertainty interval requires manual verification.',
                    ),

                  // Violations
                  if (decl.violations.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    ...decl.violations.map(
                      (v) => Padding(
                        padding: const EdgeInsets.only(bottom: 4),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Icon(
                              Icons.info_outline,
                              size: 14,
                              color: statusColor.withValues(alpha: 0.8),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                v,
                                style: TextStyle(
                                  fontSize: 12,
                                  color: statusColor.withValues(alpha: 0.9),
                                  height: 1.4,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(
              label,
              style: TextStyle(
                fontSize: 12,
                color: LenseScanTheme.onSurfaceVariant,
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 12,
                color: LenseScanTheme.onSurface,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
