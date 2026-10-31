/// Home screen — enforcement overview.
///
/// Shows only what the backend returns: inspection totals, daily activity and the most
/// recent inspections. Loading, error and empty states are explicit; nothing is filled in
/// with sample data.
library;

import 'package:dio/dio.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../config/theme.dart';
import '../core/api/api_endpoints.dart';
import '../core/api/dio_client.dart';
import '../core/utils/product_formatter.dart';
import '../widgets/inspection_widgets.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  static const _trendDays = 14;

  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _summary;
  Map<String, dynamic>? _trends;
  List<Map<String, dynamic>> _recent = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final dio = DioClient.instance.dio;
      final results = await Future.wait([
        dio.get(ApiEndpoints.dashboardSummary),
        dio.get('${ApiEndpoints.inspections}?limit=6'),
        dio.get('/dashboard/trends?days=$_trendDays'),
      ]);
      if (!mounted) return;
      setState(() {
        _summary = results[0].data as Map<String, dynamic>;
        _recent = (results[1].data as List).cast<Map<String, dynamic>>();
        _trends = results[2].data as Map<String, dynamic>;
        _loading = false;
      });
    } on DioException catch (e) {
      debugPrint('Overview load failed: ${e.type} ${e.response?.statusCode}');
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.response?.statusCode == 401
            ? 'Your session expired. Sign in again.'
            : 'Couldn\'t reach the server.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.of(context).size.width >= 840;
    final pad = wide ? 32.0 : 16.0;

    return ColoredBox(
      color: LL.paper,
      child: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          color: LL.accent,
          child: ListView(
            padding: EdgeInsets.fromLTRB(pad, wide ? 28 : 16, pad, 32),
            children: [
              Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1180),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      _header(wide),
                      SizedBox(height: wide ? 22 : 16),
                      if (_loading)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 64),
                          child: Center(
                            child: SizedBox(
                              width: 22,
                              height: 22,
                              child: CircularProgressIndicator(strokeWidth: 2, color: LL.accent),
                            ),
                          ),
                        )
                      else if (_error != null)
                        _message(title: _error!, action: 'Try again', onTap: _load)
                      else
                        LayoutBuilder(builder: (context, c) {
                          final twoUp = c.maxWidth >= 900;
                          return Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              _statCards(c.maxWidth),
                              const SizedBox(height: 16),
                              twoUp
                                  // Each card takes its own height: forcing equal heights (IntrinsicHeight)
                                  // measured them too short on a laptop and cut off the chart's date labels
                                  // and the results legend.
                                  ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                      Expanded(flex: 3, child: _activityCard()),
                                      const SizedBox(width: 16),
                                      Expanded(flex: 2, child: _resultSplitCard()),
                                    ])
                                  : Column(children: [_activityCard(), const SizedBox(height: 16), _resultSplitCard()]),
                              const SizedBox(height: 16),
                              _recentSection(wide),
                            ],
                          );
                        }),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ── Header ──
  Widget _header(bool wide) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Expanded(
          child: Text(
            'Overview',
            style: TextStyle(fontSize: wide ? 30 : 24, fontWeight: FontWeight.w700, color: LL.text, letterSpacing: -0.6),
          ),
        ),
        FilledButton.icon(
          onPressed: () => context.go('/scanner'),
          style: FilledButton.styleFrom(
            backgroundColor: LL.accent,
            foregroundColor: LL.onAccent,
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
            shape: const StadiumBorder(),
            textStyle: const TextStyle(fontFamily: LL.font, fontSize: 14, fontWeight: FontWeight.w500),
          ),
          icon: const Icon(Icons.document_scanner_outlined, size: 18),
          label: const Text('Scan a label'),
        ),
      ],
    );
  }

  // ── Stat cards ──
  Widget _statCards(double maxWidth) {
    final total = (_summary?['total_inspections'] as num?)?.toInt() ?? 0;
    final compliant = (_summary?['compliant_count'] as num?)?.toInt() ?? 0;
    final notCompliant = (_summary?['non_compliant_count'] as num?)?.toInt() ?? 0;
    final rate = (_summary?['compliance_rate_pct'] as num?)?.toDouble() ?? 0;
    final week = (_summary?['week_inspections'] as num?)?.toInt() ?? 0;

    final notPct = total == 0 ? 0 : (100 * notCompliant / total).round();

    // One dark card for the total; the rest stay white and carry colour only in a small dot
    // that matches the chart series.
    final cards = [
      _stat('Inspections', '$total', 'All time', dark: true),
      _stat('Compliant', '$compliant', '${rate.round()}% of all', dot: LL.violet),
      _stat('Not compliant', '$notCompliant', '$notPct% of all', dot: LL.accentSoft),
      _stat('Last 7 days', '$week', 'Inspections', dot: LL.faint),
    ];
    final perRow = maxWidth >= 760 ? 4 : 2;
    final w = (maxWidth - (perRow - 1) * 12) / perRow;
    return Wrap(spacing: 12, runSpacing: 12, children: [for (final c in cards) SizedBox(width: w, child: c)]);
  }

  Widget _stat(String label, String value, String note, {bool dark = false, Color? dot}) {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
      decoration: BoxDecoration(color: dark ? LL.accent : LL.surface, borderRadius: BorderRadius.circular(LL.radius)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            if (dot != null) ...[
              Container(width: 8, height: 8, decoration: BoxDecoration(color: dot, shape: BoxShape.circle)),
              const SizedBox(width: 8),
            ],
            Text(label, style: TextStyle(fontSize: 13, color: dark ? LL.sidebarText : LL.muted)),
          ]),
          const SizedBox(height: 22),
          Text(
            value,
            style: TextStyle(
              fontSize: 30,
              fontWeight: FontWeight.w600,
              letterSpacing: -0.6,
              height: 1.1,
              color: dark ? LL.onAccent : LL.text,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
          const SizedBox(height: 4),
          Text(note, style: TextStyle(fontSize: 12.5, color: dark ? LL.highlight : LL.faint)),
        ],
      ),
    );
  }

  // ── Daily activity: compliant vs not compliant per day ──
  Widget _activityCard() {
    final dates = (_trends?['dates'] as List? ?? []).cast<String>();
    final ok = (_trends?['compliant'] as List? ?? []).map((v) => (v as num).toDouble()).toList();
    final bad = (_trends?['non_compliant'] as List? ?? []).map((v) => (v as num).toDouble()).toList();
    final hasData = ok.any((v) => v > 0) || bad.any((v) => v > 0);
    // Bars are stacked (compliant under not compliant), so the axis has to fit each day's total.
    final peak = [for (var i = 0; i < dates.length; i++) ok[i] + bad[i]].fold<double>(0, (a, b) => a > b ? a : b);
    // Whole-number grid step with ~4 lines; the top of the axis is a multiple of it so labels never overlap.
    final step = peak <= 4 ? 1.0 : (peak / 4).ceilToDouble();
    final maxY = ((peak / step).ceil() + 1) * step;

    return LLCard(
      title: 'Inspections per day',
      subtitle: 'Last $_trendDays days',
      trailing: Wrap(spacing: 12, children: [
        _legendDot(LL.violet, 'Compliant'),
        _legendDot(LL.accentSoft, 'Not compliant'),
      ]),
      child: SizedBox(
        height: 262,
        child: !hasData
            ? const Center(child: Text('No inspections in this period.', style: TextStyle(fontSize: 13, color: LL.muted)))
            : BarChart(
                BarChartData(
                  minY: 0,
                  maxY: maxY,
                  barGroups: [
                    for (var i = 0; i < dates.length; i++)
                      BarChartGroupData(x: i, barRods: [
                        BarChartRodData(
                          toY: ok[i] + bad[i],
                          width: 16,
                          color: Colors.transparent,
                          borderRadius: BorderRadius.circular(6),
                          rodStackItems: [
                            BarChartRodStackItem(0, ok[i], LL.violet),
                            BarChartRodStackItem(ok[i], ok[i] + bad[i], LL.accentSoft),
                          ],
                          // Faint full-height track behind every day, so quiet days still read as days.
                          backDrawRodData: BackgroundBarChartRodData(show: true, toY: maxY, color: const Color(0xFFF9F7F3)),
                        ),
                      ]),
                  ],
                  gridData: FlGridData(
                    drawVerticalLine: false,
                    horizontalInterval: step,
                    getDrawingHorizontalLine: (_) => const FlLine(color: LL.line, strokeWidth: 1, dashArray: [4, 4]),
                  ),
                  borderData: FlBorderData(show: false),
                  titlesData: FlTitlesData(
                    topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                    leftTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 28,
                        interval: step,
                        getTitlesWidget: (v, meta) => v % step != 0
                            ? const SizedBox.shrink()
                            : SideTitleWidget(axisSide: meta.axisSide, child: Text('${v.toInt()}', style: const TextStyle(fontSize: 11, color: LL.faint))),
                      ),
                    ),
                    bottomTitles: AxisTitles(
                      sideTitles: SideTitles(
                        showTitles: true,
                        reservedSize: 26,
                        getTitlesWidget: (v, meta) {
                          final i = v.toInt();
                          // Label every 2nd day (every 4th on phones), counted back from today, so labels never collide.
                          final every = MediaQuery.of(context).size.width < 600 ? 4 : 2;
                          if ((dates.length - 1 - i) % every != 0) return const SizedBox.shrink();
                          final d = DateTime.tryParse(dates[i]);
                          return SideTitleWidget(
                            axisSide: meta.axisSide,
                            child: Text(d == null ? '' : shortMonthDay(d), style: const TextStyle(fontSize: 11, color: LL.faint)),
                          );
                        },
                      ),
                    ),
                  ),
                  barTouchData: BarTouchData(
                    touchTooltipData: BarTouchTooltipData(
                      getTooltipColor: (_) => LL.accent,
                      getTooltipItem: (g, gi, rod, ri) => BarTooltipItem(
                        '${ok[g.x].toInt()} compliant\n${bad[g.x].toInt()} not compliant',
                        const TextStyle(color: Colors.white, fontSize: 12),
                      ),
                    ),
                  ),
                ),
              ),
      ),
    );
  }

  // ── Result split (all time) ──
  Widget _resultSplitCard() {
    final compliant = (_summary?['compliant_count'] as num?)?.toDouble() ?? 0;
    final notCompliant = (_summary?['non_compliant_count'] as num?)?.toDouble() ?? 0;
    final total = compliant + notCompliant;
    return LLCard(
      title: 'Results',
      subtitle: 'All inspections',
      child: SizedBox(
        height: 262,
        child: total == 0
            ? const Center(child: Text('No inspections yet.', style: TextStyle(fontSize: 13, color: LL.muted)))
            : Column(
                children: [
                  Expanded(
                    child: Stack(
                      alignment: Alignment.center,
                      children: [
                        PieChart(PieChartData(
                          centerSpaceRadius: 74,
                          sectionsSpace: 2,
                          startDegreeOffset: -90,
                          sections: [
                            PieChartSectionData(value: compliant, color: LL.violet, radius: 12, showTitle: false),
                            PieChartSectionData(value: notCompliant, color: LL.accentSoft, radius: 12, showTitle: false),
                          ],
                        )),
                        Column(mainAxisSize: MainAxisSize.min, children: [
                          Text('${(100 * compliant / total).round()}%',
                              style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w600, letterSpacing: -0.6, color: LL.text)),
                          const Text('compliant', style: TextStyle(fontSize: 12.5, color: LL.muted)),
                        ]),
                      ],
                    ),
                  ),
                  const SizedBox(height: 10),
                  Text(
                    '${compliant.toInt()} of ${total.toInt()} inspections',
                    style: const TextStyle(fontSize: 12.5, color: LL.muted),
                  ),
                ],
              ),
      ),
    );
  }

  Widget _legendDot(Color c, String label) => Row(mainAxisSize: MainAxisSize.min, children: [
        Container(width: 9, height: 9, decoration: BoxDecoration(color: c, shape: BoxShape.circle)),
        const SizedBox(width: 6),
        Text(label, style: const TextStyle(fontSize: 12, color: LL.muted)),
      ]);

  // ── Recent inspections ──
  Widget _recentSection(bool wide) {
    final viewAll = _recent.isEmpty
        ? null
        : TextButton(
            onPressed: () => context.go('/history'),
            style: TextButton.styleFrom(
              foregroundColor: LL.text,
              backgroundColor: LL.hover,
              shape: const StadiumBorder(),
              padding: const EdgeInsets.symmetric(horizontal: 14),
            ),
            child: const Text('View all', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
          );

    if (_recent.isEmpty) {
      return LLCard(
        title: 'Recent inspections',
        child: _message(
          title: 'No inspections yet',
          body: 'Scanned labels and their results will be listed here.',
          action: 'Scan a label',
          onTap: () => context.go('/scanner'),
          bare: true,
        ),
      );
    }

    return LLCard(
      title: 'Recent inspections',
      trailing: viewAll,
      padding: const EdgeInsets.fromLTRB(22, 22, 22, 12),
      child: Column(
        children: [
          if (wide) _tableHeader(),
          for (var i = 0; i < _recent.length; i++) ...[
            if (i > 0 || wide) const Divider(height: 1, thickness: 1, color: LL.line),
            wide ? _tableRow(_recent[i]) : _listRow(_recent[i]),
          ],
        ],
      ),
    );
  }

  Widget _tableHeader() {
    const style = TextStyle(fontSize: 12, color: LL.faint);
    return const Padding(
      padding: EdgeInsets.fromLTRB(8, 0, 8, 10),
      child: Row(
        children: [
          SizedBox(width: 96, child: Text('ID', style: style)),
          Expanded(child: Text('Product', style: style)),
          SizedBox(width: 72, child: Text('Fields', style: style)),
          SizedBox(width: 110, child: Text('Date', style: style)),
          SizedBox(width: 96, child: Text('Result', style: style, textAlign: TextAlign.right)),
        ],
      ),
    );
  }

  Widget _tableRow(Map<String, dynamic> insp) {
    return InkWell(
      onTap: () => context.push('/results', extra: insp),
      hoverColor: LL.hover,
      borderRadius: BorderRadius.circular(LL.radiusSmall),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 14),
        child: Row(
          children: [
            SizedBox(width: 96, child: Text(shortInspectionId(insp), style: LL.mono())),
            Expanded(
              child: Text(inspectionDisplayName(insp, maxLength: 48), style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: LL.text)),
            ),
            SizedBox(
              width: 72,
              child: Text(
                '${insp['compliant_fields'] ?? 0}/${insp['total_fields'] ?? 0}',
                style: const TextStyle(fontSize: 14, color: LL.muted, fontFeatures: [FontFeature.tabularFigures()]),
              ),
            ),
            SizedBox(width: 110, child: Text(formatInspectionDate(insp['created_at'] as String?), style: const TextStyle(fontSize: 14, color: LL.muted))),
            SizedBox(width: 96, child: Align(alignment: Alignment.centerRight, child: ResultPill(inspectionResult(insp)))),
          ],
        ),
      ),
    );
  }

  Widget _listRow(Map<String, dynamic> insp) {
    return InkWell(
      onTap: () => context.push('/results', extra: insp),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 14),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(inspectionDisplayName(insp, maxLength: 32), style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500, color: LL.text)),
                  const SizedBox(height: 3),
                  Text(
                    '${formatInspectionDate(insp['created_at'] as String?)} · ${insp['compliant_fields'] ?? 0}/${insp['total_fields'] ?? 0} fields',
                    style: const TextStyle(fontSize: 12, color: LL.muted),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            ResultPill(inspectionResult(insp)),
          ],
        ),
      ),
    );
  }

  Widget _message({required String title, String? body, required String action, required VoidCallback onTap, bool bare = false}) {
    final content = Column(
      children: [
        Text(title, textAlign: TextAlign.center, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: LL.text)),
        if (body != null) ...[
          const SizedBox(height: 6),
          Text(body, textAlign: TextAlign.center, style: const TextStyle(fontSize: 13, color: LL.muted)),
        ],
        const SizedBox(height: 16),
        FilledButton(
          onPressed: onTap,
          style: FilledButton.styleFrom(backgroundColor: LL.accent, foregroundColor: LL.onAccent, shape: const StadiumBorder()),
          child: Text(action, style: const TextStyle(fontSize: 13)),
        ),
      ],
    );
    if (bare) return Padding(padding: const EdgeInsets.symmetric(vertical: 20), child: content);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 36),
      decoration: LL.card(),
      child: content,
    );
  }
}
