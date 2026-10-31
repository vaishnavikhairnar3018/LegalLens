/// Inspections screen — every inspection the officer can see, newest first.
///
/// Filter (all / compliant / not compliant) runs on the server; search runs over the loaded
/// rows. Loading, error and empty states are explicit; no sample data is ever shown.
library;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../config/theme.dart';
import '../core/api/api_endpoints.dart';
import '../core/api/dio_client.dart';
import '../core/utils/product_formatter.dart';
import '../widgets/inspection_widgets.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

enum _Filter { all, compliant, notCompliant }

class _HistoryScreenState extends State<HistoryScreen> {
  static const _pageSize = 100; // the API's maximum per request

  final _searchController = TextEditingController();
  _Filter _filter = _Filter.all;
  String _query = '';
  bool _loading = true;
  String? _error;
  List<Map<String, dynamic>> _inspections = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final compliantOnly = switch (_filter) {
      _Filter.all => '',
      _Filter.compliant => '&compliant_only=true',
      _Filter.notCompliant => '&compliant_only=false',
    };
    try {
      final res = await DioClient.instance.dio.get('${ApiEndpoints.inspections}?limit=$_pageSize$compliantOnly');
      if (!mounted) return;
      setState(() {
        _inspections = (res.data as List).cast<Map<String, dynamic>>();
        _loading = false;
      });
    } on DioException catch (e) {
      debugPrint('Inspections load failed: ${e.type} ${e.response?.statusCode}');
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.response?.statusCode == 401 ? 'Your session expired. Sign in again.' : 'Couldn\'t reach the server.';
      });
    }
  }

  List<Map<String, dynamic>> get _visible {
    final q = _query.trim().toLowerCase();
    if (q.isEmpty) return _inspections;
    return _inspections.where((insp) {
      return inspectionDisplayName(insp, maxLength: 200).toLowerCase().contains(q) ||
          (insp['image_filename'] as String? ?? '').toLowerCase().contains(q) ||
          (insp['id'] as String? ?? '').toLowerCase().startsWith(q);
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.of(context).size.width >= 840;
    final pad = wide ? 32.0 : 16.0;

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
                      Text('Inspections',
                          style: TextStyle(fontSize: wide ? 30 : 24, fontWeight: FontWeight.w700, color: LL.text, letterSpacing: -0.6)),
                      SizedBox(height: wide ? 20 : 14),
                      _controls(wide),
                      const SizedBox(height: 16),
                      _body(wide),
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

  Widget _controls(bool wide) {
    final search = TextField(
      controller: _searchController,
      onChanged: (v) => setState(() => _query = v),
      decoration: InputDecoration(
        hintText: 'Search by product, file name or ID',
        prefixIcon: const Icon(Icons.search, size: 20, color: LL.muted),
        suffixIcon: _query.isEmpty
            ? null
            : IconButton(
                tooltip: 'Clear search',
                icon: const Icon(Icons.close, size: 18, color: LL.muted),
                onPressed: () => setState(() {
                  _searchController.clear();
                  _query = '';
                }),
              ),
        filled: true,
        fillColor: LL.surface,
        isDense: true,
        contentPadding: const EdgeInsets.symmetric(vertical: 14),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(30), borderSide: BorderSide.none),
      ),
    );
    final filters = Wrap(spacing: 8, children: [
      _pill('All', _Filter.all),
      _pill('Compliant', _Filter.compliant),
      _pill('Not compliant', _Filter.notCompliant),
    ]);
    if (wide) {
      return Row(children: [Expanded(child: search), const SizedBox(width: 16), filters]);
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [search, const SizedBox(height: 12), filters]);
  }

  Widget _pill(String label, _Filter value) {
    final selected = _filter == value;
    return Material(
      color: selected ? LL.accent : LL.surface,
      shape: const StadiumBorder(),
      child: InkWell(
        customBorder: const StadiumBorder(),
        onTap: selected
            ? null
            : () {
                setState(() => _filter = value);
                _load();
              },
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
          child: Text(label,
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: selected ? LL.onAccent : LL.text)),
        ),
      ),
    );
  }

  Widget _body(bool wide) {
    if (_loading) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 64),
        child: Center(child: SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2, color: LL.accent))),
      );
    }
    if (_error != null) {
      return _message(_error!, action: 'Try again', onTap: _load);
    }
    if (_inspections.isEmpty) {
      return _filter == _Filter.all
          ? _message('No inspections yet', body: 'Scanned labels and their results will be listed here.', action: 'Scan a label', onTap: () => context.go('/scanner'))
          : _message('Nothing matches this filter', action: 'Show all', onTap: () {
              setState(() => _filter = _Filter.all);
              _load();
            });
    }

    final rows = _visible;
    final count = rows.length == _inspections.length
        ? '${_inspections.length} inspection${_inspections.length == 1 ? '' : 's'}'
        : '${rows.length} of ${_inspections.length} match "${_query.trim()}"';
    final capped = _inspections.length == _pageSize ? ' · showing the latest $_pageSize' : '';

    return LLCard(
      title: count,
      subtitle: capped.isEmpty ? null : capped.substring(3),
      padding: const EdgeInsets.fromLTRB(22, 22, 22, 12),
      child: rows.isEmpty
          ? const Padding(
              padding: EdgeInsets.symmetric(vertical: 24),
              child: Center(child: Text('No inspections match your search.', style: TextStyle(fontSize: 13, color: LL.muted))),
            )
          : Column(children: [
              if (wide) _tableHeader(),
              for (var i = 0; i < rows.length; i++) ...[
                if (i > 0 || wide) const Divider(height: 1, thickness: 1, color: LL.line),
                wide ? _tableRow(rows[i]) : _listRow(rows[i]),
              ],
            ]),
    );
  }

  Widget _tableHeader() {
    const style = TextStyle(fontSize: 12, color: LL.faint);
    return const Padding(
      padding: EdgeInsets.fromLTRB(8, 0, 8, 10),
      child: Row(children: [
        SizedBox(width: 96, child: Text('ID', style: style)),
        Expanded(child: Text('Product', style: style)),
        SizedBox(width: 80, child: Text('Photos', style: style)),
        SizedBox(width: 72, child: Text('Fields', style: style)),
        SizedBox(width: 110, child: Text('Date', style: style)),
        SizedBox(width: 96, child: Text('Result', style: style, textAlign: TextAlign.right)),
      ]),
    );
  }

  static int _photoCount(Map<String, dynamic> insp) {
    final name = insp['image_filename'] as String? ?? '';
    return name.isEmpty ? 0 : name.split(', ').length;
  }

  Widget _tableRow(Map<String, dynamic> insp) {
    return InkWell(
      onTap: () => context.push('/results', extra: insp),
      hoverColor: LL.hover,
      borderRadius: BorderRadius.circular(LL.radiusSmall),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 14),
        child: Row(children: [
          SizedBox(width: 96, child: Text(shortInspectionId(insp), style: LL.mono())),
          Expanded(
            child: Text(inspectionDisplayName(insp, maxLength: 60),
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: LL.text)),
          ),
          SizedBox(width: 80, child: Text('${_photoCount(insp)}', style: const TextStyle(fontSize: 14, color: LL.muted))),
          SizedBox(
            width: 72,
            child: Text('${insp['compliant_fields'] ?? 0}/${insp['total_fields'] ?? 0}',
                style: const TextStyle(fontSize: 14, color: LL.muted, fontFeatures: [FontFeature.tabularFigures()])),
          ),
          SizedBox(width: 110, child: Text(formatInspectionDate(insp['created_at'] as String?), style: const TextStyle(fontSize: 14, color: LL.muted))),
          SizedBox(width: 96, child: Align(alignment: Alignment.centerRight, child: ResultPill(inspectionResult(insp)))),
        ]),
      ),
    );
  }

  Widget _listRow(Map<String, dynamic> insp) {
    final photos = _photoCount(insp);
    return InkWell(
      onTap: () => context.push('/results', extra: insp),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 14),
        child: Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(inspectionDisplayName(insp, maxLength: 40),
                  style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500, color: LL.text)),
              const SizedBox(height: 3),
              Text(
                '${formatInspectionDate(insp['created_at'] as String?)} · ${insp['compliant_fields'] ?? 0}/${insp['total_fields'] ?? 0} fields'
                '${photos > 1 ? ' · $photos photos' : ''}',
                style: const TextStyle(fontSize: 12, color: LL.muted),
              ),
            ]),
          ),
          const SizedBox(width: 12),
          ResultPill(inspectionResult(insp)),
        ]),
      ),
    );
  }

  Widget _message(String title, {String? body, required String action, required VoidCallback onTap}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 40),
      decoration: LL.card(),
      child: Column(children: [
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
      ]),
    );
  }
}
