/// Results screen — the inspection slip for one scan.
///
/// Product, date and a result stamp at the top, then every declaration with
/// its status and the reason an officer needs to read, then the evidence hash
/// and the notice downloads.
library;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../config/theme.dart';
import '../core/api/api_endpoints.dart';
import '../core/api/dio_client.dart';
import '../core/utils/file_downloader.dart';
import '../core/utils/product_formatter.dart';
import '../models/scan_result_model.dart';

class ResultsScreen extends StatefulWidget {
  final Map<String, dynamic> report;

  const ResultsScreen({super.key, required this.report});

  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

enum _Status { pass, violation, review }

class _ResultsScreenState extends State<ResultsScreen> {
  late ScanResultModel _result;
  bool _loadingDetail = false;
  String? _detailError;
  bool _downloadingPdf = false;
  bool _downloadingDocx = false;

  @override
  void initState() {
    super.initState();
    _result = ScanResultModel.fromJson(widget.report);
    // Rows opened from History carry only the summary; fetch the declarations.
    if (_result.declarations.isEmpty && _result.scanId.isNotEmpty) {
      _loadDetail();
    }
  }

  Future<void> _loadDetail() async {
    setState(() {
      _loadingDetail = true;
      _detailError = null;
    });
    try {
      final response = await DioClient.instance.dio.get(ApiEndpoints.inspectionDetail(_result.scanId));
      if (!mounted) return;
      setState(() {
        _result = ScanResultModel.fromJson(response.data as Map<String, dynamic>);
        _loadingDetail = false;
      });
    } on DioException catch (e) {
      debugPrint('Inspection detail failed: ${e.type} ${e.response?.statusCode}');
      if (!mounted) return;
      setState(() {
        _loadingDetail = false;
        _detailError = 'Couldn\'t load the declarations for this inspection.';
      });
    }
  }

  Future<void> _download({required bool docx}) async {
    if (_result.scanId.isEmpty) return;
    setState(() => docx ? _downloadingDocx = true : _downloadingPdf = true);
    final ext = docx ? 'docx' : 'pdf';
    final mime = docx
        ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        : 'application/pdf';
    try {
      final response = await DioClient.instance.dio.get<List<int>>(
        docx ? ApiEndpoints.inspectionDocx(_result.scanId) : ApiEndpoints.inspectionPdf(_result.scanId),
        options: Options(responseType: ResponseType.bytes, headers: {'Accept': mime}),
      );
      final bytes = response.data;
      if (bytes == null || bytes.isEmpty) {
        _toast('The server returned an empty file.');
      } else {
        downloadFile(bytes, '${_documentName.replaceAll(' ', '_')}_$_shortId.$ext', mime);
        _toast('${docx ? 'Word' : 'PDF'} file downloaded');
      }
    } on DioException catch (e) {
      final detail = e.response?.data is Map ? (e.response!.data as Map)['detail'] : null;
      _toast(detail is String ? detail : 'Couldn\'t download the file. Try again.');
    } finally {
      if (mounted) setState(() => docx ? _downloadingDocx = false : _downloadingPdf = false);
    }
  }

  void _toast(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message), duration: const Duration(seconds: 3)));
  }

  // ── Derived state ──
  String get _shortId => _result.scanId.length > 8 ? _result.scanId.substring(0, 8) : _result.scanId;

  _Status _statusOf(DeclarationFieldModel d) {
    if (!d.compliant) return _Status.violation;
    if (d.needsReview) return _Status.review;
    return _Status.pass;
  }

  _Status get _overall {
    final decls = _result.declarations;
    if (decls.isEmpty) {
      if (_result.overallCompliant) return _Status.pass;
      return _result.nonCompliantFields > 0 ? _Status.violation : _Status.review;
    }
    if (decls.any((d) => _statusOf(d) == _Status.violation)) return _Status.violation;
    if (decls.any((d) => _statusOf(d) == _Status.review)) return _Status.review;
    return _Status.pass;
  }

  String get _documentName => _overall == _Status.pass ? 'Compliance certificate' : 'Non-compliance notice';

  static const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  String get _dateText {
    final dt = DateTime.tryParse(_result.timestamp)?.toLocal();
    if (dt == null) return '';
    final hh = dt.hour.toString().padLeft(2, '0');
    final mm = dt.minute.toString().padLeft(2, '0');
    return '${dt.day} ${_months[dt.month - 1]} ${dt.year}, $hh:$mm';
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.of(context).size.width >= 840;

    return Scaffold(
      backgroundColor: LL.paper,
      appBar: AppBar(
        backgroundColor: LL.paper,
        surfaceTintColor: Colors.transparent,
        leading: IconButton(
          tooltip: 'Back',
          icon: const Icon(Icons.arrow_back, color: LL.text),
          onPressed: () => context.canPop() ? context.pop() : context.go('/home'),
        ),
        titleSpacing: 0,
        title: Row(
          children: [
            const Text('Inspection', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w500, color: LL.text)),
            const SizedBox(width: 10),
            if (_shortId.isNotEmpty) Text(_shortId, style: LL.mono(size: 13)),
          ],
        ),
      ),
      body: ListView(
        padding: EdgeInsets.fromLTRB(wide ? 40 : 16, 8, wide ? 40 : 16, 32),
        children: [
          Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 760),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _slip(),
                  const SizedBox(height: 16),
                  _actions(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _slip() {
    final decls = _result.declarations;
    final passing = decls.where((d) => _statusOf(d) == _Status.pass).length;
    final total = decls.isNotEmpty ? decls.length : _result.totalFields;
    final passCount = decls.isNotEmpty ? passing : _result.compliantFields;

    return Container(
      decoration: BoxDecoration(
        color: LL.surface,
        border: Border.all(color: LL.line),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header: product, date, stamp
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 18),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        (_result.productName ?? '').trim().isNotEmpty
                            ? _result.productName!.trim()
                            : formatProductName(_result.imageFilename, maxLength: 60),
                        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600, color: LL.text, letterSpacing: -0.3),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        [if (_dateText.isNotEmpty) _dateText, '$passCount of $total declarations pass'].join(' · '),
                        style: const TextStyle(fontSize: 13, color: LL.muted),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 16),
                _Stamp(_overall),
              ],
            ),
          ),
          const Divider(height: 1, thickness: 1, color: LL.line),

          // Declarations
          if (_loadingDetail)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 32),
              child: Center(
                child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: LL.accent)),
              ),
            )
          else if (_detailError != null)
            Padding(
              padding: const EdgeInsets.all(20),
              child: Row(
                children: [
                  Expanded(child: Text(_detailError!, style: const TextStyle(fontSize: 13, color: LL.danger))),
                  TextButton(
                    onPressed: _loadDetail,
                    style: TextButton.styleFrom(foregroundColor: LL.accent),
                    child: const Text('Try again'),
                  ),
                ],
              ),
            )
          else if (decls.isEmpty)
            const Padding(
              padding: EdgeInsets.all(20),
              child: Text('No text was detected on this label.', style: TextStyle(fontSize: 14, color: LL.muted)),
            )
          else
            for (var i = 0; i < decls.length; i++) ...[
              if (i > 0) const Divider(height: 1, thickness: 1, indent: 20, endIndent: 20, color: LL.line),
              _declarationRow(decls[i]),
            ],

          // Evidence: every photo of a product inspection, or the single photo's hash
          if (_result.photos.isNotEmpty) ...[
            const Divider(height: 1, thickness: 1, color: LL.line),
            _photoEvidence(),
          ] else if ((_result.imageHashSha256 ?? '').isNotEmpty) ...[
            const Divider(height: 1, thickness: 1, color: LL.line),
            _evidence(_result.imageHashSha256!),
          ],
        ],
      ),
    );
  }

  Widget _declarationRow(DeclarationFieldModel d) {
    final status = _statusOf(d);
    final reason = d.primaryReason;
    final (IconData icon, Color color) = switch (status) {
      _Status.pass => (Icons.check, LL.accent),
      _Status.violation => (Icons.close, LL.danger),
      _Status.review => (Icons.help_outline, LL.warning),
    };
    final font = d.fontHeightMm == null
        ? null
        : d.requiredFontHeightMm == null
            ? '${d.fontHeightMm!.toStringAsFixed(1)} mm'
            : '${d.fontHeightMm!.toStringAsFixed(1)} mm (min ${d.requiredFontHeightMm!.toStringAsFixed(1)})';

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(padding: const EdgeInsets.only(top: 1), child: Icon(icon, size: 18, color: color)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Text(d.displayName, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: LL.text)),
                    ),
                    if (font != null) ...[
                      const SizedBox(width: 12),
                      Text(font, style: LL.mono(size: 12)),
                    ],
                  ],
                ),
                if (d.value != null && d.value!.isNotEmpty) ...[
                  const SizedBox(height: 3),
                  Text(d.value!, style: const TextStyle(fontSize: 13, color: LL.muted)),
                ] else if (!d.detected) ...[
                  const SizedBox(height: 3),
                  const Text('Not found on this label', style: TextStyle(fontSize: 13, color: LL.muted)),
                ],
                if (reason != null) ...[
                  const SizedBox(height: 6),
                  Text(
                    reason,
                    style: TextStyle(
                      fontSize: 12.5,
                      height: 1.4,
                      color: status == _Status.violation
                          ? LL.danger
                          : status == _Status.review
                              ? LL.warning
                              : LL.muted,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _photoEvidence() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 14, 8, 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Photos, SHA-256 hashed before processing', style: TextStyle(fontSize: 12, color: LL.faint)),
          const SizedBox(height: 6),
          for (final p in _result.photos)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text.rich(
                          TextSpan(children: [
                            TextSpan(text: p.filename, style: const TextStyle(fontSize: 13, color: LL.text)),
                            TextSpan(
                              text: p.hasMarker ? '  ·  40 mm marker' : '  ·  text only',
                              style: TextStyle(fontSize: 12, color: p.hasMarker ? LL.accent : LL.muted),
                            ),
                          ]),
                        ),
                        const SizedBox(height: 2),
                        SelectableText(p.sha256, style: LL.mono(size: 11.5, color: LL.muted)),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Copy hash',
                    icon: const Icon(Icons.copy_outlined, size: 16, color: LL.muted),
                    onPressed: () {
                      Clipboard.setData(ClipboardData(text: p.sha256));
                      _toast('Hash copied');
                    },
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _evidence(String hash) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 14, 8, 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Image SHA-256, hashed before processing', style: TextStyle(fontSize: 12, color: LL.faint)),
                const SizedBox(height: 4),
                SelectableText(hash, style: LL.mono(size: 12, color: LL.text)),
              ],
            ),
          ),
          IconButton(
            tooltip: 'Copy hash',
            icon: const Icon(Icons.copy_outlined, size: 18, color: LL.muted),
            onPressed: () {
              Clipboard.setData(ClipboardData(text: hash));
              _toast('Hash copied');
            },
          ),
        ],
      ),
    );
  }

  Widget _actions() {
    Widget spinner(Color c) => SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: c));
    final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(8));
    const pad = EdgeInsets.symmetric(horizontal: 16, vertical: 14);

    final word = OutlinedButton.icon(
          onPressed: _downloadingDocx ? null : () => _download(docx: true),
          style: OutlinedButton.styleFrom(
            foregroundColor: LL.text,
            side: const BorderSide(color: LL.line),
            backgroundColor: LL.surface,
            padding: pad,
            shape: shape,
          ),
          icon: _downloadingDocx ? spinner(LL.muted) : const Icon(Icons.description_outlined, size: 18),
          label: const Text('Word file', style: TextStyle(fontSize: 14)),
        );
    final pdf = FilledButton.icon(
          onPressed: _downloadingPdf ? null : () => _download(docx: false),
          style: FilledButton.styleFrom(
            backgroundColor: LL.accent,
            foregroundColor: LL.onAccent,
            padding: pad,
            shape: shape,
          ),
          icon: _downloadingPdf ? spinner(LL.onAccent) : const Icon(Icons.download_outlined, size: 18),
          label: Text('$_documentName (PDF)', style: const TextStyle(fontSize: 14)),
        );

    // Phones: full-width stack with the notice first. Wider: side by side, right-aligned.
    if (MediaQuery.of(context).size.width < 600) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [pdf, const SizedBox(height: 10), word],
      );
    }
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [word, const SizedBox(width: 10), pdf],
    );
  }
}

/// The overall result, set like an inspector's rubber stamp.
class _Stamp extends StatelessWidget {
  final _Status status;
  const _Stamp(this.status);

  @override
  Widget build(BuildContext context) {
    final (String label, Color color) = switch (status) {
      _Status.pass => ('COMPLIANT', LL.accent),
      _Status.violation => ('VIOLATION', LL.danger),
      _Status.review => ('REVIEW', LL.warning),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        border: Border.all(color: color, width: 1.6),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, letterSpacing: 1.6, color: color),
      ),
    );
  }
}
