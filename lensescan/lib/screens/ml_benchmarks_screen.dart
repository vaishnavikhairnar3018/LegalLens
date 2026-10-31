/// Model screen — product-category classifier benchmark.
///
/// Every number comes from GET /ml/metrics (docs/model_metrics.json written by
/// scripts/train_product_categorizer.py). Per-category precision / recall / F1 and the
/// test-set mix are computed here from the best model's confusion matrix. The top words
/// per category come from GET /ml/top-terms (the saved Linear SVM's own weights).
library;

import 'package:dio/dio.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../config/theme.dart';
import '../core/api/dio_client.dart';

class MLBenchmarksScreen extends StatefulWidget {
  const MLBenchmarksScreen({super.key});

  @override
  State<MLBenchmarksScreen> createState() => _MLBenchmarksScreenState();
}

/// One trained model's test-set scores (percent).
class _ModelScore {
  final String name;
  final double accuracy, precision, recall, f1, cvMean, cvStd;
  _ModelScore(this.name, this.accuracy, this.precision, this.recall, this.f1, this.cvMean, this.cvStd);

  double metric(int i) => [accuracy, precision, recall, f1][i];

  factory _ModelScore.fromJson(Map<String, dynamic> j) {
    double n(String k) => (j[k] as num?)?.toDouble() ?? 0;
    return _ModelScore(j['model_name'] as String? ?? '', n('accuracy_pct'), n('precision_pct'), n('recall_pct'), n('f1_score_pct'),
        n('cv_mean_pct'), n('cv_std_pct'));
  }
}

/// Per-category scores of the best model, from its confusion matrix (rows = true, cols = predicted).
class _ClassScore {
  final String name;
  final int support; // test products in this category
  final double precision, recall, f1; // percent
  _ClassScore(this.name, this.support, this.precision, this.recall, this.f1);

  double metric(int i) => [precision, recall, f1][i];
}

/// The words the Linear SVM weighs most for one category.
class _CategoryTerms {
  final String category;
  final List<(String, double)> terms; // (word, weight), highest first
  _CategoryTerms(this.category, this.terms);

  factory _CategoryTerms.fromJson(Map<String, dynamic> j) => _CategoryTerms(
        j['category'] as String? ?? '',
        [
          for (final t in (j['terms'] as List? ?? const []))
            ((t as Map<String, dynamic>)['term'] as String? ?? '', (t['weight'] as num?)?.toDouble() ?? 0),
        ],
      );
}

const _metricNames = ['Accuracy', 'Precision', 'Recall', 'F1 score'];

// Shortened explicitly so axis labels never get cut off.
const _shortNames = {
  'Linear SVM': 'Linear SVM',
  'Multinomial Naive Bayes': 'Naive Bayes',
  'Logistic Regression': 'Logistic Reg.',
  'k-Nearest Neighbors': 'k-NN',
  'Random Forest': 'Random Forest',
  'Decision Tree': 'Decision Tree',
};

class _MLBenchmarksScreenState extends State<MLBenchmarksScreen> {
  bool _loading = true;
  String? _error;

  String _bestModel = '';
  int _totalSamples = 0;
  List<_ModelScore> _models = [];
  List<String> _classes = [];
  List<List<int>> _matrix = [];
  List<_ClassScore> _classScores = [];

  int _histMetric = 2; // 0 precision, 1 recall, 2 F1
  int _singleMetric = 0; // index into _metricNames

  List<_CategoryTerms> _topTerms = [];
  String? _topTermsError;
  int _termCategory = 0;

  final _classifyController = TextEditingController();
  bool _classifying = false;
  String? _classifyError;
  Map<String, dynamic>? _classifyResult;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _classifyController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final res = await DioClient.instance.dio.get('/ml/metrics');
      final data = res.data as Map<String, dynamic>;
      final cm = data['confusion_matrix'] as Map<String, dynamic>;
      final classes = (cm['classes'] as List).cast<String>();
      final matrix = (cm['matrix'] as List).map((r) => (r as List).map((v) => (v as num).toInt()).toList()).toList();
      if (!mounted) return;
      setState(() {
        _bestModel = data['best_model'] as String? ?? '';
        _totalSamples = (data['total_samples'] as num?)?.toInt() ?? 0;
        _models = (data['models_benchmark'] as List).map((m) => _ModelScore.fromJson(m as Map<String, dynamic>)).toList();
        _classes = classes;
        _matrix = matrix;
        _classScores = _perClass(classes, matrix);
        _loading = false;
      });
    } on DioException catch (e) {
      debugPrint('Model metrics load failed: ${e.type} ${e.response?.statusCode}');
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.response?.statusCode == 404
            ? 'No model metrics on the server yet. Run the training script first.'
            : 'Couldn\'t reach the server.';
      });
      return;
    }
    await _loadTopTerms();
  }

  // Loaded separately: if it fails, only this chart shows the error; the metrics still show.
  Future<void> _loadTopTerms() async {
    try {
      final res = await DioClient.instance.dio.get('/ml/top-terms', queryParameters: {'n': 8});
      final cats = ((res.data as Map<String, dynamic>)['categories'] as List)
          .map((c) => _CategoryTerms.fromJson(c as Map<String, dynamic>))
          .toList();
      if (!mounted) return;
      setState(() {
        _topTerms = cats;
        _topTermsError = null;
        if (_termCategory >= cats.length) _termCategory = 0;
      });
    } on DioException catch (e) {
      debugPrint('Top terms load failed: ${e.type} ${e.response?.statusCode}');
      if (!mounted) return;
      setState(() {
        _topTerms = [];
        _topTermsError =
            e.response?.statusCode == 503 ? 'The classifier isn\'t loaded on the server.' : 'Couldn\'t load the model\'s words.';
      });
    }
  }

  static List<_ClassScore> _perClass(List<String> classes, List<List<int>> m) {
    final out = <_ClassScore>[];
    for (var i = 0; i < classes.length; i++) {
      final tp = m[i][i];
      final support = m[i].fold<int>(0, (a, b) => a + b);
      final predicted = m.fold<int>(0, (a, row) => a + row[i]);
      final p = predicted == 0 ? 0.0 : tp / predicted;
      final r = support == 0 ? 0.0 : tp / support;
      final f1 = (p + r) == 0 ? 0.0 : 2 * p * r / (p + r);
      out.add(_ClassScore(classes[i], support, p * 100, r * 100, f1 * 100));
    }
    return out;
  }

  int get _testSize => _classScores.fold<int>(0, (a, c) => a + c.support);
  _ModelScore? get _best => _models.where((m) => m.name == _bestModel).firstOrNull ?? _models.firstOrNull;

  Future<void> _classify() async {
    final query = _classifyController.text.trim();
    if (query.isEmpty) {
      setState(() => _classifyError = 'Enter a product name first.');
      return;
    }
    setState(() {
      _classifying = true;
      _classifyError = null;
    });
    try {
      final res = await DioClient.instance.dio.post('/ml/categorize', data: {'product_name': query});
      if (!mounted) return;
      setState(() {
        _classifyResult = res.data as Map<String, dynamic>;
        _classifying = false;
      });
    } on DioException catch (e) {
      // Never invent a prediction when the model can't be reached.
      if (!mounted) return;
      final detail = e.response?.data is Map ? (e.response!.data as Map)['detail'] : null;
      setState(() {
        _classifying = false;
        _classifyResult = null;
        _classifyError = detail is String ? detail : 'Couldn\'t reach the model. Try again.';
      });
    }
  }

  // ── Build ──
  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.of(context).size.width;
    final wide = width >= 840;
    final pad = wide ? 32.0 : 16.0;

    Widget body;
    if (_loading) {
      body = const Padding(
        padding: EdgeInsets.symmetric(vertical: 80),
        child: Center(child: SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2, color: LL.accent))),
      );
    } else if (_error != null) {
      body = LLCard(
        child: Column(
          children: [
            Text(_error!, textAlign: TextAlign.center, style: const TextStyle(fontSize: 15, color: LL.text)),
            const SizedBox(height: 12),
            OutlinedButton(onPressed: _load, child: const Text('Try again')),
          ],
        ),
      );
    } else {
      body = LayoutBuilder(builder: (context, c) {
        final twoUp = c.maxWidth >= 900;
        // Each card takes its own height. Forcing equal heights (IntrinsicHeight) measured some
        // cards too short on a laptop and cut off their last line (legend, chart labels).
        Widget pair(Widget a, Widget b) => twoUp
            ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(child: a),
                const SizedBox(width: 16),
                Expanded(child: b),
              ])
            : Column(children: [a, const SizedBox(height: 16), b]);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _statCards(c.maxWidth),
            const SizedBox(height: 16),
            _barCard(),
            const SizedBox(height: 16),
            pair(_metricBarCard(), _errorRateCard()),
            const SizedBox(height: 16),
            _radarGridCard(),
            const SizedBox(height: 16),
            pair(_radarCard(), _pieCard()),
            const SizedBox(height: 16),
            pair(_histogramCard(), _perClassCard()),
            const SizedBox(height: 16),
            _leaderboardCard(),
            const SizedBox(height: 16),
            pair(_confusionCard(), _classifyCard()),
            const SizedBox(height: 16),
            _topTermsCard(),
          ],
        );
      });
    }

    return Scaffold(
      backgroundColor: LL.paper,
      body: SafeArea(
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
                      Text('Model',
                          style: TextStyle(fontSize: wide ? 30 : 24, fontWeight: FontWeight.w700, color: LL.text, letterSpacing: -0.6)),
                      const SizedBox(height: 4),
                      if (!_loading && _error == null)
                        Text(
                          'Product category classifier · $_totalSamples products · ${_classes.length} categories · tested on $_testSize',
                          style: const TextStyle(fontSize: 13.5, color: LL.muted),
                        ),
                      SizedBox(height: wide ? 22 : 16),
                      body,
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

  // ── Stat cards ──
  Widget _statCards(double maxWidth) {
    final b = _best!;
    final cards = [
      _stat(Icons.emoji_events_outlined, b.name, 'Best model', dark: true),
      _stat(Icons.check_circle_outline, '${b.accuracy.toStringAsFixed(2)}%', 'Accuracy', bg: LL.pastel(0)),
      _stat(Icons.center_focus_strong_outlined, '${b.precision.toStringAsFixed(2)}%', 'Precision', bg: LL.pastel(1)),
      _stat(Icons.replay_outlined, '${b.recall.toStringAsFixed(2)}%', 'Recall', bg: LL.pastel(2)),
      _stat(Icons.balance_outlined, '${b.f1.toStringAsFixed(2)}%', 'F1 score', bg: LL.pastel(3)),
    ];
    final perRow = maxWidth >= 900 ? 5 : (maxWidth >= 560 ? 3 : 2);
    final w = (maxWidth - (perRow - 1) * 12) / perRow;
    return Wrap(spacing: 12, runSpacing: 12, children: [for (final c in cards) SizedBox(width: w, child: c)]);
  }

  Widget _stat(IconData icon, String value, String label, {bool dark = false, Color? bg}) {
    final fg = dark ? LL.onAccent : LL.text;
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 18),
      decoration: BoxDecoration(color: dark ? LL.accent : (bg ?? LL.surface), borderRadius: BorderRadius.circular(LL.radius)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(color: dark ? LL.highlight : Colors.white, shape: BoxShape.circle),
            child: Icon(icon, size: 20, color: LL.text),
          ),
          const SizedBox(height: 16),
          Text(value, style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: fg, letterSpacing: -0.4)),
          const SizedBox(height: 2),
          Text(label, style: TextStyle(fontSize: 12.5, color: dark ? Colors.white70 : LL.muted)),
        ],
      ),
    );
  }

  Widget _legend(List<String> labels, List<Color> colors) {
    return Wrap(
      spacing: 14,
      runSpacing: 6,
      children: [
        for (var i = 0; i < labels.length; i++)
          Row(mainAxisSize: MainAxisSize.min, children: [
            Container(width: 10, height: 10, decoration: BoxDecoration(color: colors[i], borderRadius: BorderRadius.circular(3))),
            const SizedBox(width: 6),
            Text(labels[i], style: const TextStyle(fontSize: 12, color: LL.muted)),
          ]),
      ],
    );
  }

  static const _metricColors = [Color(0xFF7C5CFF), Color(0xFFFF7A59), Color(0xFF2BB673), Color(0xFFFFB800)];

  Widget _axisText(String s) => Text(s, style: const TextStyle(fontSize: 11, color: LL.faint));

  // ── 1. Grouped bars: 4 metrics × 6 models ──
  Widget _barCard() {
    return LLCard(
      title: 'All models, all four metrics',
      subtitle: 'Test-set scores in percent. Hover a bar for the exact value.',
      trailing: _legend(_metricNames, _metricColors),
      // Phones: keep a readable width and scroll sideways, so model names never overlap.
      child: LayoutBuilder(
        builder: (context, box) => SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: SizedBox(
            width: box.maxWidth < 680 ? 680 : box.maxWidth,
            height: 300,
            child: BarChart(
              BarChartData(
                minY: 0,
                maxY: 100,
                barGroups: [
                  for (var i = 0; i < _models.length; i++)
                    BarChartGroupData(
                      x: i,
                      barsSpace: 4,
                      barRods: [
                        for (var k = 0; k < 4; k++)
                          BarChartRodData(
                            toY: _models[i].metric(k),
                            color: _metricColors[k],
                            width: 11,
                            borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
                          ),
                      ],
                    ),
                ],
                gridData: FlGridData(
                  drawVerticalLine: false,
                  horizontalInterval: 20,
                  getDrawingHorizontalLine: (_) => const FlLine(color: LL.line, strokeWidth: 1),
                ),
                borderData: FlBorderData(show: false),
                titlesData: FlTitlesData(
                  topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                  leftTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 42,
                      interval: 20,
                      getTitlesWidget: (v, meta) => SideTitleWidget(axisSide: meta.axisSide, child: _axisText('${v.toInt()}%')),
                    ),
                  ),
                  bottomTitles: AxisTitles(
                    sideTitles: SideTitles(
                      showTitles: true,
                      reservedSize: 30,
                      getTitlesWidget: (v, meta) {
                        final m = _models[v.toInt()];
                        return SideTitleWidget(
                          axisSide: meta.axisSide,
                          child: Text(_shortNames[m.name] ?? m.name,
                              style: TextStyle(
                                  fontSize: 11.5,
                                  color: m.name == _bestModel ? LL.text : LL.muted,
                                  fontWeight: m.name == _bestModel ? FontWeight.w700 : FontWeight.w400)),
                        );
                      },
                    ),
                  ),
                ),
                barTouchData: BarTouchData(
                  touchTooltipData: BarTouchTooltipData(
                    getTooltipColor: (_) => LL.accent,
                    getTooltipItem: (group, gi, rod, ri) => BarTooltipItem(
                      '${_shortNames[_models[gi].name] ?? _models[gi].name}\n${_metricNames[ri]}: ${rod.toY.toStringAsFixed(2)}%',
                      const TextStyle(color: Colors.white, fontSize: 12),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _chips(List<String> names, int selected, ValueChanged<int> onSelect) {
    return Wrap(spacing: 6, runSpacing: 6, children: [
      for (var i = 0; i < names.length; i++)
        ChoiceChip(
          label: Text(names[i], style: TextStyle(fontSize: 12, color: selected == i ? LL.onAccent : LL.text)),
          selected: selected == i,
          selectedColor: LL.accent,
          backgroundColor: LL.hover,
          showCheckmark: false,
          side: BorderSide.none,
          shape: const StadiumBorder(),
          onSelected: (_) => onSelect(i),
        ),
    ]);
  }

  /// A model keeps the same colour in every chart (its position in the benchmark list).
  Color _modelColor(_ModelScore m) => LL.series[_models.indexOf(m) % LL.series.length];

  /// Bar chart of one value per model, with the value printed above each bar.
  /// All six models fit the card width at every screen size, with model names on two lines
  /// so neighbouring labels never touch.
  Widget _valueBars(List<_ModelScore> order, double Function(_ModelScore) value, {required double maxY}) {
    final phone = MediaQuery.sizeOf(context).width < 700;
    return SizedBox(
      height: phone ? 270 : 260,
      child: BarChart(
        BarChartData(
          minY: 0,
          maxY: maxY,
          barGroups: [
            for (var i = 0; i < order.length; i++)
              BarChartGroupData(
                x: i,
                showingTooltipIndicators: [0],
                barRods: [
                  BarChartRodData(
                    toY: value(order[i]),
                    color: _modelColor(order[i]),
                    width: phone ? 20 : 26,
                    borderRadius: const BorderRadius.vertical(top: Radius.circular(6)),
                  ),
                ],
              ),
          ],
          gridData: FlGridData(
            drawVerticalLine: false,
            horizontalInterval: maxY / 5,
            getDrawingHorizontalLine: (_) => const FlLine(color: LL.line, strokeWidth: 1),
          ),
          borderData: FlBorderData(show: false),
          titlesData: FlTitlesData(
            topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 42,
                interval: maxY / 5,
                getTitlesWidget: (v, meta) => SideTitleWidget(axisSide: meta.axisSide, child: _axisText('${v.toInt()}%')),
              ),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                // Two-line names at every width: on a laptop these charts are half-width cards,
                // too narrow for six one-line names.
                reservedSize: 40,
                getTitlesWidget: (v, meta) {
                  final m = order[v.toInt()];
                  final name = _shortNames[m.name] ?? m.name;
                  return SideTitleWidget(
                    axisSide: meta.axisSide,
                    child: Text(name.replaceFirst(' ', '\n'),
                        textAlign: TextAlign.center,
                        style: TextStyle(
                            fontSize: phone ? 10 : 11,
                            height: 1.15,
                            color: m.name == _bestModel ? LL.text : LL.muted,
                            fontWeight: m.name == _bestModel ? FontWeight.w700 : FontWeight.w400)),
                  );
                },
              ),
            ),
          ),
          // Values are always shown above the bars, so touch tooltips are off.
          barTouchData: BarTouchData(
            enabled: false,
            touchTooltipData: BarTouchTooltipData(
              getTooltipColor: (_) => Colors.transparent,
              tooltipPadding: EdgeInsets.zero,
              tooltipMargin: 4,
              getTooltipItem: (group, gi, rod, ri) => BarTooltipItem(
                '${rod.toY.toStringAsFixed(1)}%',
                TextStyle(color: LL.text, fontSize: phone ? 10 : 11.5, fontWeight: FontWeight.w700),
              ),
            ),
          ),
        ),
      ),
    );
  }

  // ── 1b. One metric at a time, models ranked ──
  Widget _metricBarCard() {
    final order = [..._models]..sort((a, b) => b.metric(_singleMetric).compareTo(a.metric(_singleMetric)));
    return LLCard(
      title: '${_metricNames[_singleMetric]} by model',
      subtitle: 'Ranked, highest first.',
      // Buttons in the body, not `trailing`: the side-by-side row sizes both cards by their
      // measured height, and a trailing widget that wraps under the title isn't counted.
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _chips(_metricNames, _singleMetric, (i) => setState(() => _singleMetric = i)),
          const SizedBox(height: 12),
          _valueBars(order, (m) => m.metric(_singleMetric), maxY: 100),
        ],
      ),
    );
  }

  // ── 1c. Error rate (100% − accuracy). Each product has one category, so this equals the Hamming loss. ──
  Widget _errorRateCard() {
    final order = [..._models]..sort((a, b) => (100 - a.accuracy).compareTo(100 - b.accuracy));
    final worst = 100 - order.last.accuracy;
    final maxY = ((worst / 10).ceil() * 10).clamp(10, 100).toDouble();
    return LLCard(
      title: 'Error rate',
      subtitle: '100% − accuracy on the test set. Lower is better.',
      child: _valueBars(order, (m) => 100 - m.accuracy, maxY: maxY),
    );
  }

  // ── 2b. One small radar per model ──
  static const _radarMin = 40.0;

  Widget _miniRadar(_ModelScore m) {
    final color = _modelColor(m);
    return Column(
      children: [
        Text(_shortNames[m.name] ?? m.name, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: color)),
        const SizedBox(height: 2),
        Text('F1 ${m.f1.toStringAsFixed(1)}%', style: const TextStyle(fontSize: 11.5, color: LL.muted)),
        const SizedBox(height: 18), // room for the 'Acc.' axis label above the circle
        // Side padding keeps the 'Prec.' and 'F1' axis labels inside this tile, clear of the next radar.
        Container(
          height: 170,
          padding: const EdgeInsets.symmetric(horizontal: 22),
          child: RadarChart(
            RadarChartData(
              radarShape: RadarShape.circle,
              tickCount: 3,
              ticksTextStyle: const TextStyle(fontSize: 9, color: Colors.transparent),
              tickBorderData: const BorderSide(color: LL.line),
              gridBorderData: const BorderSide(color: LL.line, width: 1),
              radarBorderData: const BorderSide(color: LL.line),
              titleTextStyle: const TextStyle(fontSize: 10.5, color: LL.muted, fontWeight: FontWeight.w500),
              titlePositionPercentageOffset: 0.14,
              getTitle: (i, _) => RadarChartTitle(text: const ['Acc.', 'Prec.', 'Recall', 'F1'][i]),
              dataSets: [
                // Fixed 40–100 scale, the same in every radar, so their shapes can be compared.
                RadarDataSet(
                  dataEntries: List.generate(4, (_) => const RadarEntry(value: _radarMin)),
                  fillColor: Colors.transparent,
                  borderColor: Colors.transparent,
                  entryRadius: 0,
                ),
                RadarDataSet(
                  dataEntries: List.generate(4, (_) => const RadarEntry(value: 100)),
                  fillColor: Colors.transparent,
                  borderColor: Colors.transparent,
                  entryRadius: 0,
                ),
                RadarDataSet(
                  dataEntries: [for (var k = 0; k < 4; k++) RadarEntry(value: m.metric(k))],
                  fillColor: color.withValues(alpha: 0.22),
                  borderColor: color,
                  borderWidth: 2,
                  entryRadius: 2.5,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _radarGridCard() {
    return LLCard(
      title: 'Each model on its own',
      subtitle: 'Same scale in every chart: ${_radarMin.toInt()}% at the centre, 100% at the edge.',
      child: LayoutBuilder(builder: (context, box) {
        final perRow = box.maxWidth >= 700 ? 3 : 2;
        final w = (box.maxWidth - (perRow - 1) * 16) / perRow;
        return Wrap(
          spacing: 16,
          runSpacing: 24,
          children: [for (final m in _models) SizedBox(width: w, child: _miniRadar(m))],
        );
      }),
    );
  }

  // ── 7. Words the Linear SVM weighs most for a category (its "feature importance") ──
  Widget _topTermsCard() {
    if (_topTerms.isEmpty) {
      return LLCard(
        title: 'Top words per category',
        child: Text(_topTermsError ?? 'Loading…', style: const TextStyle(fontSize: 13, color: LL.muted)),
      );
    }
    final cat = _topTerms[_termCategory];
    final maxW = cat.terms.isEmpty ? 1.0 : cat.terms.first.$2;
    return LLCard(
      title: 'Top words per category',
      subtitle: 'Linear SVM weights: the words that most push a product into this category.',
      trailing: DropdownButton<int>(
        value: _termCategory,
        underline: const SizedBox.shrink(),
        borderRadius: BorderRadius.circular(LL.radius),
        style: const TextStyle(fontSize: 13, color: LL.text),
        items: [
          for (var i = 0; i < _topTerms.length; i++) DropdownMenuItem(value: i, child: Text(_topTerms[i].category)),
        ],
        onChanged: (i) => setState(() => _termCategory = i ?? 0),
      ),
      child: Column(
        children: [
          for (var i = 0; i < cat.terms.length; i++)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(children: [
                SizedBox(
                  width: 120,
                  child: Text(cat.terms[i].$1, textAlign: TextAlign.right, style: const TextStyle(fontSize: 12.5, color: LL.text)),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: LayoutBuilder(
                    builder: (context, box) => Row(children: [
                      Container(
                        width: (box.maxWidth - 48) * (cat.terms[i].$2 / maxW),
                        height: 18,
                        decoration: BoxDecoration(
                          // Darkest for the strongest word, lighter down the list.
                          color: Color.lerp(LL.violet, const Color(0xFFD9CFFF), i / (cat.terms.length - 1 == 0 ? 1 : cat.terms.length - 1)),
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text(cat.terms[i].$2.toStringAsFixed(2), style: LL.mono(size: 11.5)),
                    ]),
                  ),
                ),
              ]),
            ),
        ],
      ),
    );
  }

  // ── 2. Radar: 6 models on the 4 metrics ──
  Widget _radarCard() {
    const colors = LL.series;
    return LLCard(
      title: 'Radar comparison',
      subtitle: 'Each line is one model. Scale runs from 50% (centre) to 100% (edge).',
      child: Column(
        children: [
          SizedBox(
            height: 300,
            child: RadarChart(
              RadarChartData(
                radarShape: RadarShape.polygon,
                tickCount: 5,
                ticksTextStyle: const TextStyle(fontSize: 9, color: Colors.transparent),
                tickBorderData: const BorderSide(color: Colors.transparent),
                gridBorderData: const BorderSide(color: LL.line, width: 1),
                radarBorderData: const BorderSide(color: LL.line),
                titleTextStyle: const TextStyle(fontSize: 12, color: LL.muted, fontWeight: FontWeight.w500),
                titlePositionPercentageOffset: 0.12,
                getTitle: (i, _) => RadarChartTitle(text: _metricNames[i]),
                dataSets: [
                  // Fixed scale 50–100 so the models' differences are visible.
                  RadarDataSet(
                    dataEntries: List.generate(4, (_) => const RadarEntry(value: 50)),
                    fillColor: Colors.transparent,
                    borderColor: Colors.transparent,
                    entryRadius: 0,
                  ),
                  RadarDataSet(
                    dataEntries: List.generate(4, (_) => const RadarEntry(value: 100)),
                    fillColor: Colors.transparent,
                    borderColor: Colors.transparent,
                    entryRadius: 0,
                  ),
                  for (var i = 0; i < _models.length; i++)
                    RadarDataSet(
                      dataEntries: [for (var k = 0; k < 4; k++) RadarEntry(value: _models[i].metric(k))],
                      fillColor: colors[i].withValues(alpha: _models[i].name == _bestModel ? 0.12 : 0.03),
                      borderColor: colors[i],
                      borderWidth: _models[i].name == _bestModel ? 2.6 : 1.6,
                      entryRadius: 2.5,
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          _legend([for (final m in _models) _shortNames[m.name] ?? m.name], colors.take(_models.length).toList()),
        ],
      ),
    );
  }

  // ── 3. Pie: test set by category ──
  Widget _pieCard() {
    final total = _testSize;
    // On phones the legend goes under the pie, so category names get the full width.
    final phone = MediaQuery.sizeOf(context).width < 700;
    final pie = SizedBox(
      width: 190,
      height: 220,
      child: PieChart(
        PieChartData(
          centerSpaceRadius: 46,
          sectionsSpace: 2,
          sections: [
            for (var i = 0; i < _classScores.length; i++)
              PieChartSectionData(
                value: _classScores[i].support.toDouble(),
                color: LL.series[i % LL.series.length],
                radius: 44,
                title: '${_classScores[i].support}',
                titleStyle: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: i == 9 ? LL.text : Colors.white,
                ),
              ),
          ],
        ),
      ),
    );
    final legend = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var i = 0; i < _classScores.length; i++)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 3),
            child: Row(children: [
              Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(color: LL.series[i % LL.series.length], borderRadius: BorderRadius.circular(3))),
              const SizedBox(width: 8),
              Expanded(child: Text(_classScores[i].name, style: const TextStyle(fontSize: 12, color: LL.text))),
              Text('${(100 * _classScores[i].support / total).toStringAsFixed(0)}%', style: const TextStyle(fontSize: 12, color: LL.muted)),
            ]),
          ),
      ],
    );
    return LLCard(
      title: 'Test set by category',
      subtitle: '$total products held out for testing (from the confusion matrix).',
      child: phone
          ? Column(children: [Center(child: pie), const SizedBox(height: 12), legend])
          : Row(children: [pie, const SizedBox(width: 16), Expanded(child: legend)]),
    );
  }

  // ── 4. Histogram: how many categories fall in each score band ──
  static const _bands = ['< 60', '60–70', '70–80', '80–90', '90–100'];

  int _band(double v) {
    if (v < 60) return 0;
    if (v < 70) return 1;
    if (v < 80) return 2;
    if (v < 90) return 3;
    return 4;
  }

  Widget _histogramCard() {
    final names = ['Precision', 'Recall', 'F1 score'];
    final counts = List.filled(_bands.length, 0);
    for (final c in _classScores) {
      counts[_band(c.metric(_histMetric))]++;
    }
    final maxCount = counts.reduce((a, b) => a > b ? a : b);
    return LLCard(
      title: 'Histogram of category scores',
      subtitle: '$_bestModel: number of categories in each score band (%).',
      trailing: Wrap(spacing: 6, children: [
        for (var i = 0; i < names.length; i++)
          ChoiceChip(
            label: Text(names[i], style: TextStyle(fontSize: 12, color: _histMetric == i ? LL.onAccent : LL.text)),
            selected: _histMetric == i,
            selectedColor: LL.accent,
            backgroundColor: LL.hover,
            showCheckmark: false,
            side: BorderSide.none,
            shape: const StadiumBorder(),
            onSelected: (_) => setState(() => _histMetric = i),
          ),
      ]),
      child: SizedBox(
        height: 240,
        child: BarChart(
          BarChartData(
            minY: 0,
            maxY: (maxCount + 1).toDouble(),
            barGroups: [
              for (var b = 0; b < _bands.length; b++)
                BarChartGroupData(x: b, barRods: [
                  BarChartRodData(
                    toY: counts[b].toDouble(),
                    color: b == 4 ? LL.violet : const Color(0xFFCFC3FF),
                    width: 34,
                    borderRadius: const BorderRadius.vertical(top: Radius.circular(8)),
                  ),
                ]),
            ],
            gridData: FlGridData(
              drawVerticalLine: false,
              horizontalInterval: 1,
              getDrawingHorizontalLine: (_) => const FlLine(color: LL.line, strokeWidth: 1),
            ),
            borderData: FlBorderData(show: false),
            titlesData: FlTitlesData(
              topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
              rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
              leftTitles: AxisTitles(
                sideTitles: SideTitles(
                  showTitles: true,
                  reservedSize: 26,
                  interval: 1,
                  getTitlesWidget: (v, meta) => SideTitleWidget(axisSide: meta.axisSide, child: _axisText('${v.toInt()}')),
                ),
              ),
              bottomTitles: AxisTitles(
                sideTitles: SideTitles(
                  showTitles: true,
                  reservedSize: 28,
                  // The subtitle says the bands are in %, so the labels stay short enough not to touch on a phone.
                  getTitlesWidget: (v, meta) => SideTitleWidget(axisSide: meta.axisSide, child: _axisText(_bands[v.toInt()])),
                ),
              ),
            ),
            barTouchData: BarTouchData(
              touchTooltipData: BarTouchTooltipData(
                getTooltipColor: (_) => LL.accent,
                getTooltipItem: (g, gi, rod, ri) => BarTooltipItem(
                  '${rod.toY.toInt()} categor${rod.toY.toInt() == 1 ? 'y' : 'ies'}',
                  const TextStyle(color: Colors.white, fontSize: 12),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  // ── 5. Per-category scores (the data behind the histogram) ──
  Widget _perClassCard() {
    final names = ['Precision', 'Recall', 'F1 score'];
    final sorted = [..._classScores]..sort((a, b) => b.metric(_histMetric).compareTo(a.metric(_histMetric)));
    return LLCard(
      title: '${names[_histMetric]} by category',
      subtitle: '$_bestModel on the test set.',
      child: Column(
        children: [
          for (final c in sorted)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 5),
              child: Row(children: [
                SizedBox(width: 170, child: Text(c.name, style: const TextStyle(fontSize: 12.5, color: LL.text))),
                Expanded(
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: LinearProgressIndicator(
                      value: c.metric(_histMetric) / 100,
                      minHeight: 10,
                      backgroundColor: LL.hover,
                      color: c.metric(_histMetric) >= 90 ? LL.violet : LL.accentSoft,
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                SizedBox(
                  width: 52,
                  child: Text('${c.metric(_histMetric).toStringAsFixed(1)}%',
                      textAlign: TextAlign.right, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: LL.text)),
                ),
              ]),
            ),
        ],
      ),
    );
  }

  // ── 6. Leaderboard ──
  Widget _leaderboardCard() {
    const head = TextStyle(fontSize: 12, color: LL.faint, fontWeight: FontWeight.w500);
    const cell = TextStyle(fontSize: 13.5, color: LL.text);
    final sorted = [..._models]..sort((a, b) => b.f1.compareTo(a.f1));
    return LLCard(
      title: 'Leaderboard',
      subtitle: 'Sorted by F1 score. Cross-validation is 5-fold on all $_totalSamples products.',
      child: LayoutBuilder(
        builder: (context, box) => SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: ConstrainedBox(
            // Fill the card on wide screens; scroll sideways on phones.
            constraints:
                BoxConstraints(minWidth: box.maxWidth < 760 ? 760 : box.maxWidth, maxWidth: box.maxWidth < 760 ? 760 : box.maxWidth),
            child: Table(
              columnWidths: const {0: FlexColumnWidth(2.4)},
              defaultVerticalAlignment: TableCellVerticalAlignment.middle,
              children: [
                TableRow(children: [
                  for (final h in ['Model', 'Accuracy', 'Precision', 'Recall', 'F1 score', 'CV (mean ± sd)'])
                    Padding(padding: const EdgeInsets.only(bottom: 10), child: Text(h, style: head)),
                ]),
                for (final m in sorted)
                  TableRow(
                    decoration: BoxDecoration(
                      color: m.name == _bestModel ? LL.hover : null,
                      border: const Border(top: BorderSide(color: LL.line)),
                    ),
                    children: [
                      Padding(
                        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
                        child: Row(children: [
                          Text(m.name, style: cell.copyWith(fontWeight: m.name == _bestModel ? FontWeight.w700 : FontWeight.w400)),
                          if (m.name == _bestModel) ...[
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(color: LL.accent, borderRadius: BorderRadius.circular(20)),
                              child: const Text('In use', style: TextStyle(fontSize: 11, color: LL.onAccent)),
                            ),
                          ],
                        ]),
                      ),
                      for (final v in [m.accuracy, m.precision, m.recall, m.f1]) Text('${v.toStringAsFixed(2)}%', style: cell),
                      Text('${m.cvMean.toStringAsFixed(2)} ± ${m.cvStd.toStringAsFixed(2)}%', style: cell),
                    ],
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // ── 7. Confusion matrix ──
  Widget _confusionCard() {
    final n = _classes.length;
    return LLCard(
      title: 'Confusion matrix',
      subtitle: '$_bestModel. Rows: true category · columns: predicted. Numbers are product counts.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (var r = 0; r < n; r++)
            Padding(
              padding: const EdgeInsets.only(bottom: 3),
              child: Row(children: [
                SizedBox(width: 150, child: Text(_classes[r], style: const TextStyle(fontSize: 11.5, color: LL.muted))),
                for (var c = 0; c < n; c++)
                  Expanded(
                    child: AspectRatio(
                      aspectRatio: 1,
                      child: Container(
                        margin: const EdgeInsets.all(1.5),
                        decoration: BoxDecoration(
                          color: _cellColor(r, c),
                          borderRadius: BorderRadius.circular(5),
                        ),
                        alignment: Alignment.center,
                        child: _matrix[r][c] == 0
                            ? null
                            : Text('${_matrix[r][c]}',
                                style: TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: r == c ? Colors.white : LL.danger)),
                      ),
                    ),
                  ),
              ]),
            ),
          const SizedBox(height: 8),
          const Text('Dark: correct · red numbers: mistakes.', style: TextStyle(fontSize: 11.5, color: LL.faint)),
        ],
      ),
    );
  }

  Color _cellColor(int r, int c) {
    final v = _matrix[r][c];
    if (v == 0) return LL.hover;
    if (r == c) return LL.violet;
    return LL.danger.withValues(alpha: 0.12);
  }

  // ── 8. Try the classifier ──
  Widget _classifyCard() {
    final result = _classifyResult;
    return LLCard(
      title: 'Try the classifier',
      subtitle: 'Type a product name; $_bestModel predicts its category.',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          TextField(
            controller: _classifyController,
            onSubmitted: (_) => _classify(),
            onChanged: (_) {
              if (_classifyError != null) setState(() => _classifyError = null);
            },
            decoration: InputDecoration(
              hintText: 'Tata Salt Vacuum Evaporated 1kg',
              filled: true,
              fillColor: LL.hover,
              isDense: true,
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(LL.radiusSmall), borderSide: BorderSide.none),
            ),
          ),
          const SizedBox(height: 10),
          FilledButton(
            onPressed: _classifying ? null : _classify,
            style: FilledButton.styleFrom(
              backgroundColor: LL.accent,
              foregroundColor: LL.onAccent,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(LL.radiusSmall)),
            ),
            child: Text(_classifying ? 'Classifying…' : 'Classify'),
          ),
          if (_classifyError != null) ...[
            const SizedBox(height: 10),
            Text(_classifyError!, style: const TextStyle(fontSize: 13, color: LL.danger)),
          ],
          if (result != null) ...[
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(color: LL.hover, borderRadius: BorderRadius.circular(LL.radiusSmall)),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('${result['input_text'] ?? ''}', style: const TextStyle(fontSize: 12.5, color: LL.muted)),
                  const SizedBox(height: 4),
                  Text('${result['predicted_category'] ?? ''}',
                      style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: LL.text)),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}
