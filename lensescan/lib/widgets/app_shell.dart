/// App shell — dark floating sidebar on wide screens, bottom tab bar on phones.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';

import '../config/theme.dart';
import '../core/auth/auth_provider.dart';
import 'legal_lens_logo.dart';

class _NavItem {
  final String label;
  final String shortLabel;
  final IconData icon;
  const _NavItem(this.label, this.shortLabel, this.icon);
}

// Order matches the StatefulShellRoute branches in routes.dart.
const _items = [
  _NavItem('Overview', 'Overview', Icons.space_dashboard_outlined),
  _NavItem('Scan a label', 'Scan', Icons.document_scanner_outlined),
  _NavItem('Model', 'Model', Icons.insights_outlined),
  _NavItem('Inspections', 'History', Icons.receipt_long_outlined),
  _NavItem('Profile', 'Profile', Icons.person_outline),
];

class AppShell extends StatelessWidget {
  final Widget child;
  final StatefulNavigationShell navigationShell;

  const AppShell({
    super.key,
    required this.child,
    required this.navigationShell,
  });

  @override
  Widget build(BuildContext context) {
    final isDesktop = MediaQuery.of(context).size.width >= 840;

    if (isDesktop) {
      return Scaffold(
        backgroundColor: LL.paper,
        body: Row(
          children: [
            _Sidebar(navigationShell: navigationShell),
            Expanded(child: child),
          ],
        ),
      );
    }

    return Scaffold(
      backgroundColor: LL.paper,
      body: child,
      bottomNavigationBar: _BottomNav(navigationShell: navigationShell),
    );
  }
}

class _Sidebar extends StatelessWidget {
  final StatefulNavigationShell navigationShell;
  const _Sidebar({required this.navigationShell});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final current = navigationShell.currentIndex;
    final username = auth.username ?? '';

    return Container(
      width: 244,
      margin: const EdgeInsets.fromLTRB(16, 16, 0, 16),
      decoration: BoxDecoration(color: LL.sidebar, borderRadius: BorderRadius.circular(28)),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 28, 16, 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 8),
              child: Row(
                children: [
                  LegalLensLogo(size: 32, tile: false),
                  SizedBox(width: 8),
                  Text(
                    'LegalLens',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.w500, color: Colors.white, letterSpacing: -0.4),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 36),
            for (var i = 0; i < _items.length; i++)
              _SidebarLink(
                item: _items[i],
                selected: current == i,
                onTap: () => navigationShell.goBranch(i, initialLocation: i == current),
              ),
            const Spacer(),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.07), borderRadius: BorderRadius.circular(18)),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 18,
                    backgroundColor: LL.highlight,
                    child: Text(
                      username.isEmpty ? '?' : username[0].toUpperCase(),
                      style: const TextStyle(color: LL.accent, fontWeight: FontWeight.w700),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          username.isEmpty ? 'Not signed in' : username,
                          style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Colors.white),
                        ),
                        if (auth.role != null)
                          Text(_roleLabel(auth.role!), style: const TextStyle(fontSize: 12, color: LL.sidebarText)),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Sign out',
                    onPressed: () {
                      context.read<AuthProvider>().logout();
                      context.go('/login');
                    },
                    icon: const Icon(Icons.logout, size: 18, color: LL.sidebarText),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _roleLabel(String role) =>
      role.isEmpty ? role : role[0].toUpperCase() + role.substring(1).toLowerCase();
}

class _SidebarLink extends StatelessWidget {
  final _NavItem item;
  final bool selected;
  final VoidCallback onTap;
  const _SidebarLink({required this.item, required this.selected, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Material(
        color: selected ? LL.highlight.withValues(alpha: 0.14) : Colors.transparent,
        borderRadius: BorderRadius.circular(14),
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          hoverColor: Colors.white.withValues(alpha: 0.06),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
            child: Row(
              children: [
                Icon(item.icon, size: 19, color: selected ? LL.highlight : LL.sidebarText),
                const SizedBox(width: 12),
                Text(
                  item.label,
                  style: TextStyle(
                    fontSize: 14,
                    color: selected ? LL.highlight : LL.sidebarText,
                    fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _BottomNav extends StatelessWidget {
  final StatefulNavigationShell navigationShell;
  const _BottomNav({required this.navigationShell});

  @override
  Widget build(BuildContext context) {
    final current = navigationShell.currentIndex;
    return Container(
      color: LL.sidebar,
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 66,
          child: Row(
            children: [
              for (var i = 0; i < _items.length; i++)
                Expanded(
                  child: InkWell(
                    onTap: () => navigationShell.goBranch(i, initialLocation: i == current),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        AnimatedContainer(
                          duration: const Duration(milliseconds: 180),
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
                          decoration: BoxDecoration(
                            color: current == i ? LL.highlight : Colors.transparent,
                            borderRadius: BorderRadius.circular(20),
                          ),
                          child: Icon(_items[i].icon, size: 20, color: current == i ? LL.accent : LL.sidebarText),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          _items[i].shortLabel,
                          style: TextStyle(
                            fontSize: 11,
                            color: current == i ? Colors.white : LL.sidebarText,
                            fontWeight: current == i ? FontWeight.w600 : FontWeight.w400,
                          ),
                        ),
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
}
