/// Shared pieces for inspection lists (Overview, Inspections): result pill and formatting.
library;

import 'package:flutter/material.dart';

import '../config/theme.dart';

enum InspectionResult { compliant, violation, review }

/// Hard violations take precedence; otherwise a non-compliant record is pending officer review.
InspectionResult inspectionResult(Map<String, dynamic> insp) {
  if (insp['overall_compliant'] == true) return InspectionResult.compliant;
  final hard = (insp['non_compliant_fields'] as num?)?.toInt() ?? 0;
  return hard > 0 ? InspectionResult.violation : InspectionResult.review;
}

String shortInspectionId(Map<String, dynamic> insp) {
  final id = (insp['id'] ?? '').toString();
  return id.length > 8 ? id.substring(0, 8) : id;
}

const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/// "Today 14:05", "26 Sep", or "26 Sep 2025" for other years.
String formatInspectionDate(String? iso) {
  final dt = iso == null ? null : DateTime.tryParse(iso)?.toLocal();
  if (dt == null) return '—';
  final now = DateTime.now();
  if (dt.year == now.year && dt.month == now.month && dt.day == now.day) {
    return 'Today ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }
  final base = '${dt.day} ${_months[dt.month - 1]}';
  return dt.year == now.year ? base : '$base ${dt.year}';
}

String shortMonthDay(DateTime d) => '${d.day} ${_months[d.month - 1]}';

/// Result as a soft pill: red for violations, amber for review, green when compliant.
class ResultPill extends StatelessWidget {
  final InspectionResult result;
  const ResultPill(this.result, {super.key});

  @override
  Widget build(BuildContext context) {
    final (String label, Color fg, Color bg) = switch (result) {
      InspectionResult.compliant => ('Compliant', LL.success, const Color(0xFFE6F2EA)),
      InspectionResult.violation => ('Violation', LL.danger, const Color(0xFFFBE9E7)),
      InspectionResult.review => ('Review', LL.warning, const Color(0xFFFBF0DD)),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(20)),
      child: Text(label, style: TextStyle(fontSize: 12, color: fg, fontWeight: FontWeight.w600)),
    );
  }
}
