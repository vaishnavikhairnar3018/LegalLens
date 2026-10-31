/// GoRouter configuration with auth-guarded routes and bottom nav shell.
library;

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../core/auth/auth_provider.dart';
import '../screens/home_screen.dart';
import '../screens/login_screen.dart';
import '../screens/scanner_screen.dart';
import '../screens/results_screen.dart';
import '../screens/history_screen.dart';
import '../screens/profile_screen.dart';
import '../screens/ml_benchmarks_screen.dart';
import '../widgets/app_shell.dart';

/// Application routing configuration.
class AppRouter {
  AppRouter._();

  static GoRouter createRouter(AuthProvider authProvider) {
    return GoRouter(
      initialLocation: '/home',
      refreshListenable: authProvider,
      redirect: (context, state) {
        final isLoggedIn = authProvider.isLoggedIn;
        final isLoginRoute = state.matchedLocation == '/login';

        // If not logged in and not on login page → redirect to login
        if (!isLoggedIn && !isLoginRoute) {
          return '/login';
        }

        // If logged in and on login page → redirect to home
        if (isLoggedIn && isLoginRoute) {
          return '/home';
        }

        return null; // No redirect
      },
      routes: [
        GoRoute(
          path: '/login',
          name: 'login',
          builder: (context, state) => const LoginScreen(),
        ),

        // Shell route wrapping the 5 tabbed screens (responsive: sidebar on web, bottom nav on mobile)
        StatefulShellRoute.indexedStack(
          builder: (context, state, navigationShell) {
            return AppShell(
              navigationShell: navigationShell,
              child: navigationShell,
            );
          },
          branches: [
            // Tab 0: Home Dashboard
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/home',
                  name: 'home',
                  builder: (context, state) => const HomeScreen(),
                ),
              ],
            ),
            // Tab 1: Live Camera Scanner
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/scanner',
                  name: 'scanner',
                  builder: (context, state) => const ScannerScreen(),
                ),
                GoRoute(
                  path: '/scan',
                  redirect: (context, state) => '/scanner',
                ),
              ],
            ),
            // Tab 2: AI & ML Algorithms (NEW BUTTON)
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/ml-benchmarks',
                  name: 'ml-benchmarks',
                  builder: (context, state) => const MLBenchmarksScreen(),
                ),
                GoRoute(
                  path: '/ml',
                  redirect: (context, state) => '/ml-benchmarks',
                ),
                GoRoute(
                  path: '/algorithms',
                  redirect: (context, state) => '/ml-benchmarks',
                ),
              ],
            ),
            // Tab 3: History
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/history',
                  name: 'history',
                  builder: (context, state) => const HistoryScreen(),
                ),
              ],
            ),
            // Tab 4: Profile
            StatefulShellBranch(
              routes: [
                GoRoute(
                  path: '/profile',
                  name: 'profile',
                  builder: (context, state) => const ProfileScreen(),
                ),
              ],
            ),
          ],
        ),

        // Results — pushed as stack (no bottom nav)
        GoRoute(
          path: '/results',
          name: 'results',
          builder: (context, state) {
            final report = state.extra as Map<String, dynamic>?;
            return ResultsScreen(report: report ?? {});
          },
        ),
      ],
      errorBuilder: (context, state) => Scaffold(
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline, size: 64, color: Colors.red),
              const SizedBox(height: 16),
              Text(
                'Page not found',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: () => GoRouter.of(context).go('/scanner'),
                child: const Text('Go to Scanner'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
