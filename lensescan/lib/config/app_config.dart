/// Application configuration constants.
///
/// All environment-specific values are centralized here.
/// In production, these should be loaded from build-time environment variables.
library;

import 'package:flutter/foundation.dart';

class AppConfig {
  AppConfig._(); // Prevent instantiation

  /// Backend API base URL with automatic platform detection.
  /// - Web (Laptop browser): http://localhost:8000
  /// - Web (Mobile phone browser over Wi-Fi): http://<host>:8000
  /// - Android Device over Wi-Fi: http://10.244.134.104:8000
  /// Optional build-time override: flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8001
  static const String _apiBaseOverride = String.fromEnvironment('API_BASE_URL');

  static String get apiBaseUrl {
    if (_apiBaseOverride.isNotEmpty) return _apiBaseOverride;
    if (kIsWeb) {
      final origin = Uri.base.origin;
      final host = Uri.base.host;
      final port = Uri.base.port;

      // 1. Local Flutter dev server (random debug port on localhost/127.0.0.1)
      if ((host == 'localhost' || host == '127.0.0.1') &&
          port != 5000 &&
          port != 8443 &&
          port != 8000) {
        return 'http://127.0.0.1:8000';
      }

      // 2. Wi-Fi proxy (5000 / 8443), Cloudflare tunnel (*.trycloudflare.com), or remote host:
      // The host/proxy serves both frontend and /api/ backend from the exact same origin.
      if (origin.isNotEmpty && origin != 'null') {
        return origin;
      }

      return 'http://127.0.0.1:8000';
    }
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
      case TargetPlatform.iOS:
        return 'http://10.244.134.104:8000';
      case TargetPlatform.macOS:
        return 'http://localhost:8000';
      case TargetPlatform.windows:
      case TargetPlatform.linux:
      default:
        return 'http://127.0.0.1:8000';
    }
  }

  /// API version prefix
  static const String apiPrefix = '/api/v1';

  /// Full API URL
  static String get apiUrl => '$apiBaseUrl$apiPrefix';

  /// Connection timeout in milliseconds
  static const int connectTimeout = 15000;

  /// Receive timeout in milliseconds
  static const int receiveTimeout = 60000; // OCR can take time

  /// Maximum upload file size in bytes (10MB)
  static const int maxUploadSizeBytes = 10 * 1024 * 1024;

  /// Secure storage keys
  static const String accessTokenKey = 'lensescan_access_token';
  static const String usernameKey = 'lensescan_username';
  static const String roleKey = 'lensescan_role';
}
