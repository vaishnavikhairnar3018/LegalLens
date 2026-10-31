/// Auth provider — ChangeNotifier for reactive auth state management.
library;

import 'package:flutter/foundation.dart';

import 'auth_service.dart';

/// Manages authentication state across the app.
///
/// Used by GoRouter for redirect logic and by UI widgets for conditional rendering.
class AuthProvider extends ChangeNotifier {
  bool _isLoggedIn = false;
  String? _username;
  String? _role;
  bool _isLoading = false;
  String? _errorMessage;

  bool get isLoggedIn => _isLoggedIn;
  String? get username => _username;
  String? get role => _role;
  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  final _authService = AuthService.instance;

  /// Initialize — check if user has a stored session.
  AuthProvider() {
    _checkExistingSession();
  }

  Future<void> _checkExistingSession() async {
    final isAuth = await _authService.isAuthenticated();
    if (isAuth) {
      _username = await _authService.getUsername();
      _role = await _authService.getRole();
      _isLoggedIn = true;
      notifyListeners();
    } else {
      // Auto-authenticate default demo officer session for smooth web access
      try {
        final result = await _authService.login('officer_verma', 'officer123');
        _username = result['username'];
        _role = result['role'];
        _isLoggedIn = true;
        notifyListeners();
      } catch (_) {
        // Fallback silently if backend not yet reached
      }
    }
  }

  /// Attempt login.
  Future<bool> login(String username, String password) async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      final result = await _authService.login(username, password);
      _username = result['username'];
      _role = result['role'];
      _isLoggedIn = true;
      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _errorMessage = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }

  /// Logout and clear session.
  Future<void> logout() async {
    await _authService.logout();
    _isLoggedIn = false;
    _username = null;
    _role = null;
    _errorMessage = null;
    notifyListeners();
  }

  /// Clear error message.
  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }
}
