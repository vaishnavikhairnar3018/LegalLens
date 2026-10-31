/// Profile screen — the signed-in officer, their own inspection totals, and an LMPC quick
/// reference. Account details come from /auth/me and totals from /dashboard/summary
/// (scoped to the officer by the server). Citations match the Ministry's consolidated text of
/// the Legal Metrology (Packaged Commodities) Rules, 2011 with all amendments.
library;

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../config/app_config.dart';
import '../config/theme.dart';
import '../core/api/api_endpoints.dart';
import '../core/api/dio_client.dart';
import '../core/auth/auth_provider.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

/// Rule → what must be declared. Kept to the citations verified against the gazette text.
const _lmpcReference = [
  ('Rule 6(1)(a)', 'Name and address of the manufacturer, packer or importer'),
  ('Rule 6(1)(aa)', 'Country of origin, for imported products'),
  ('Rule 6(1)(b)', 'Common or generic name of the commodity'),
  ('Rule 6(1)(c)', 'Net quantity in a standard unit of weight, measure or number'),
  ('Rule 6(1)(d)', 'Month and year of manufacture'),
  ('Rule 6(1)(da)', 'Best before / use by date, where the commodity can become unfit'),
  ('Rule 6(1)(e)', 'Maximum retail price, inclusive of all taxes'),
  ('Rule 6(2)', 'Consumer care: name, address, telephone and e-mail'),
  ('Rule 6(11)', 'Unit sale price'),
  ('Rule 8(1)', 'Every declaration on the principal display panel'),
];

/// Rule 7(2) Table-I: minimum height of numerals and letters by PDP area.
const _fontTable = [
  ('up to 50 cm²', '1.0 mm'),
  ('50 – 100 cm²', '1.5 mm'),
  ('100 – 500 cm²', '2.5 mm'),
  ('500 – 2500 cm²', '4.0 mm'),
  ('above 2500 cm²', '6.0 mm'),
];

class _ProfileScreenState extends State<ProfileScreen> {
  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _me;
  Map<String, dynamic>? _summary;

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
      final results = await Future.wait([dio.get(ApiEndpoints.me), dio.get(ApiEndpoints.dashboardSummary)]);
      if (!mounted) return;
      setState(() {
        _me = results[0].data as Map<String, dynamic>;
        _summary = results[1].data as Map<String, dynamic>;
        _loading = false;
      });
    } on DioException catch (e) {
      debugPrint('Profile load failed: ${e.type} ${e.response?.statusCode}');
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.response?.statusCode == 401 ? 'Your session expired. Sign in again.' : 'Couldn\'t reach the server.';
      });
    }
  }

  void _signOut() {
    context.read<AuthProvider>().logout();
    context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.of(context).size.width >= 840;
    final pad = wide ? 32.0 : 16.0;

    Widget body;
    if (_loading) {
      body = const Padding(
        padding: EdgeInsets.symmetric(vertical: 64),
        child: Center(child: SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2, color: LL.accent))),
      );
    } else if (_error != null) {
      body = Container(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 40),
        decoration: LL.card(),
        child: Column(children: [
          Text(_error!, textAlign: TextAlign.center, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: LL.text)),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _load,
            style: FilledButton.styleFrom(backgroundColor: LL.accent, foregroundColor: LL.onAccent, shape: const StadiumBorder()),
            child: const Text('Try again'),
          ),
        ]),
      );
    } else {
      body = LayoutBuilder(builder: (context, c) {
        final twoUp = c.maxWidth >= 900;
        final left = Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          _accountCard(),
          const SizedBox(height: 16),
          _statsCard(),
          const SizedBox(height: 16),
          _sessionCard(),
        ]);
        final right = _referenceCard();
        return twoUp
            ? Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(flex: 5, child: left),
                const SizedBox(width: 16),
                Expanded(flex: 6, child: right),
              ])
            : Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [left, const SizedBox(height: 16), right]);
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
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    Text('Profile', style: TextStyle(fontSize: wide ? 30 : 24, fontWeight: FontWeight.w700, color: LL.text, letterSpacing: -0.6)),
                    SizedBox(height: wide ? 22 : 16),
                    body,
                  ]),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _accountCard() {
    final fullName = (_me?['full_name'] as String?)?.trim() ?? '';
    final username = _me?['username'] as String? ?? '';
    final role = _me?['role'] as String? ?? '';
    final active = _me?['is_active'] == true;
    final initial = (fullName.isNotEmpty ? fullName : username).isEmpty ? '?' : (fullName.isNotEmpty ? fullName : username)[0].toUpperCase();
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(color: LL.accent, borderRadius: BorderRadius.circular(LL.radius)),
      child: Row(children: [
        CircleAvatar(
          radius: 30,
          backgroundColor: Colors.white,
          child: Text(initial, style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: LL.text)),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(fullName.isEmpty ? username : fullName,
                style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w700, color: LL.onAccent, letterSpacing: -0.3)),
            const SizedBox(height: 4),
            Text(username, style: LL.mono(size: 12.5, color: Colors.white70)),
            const SizedBox(height: 10),
            Wrap(spacing: 8, runSpacing: 6, children: [
              _darkPill(role.isEmpty ? 'No role' : role[0].toUpperCase() + role.substring(1)),
              _darkPill(active ? 'Active account' : 'Account disabled'),
            ]),
          ]),
        ),
      ]),
    );
  }

  Widget _darkPill(String text) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.14), borderRadius: BorderRadius.circular(20)),
        child: Text(text, style: const TextStyle(fontSize: 12, color: LL.onAccent, fontWeight: FontWeight.w500)),
      );

  Widget _statsCard() {
    final total = (_summary?['total_inspections'] as num?)?.toInt() ?? 0;
    final compliant = (_summary?['compliant_count'] as num?)?.toInt() ?? 0;
    final notCompliant = (_summary?['non_compliant_count'] as num?)?.toInt() ?? 0;
    final week = (_summary?['week_inspections'] as num?)?.toInt() ?? 0;
    final role = _me?['role'] as String? ?? '';
    var n = 0;
    Widget tile(IconData icon, String value, String label, {Color color = LL.text}) => Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Container(
              width: 36,
              height: 36,
              decoration: BoxDecoration(color: LL.pastel(n++), shape: BoxShape.circle),
              child: Icon(icon, size: 18, color: LL.text),
            ),
            const SizedBox(height: 12),
            Text(value, style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700, color: color, letterSpacing: -0.5)),
            Text(label, style: const TextStyle(fontSize: 12, color: LL.muted)),
          ]),
        );
    return LLCard(
      title: role == 'officer' ? 'Your inspections' : 'All inspections',
      subtitle: role == 'officer' ? 'Only inspections you scanned.' : 'Department-wide, as your role allows.',
      child: Row(children: [
        tile(Icons.receipt_long_outlined, '$total', 'Total'),
        tile(Icons.verified_outlined, '$compliant', 'Compliant'),
        tile(Icons.report_gmailerrorred_outlined, '$notCompliant', 'Not compliant', color: notCompliant > 0 ? LL.danger : LL.text),
        tile(Icons.calendar_today_outlined, '$week', 'Last 7 days'),
      ]),
    );
  }

  Widget _sessionCard() {
    return LLCard(
      title: 'Session',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          const Text('Server', style: TextStyle(fontSize: 13, color: LL.muted)),
          const SizedBox(width: 12),
          Expanded(child: Text(AppConfig.apiBaseUrl, textAlign: TextAlign.right, style: LL.mono(size: 12.5, color: LL.text))),
        ]),
        const SizedBox(height: 16),
        OutlinedButton.icon(
          onPressed: _signOut,
          style: OutlinedButton.styleFrom(
            foregroundColor: LL.danger,
            side: const BorderSide(color: LL.line),
            padding: const EdgeInsets.symmetric(vertical: 14),
            shape: const StadiumBorder(),
          ),
          icon: const Icon(Icons.logout, size: 18),
          label: const Text('Sign out', style: TextStyle(fontWeight: FontWeight.w600)),
        ),
      ]),
    );
  }

  Widget _referenceCard() {
    return LLCard(
      title: 'LMPC Rules, 2011 quick reference',
      subtitle: 'What every package must declare, and the Rule 7(2) minimum letter height.',
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        for (var i = 0; i < _lmpcReference.length; i++) ...[
          if (i > 0) const Divider(height: 1, thickness: 1, color: LL.line),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 10),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              SizedBox(width: 108, child: Text(_lmpcReference[i].$1, style: LL.mono(size: 12.5, color: LL.text))),
              Expanded(child: Text(_lmpcReference[i].$2, style: const TextStyle(fontSize: 13.5, color: LL.text))),
            ]),
          ),
        ],
        const SizedBox(height: 18),
        const Text('Rule 7(2) Table-I · normal print', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: LL.text)),
        const SizedBox(height: 10),
        Container(
          decoration: BoxDecoration(color: LL.hover, borderRadius: BorderRadius.circular(LL.radiusSmall)),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          child: Column(children: [
            for (final (area, mm) in _fontTable)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Row(children: [
                  Expanded(child: Text('Display panel area $area', style: const TextStyle(fontSize: 13, color: LL.muted))),
                  Text(mm, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: LL.text)),
                ]),
              ),
          ]),
        ),
      ]),
    );
  }
}
