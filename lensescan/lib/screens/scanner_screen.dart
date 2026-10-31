/// Scanner screen — live camera viewfinder, then a confirm step before upload.
///
/// Camera preview with frame corners, shutter and photo upload; after capture,
/// the photo, an optional display panel area, and Retake / Check label.
library;

import 'package:camera/camera.dart';
import 'dart:ui' as ui;
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';
import 'package:flutter/foundation.dart';

import '../config/app_config.dart';
import '../config/theme.dart';
import '../core/api/api_endpoints.dart';
import '../core/api/dio_client.dart';
import '../core/utils/camera_permission.dart';
import '../widgets/loading_overlay.dart';

/// Core scanner screen — capture product labels and submit for compliance analysis.
class ScannerScreen extends StatefulWidget {
  const ScannerScreen({super.key});

  @override
  State<ScannerScreen> createState() => _ScannerScreenState();
}

/// One photo of the product being inspected.
class _Photo {
  final Uint8List bytes;
  final String name;
  const _Photo(this.bytes, this.name);
}

class _ScannerScreenState extends State<ScannerScreen> {
  final ImagePicker _picker = ImagePicker();
  // All photos of the current product (e.g. a clean shot and one with the 40 mm marker).
  final List<_Photo> _photos = [];
  int _selectedPhoto = 0;
  // True while the officer is back in the camera to add another photo of the same product.
  bool _addingMore = false;
  bool _isUploading = false;
  double _uploadProgress = 0.0;
  String? _errorMessage;
  bool _torchOn = false;
  // Optional Principal Display Panel area (cm²) for the Rule 7(2) font-height minimum
  final _pdpAreaController = TextEditingController();
  // Product name as written on the pack; required so records are identifiable
  final _productNameController = TextEditingController();

  // Live camera stream state
  CameraController? _cameraController;
  List<CameraDescription> _availableCameras = [];
  bool _isCameraInitialized = false;
  bool _isCameraInitializing = true;
  String? _cameraErrorMessage;

  @override
  void initState() {
    super.initState();
    _initCamera();
  }

  @override
  void dispose() {
    _pdpAreaController.dispose();
    _productNameController.dispose();
    _cameraController?.dispose();
    super.dispose();
  }

  Future<void> _initCamera() async {
    if (!mounted) return;
    setState(() {
      _isCameraInitializing = true;
      _cameraErrorMessage = null;
    });

    try {
      if (kIsWeb) {
        // Trigger browser permission prompt first via HTML5 getUserMedia
        await requestWebCameraPermission();
      }

      final cameras = await availableCameras().timeout(
        const Duration(seconds: 15),
        onTimeout: () => <CameraDescription>[],
      );
      _availableCameras = cameras;
      if (cameras.isEmpty) {
        if (!mounted) return;
        setState(() {
          _isCameraInitializing = false;
          _cameraErrorMessage = 'No camera found or permission not granted in browser.\nPlease allow camera access and tap Retry.';
        });
        return;
      }

      // Prefer rear/back camera for label scanning
      final backCamera = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );

      final controller = CameraController(
        backCamera,
        ResolutionPreset.medium,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.jpeg,
      );

      await controller.initialize().timeout(
        const Duration(seconds: 15),
        onTimeout: () {
          throw Exception('Camera initialization timed out');
        },
      );
      if (!mounted) {
        await controller.dispose();
        return;
      }

      setState(() {
        _cameraController = controller;
        _isCameraInitialized = true;
        _isCameraInitializing = false;
        _cameraErrorMessage = null;
      });
    } catch (e) {
      if (!mounted) return;
      String err = 'Camera access denied or unavailable.';
      final eStr = e.toString().toLowerCase();
      if (eStr.contains('notallowederror') || eStr.contains('permission')) {
        err = 'Camera permission blocked. Tap the tune/lock icon in browser URL bar to allow camera.';
      } else if (eStr.contains('securityerror') || eStr.contains('insecure') || eStr.contains('secure context')) {
        err = 'Live camera requires a secure origin. Please tap lock icon near URL to Allow Camera.';
      } else if (eStr.contains('timed out')) {
        err = 'Camera initialization timed out. Tap Allow / Retry Camera below.';
      }
      setState(() {
        _isCameraInitialized = false;
        _isCameraInitializing = false;
        _cameraErrorMessage = err;
      });
    }
  }

  Future<void> _switchCamera() async {
    if (_availableCameras.length < 2 || _cameraController == null) return;
    final currentLens = _cameraController!.description.lensDirection;
    final newCamera = _availableCameras.firstWhere(
      (c) => c.lensDirection != currentLens,
      orElse: () => _availableCameras.first,
    );
    await _cameraController?.dispose();
    if (!mounted) return;
    setState(() {
      _isCameraInitialized = false;
      _isCameraInitializing = true;
    });
    try {
      final controller = CameraController(
        newCamera,
        ResolutionPreset.veryHigh,
        enableAudio: false,
        imageFormatGroup: ImageFormatGroup.jpeg,
      );
      await controller.initialize();
      if (!mounted) {
        await controller.dispose();
        return;
      }
      setState(() {
        _cameraController = controller;
        _isCameraInitialized = true;
        _isCameraInitializing = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isCameraInitialized = false;
        _isCameraInitializing = false;
      });
    }
  }

  Future<void> _toggleTorch() async {
    if (_cameraController != null && _cameraController!.value.isInitialized) {
      try {
        if (_torchOn) {
          await _cameraController!.setFlashMode(FlashMode.off);
          setState(() => _torchOn = false);
        } else {
          await _cameraController!.setFlashMode(FlashMode.torch);
          setState(() => _torchOn = true);
        }
        return;
      } catch (_) {
        // Fallback for browsers / devices without torch support
      }
    }
    setState(() => _torchOn = !_torchOn);
  }

  Future<void> _handleShutterCapture() async {
    // 1. If live camera stream is active, capture photo instantly from feed
    if (_isCameraInitialized &&
        _cameraController != null &&
        _cameraController!.value.isInitialized &&
        !_cameraController!.value.isTakingPicture) {
      try {
        final XFile photo = await _cameraController!.takePicture();
        final bytes = await photo.readAsBytes();
        if (!mounted) return;
        _addPhoto(bytes, photo.name.isNotEmpty ? photo.name : 'label_scan.jpg');
        return;
      } catch (e) {
        setState(() {
          _errorMessage = 'Failed to capture from live stream: $e';
        });
        return;
      }
    }

    // 2. If camera not ready, open gallery/file picker so shutter button is never dead
    await _pickFromGallery();
  }

  Future<void> _loadSampleLabel() async {
    try {
      final recorder = ui.PictureRecorder();
      final canvas = Canvas(recorder, const Rect.fromLTWH(0, 0, 800, 950));
      final bgPaint = Paint()..color = const Color(0xFFF8FAFC);
      canvas.drawRect(const Rect.fromLTWH(0, 0, 800, 950), bgPaint);

      final borderPaint = Paint()
        ..color = const Color(0xFF1E293B)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3;
      canvas.drawRect(const Rect.fromLTWH(24, 24, 752, 902), borderPaint);

      void drawText(String text, double x, double y, double fontSize, {bool isBold = false, Color color = const Color(0xFF0F172A)}) {
        final textPainter = TextPainter(
          text: TextSpan(
            text: text,
            style: TextStyle(
              fontSize: fontSize,
              fontWeight: isBold ? FontWeight.bold : FontWeight.normal,
              color: color,
            ),
          ),
          textDirection: TextDirection.ltr,
        );
        textPainter.layout();
        textPainter.paint(canvas, Offset(x, y));
      }

      drawText('TATA SALT', 50, 60, 36, isBold: true, color: const Color(0xFF1E3A8A));
      drawText('VACUUM EVAPORATED IODISED SALT', 50, 110, 18, isBold: true);
      drawText('Net Quantity: 1 kg (1000 g)', 50, 190, 24, isBold: true);
      drawText('MRP: Rs. 28.00 (Incl. of all taxes)', 50, 240, 24, isBold: true);
      drawText('Month & Year of Packing: 08/2026', 50, 290, 20);
      drawText('Batch No.: B-2026/8940-TS', 50, 340, 18);
      drawText('Manufactured by: Tata Consumer Products Ltd.', 50, 400, 18, isBold: true);
      drawText('1, Bishop Lefroy Road, Kolkata - 700020', 50, 435, 16);
      drawText('Country of Origin: India', 50, 485, 18, isBold: true);
      drawText('Consumer Care: care@tataconsumer.com | 1800-108-4488', 50, 530, 16);

      final picture = recorder.endRecording();
      final img = await picture.toImage(800, 950);
      final byteData = await img.toByteData(format: ui.ImageByteFormat.png);

      if (byteData != null) {
        _addPhoto(byteData.buffer.asUint8List(), 'Tata_Salt_1kg_Sample.png');
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Could not generate sample label: $e';
      });
    }
  }

  Future<void> _captureFromCamera() async {
    try {
      // Send the original photo: the server resizes it once for both the marker scale and OCR,
      // and hashes the untouched original as evidence. Browser-side resizing blurred small print.
      final XFile? photo = await _picker.pickImage(source: ImageSource.camera);
      if (photo != null) {
        final bytes = await photo.readAsBytes();
        _addPhoto(bytes, photo.name.isNotEmpty ? photo.name : 'label_scan.jpg');
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Camera access denied or unavailable.';
      });
    }
  }

  Future<void> _pickFromGallery() async {
    try {
      final XFile? photo = await _picker.pickImage(source: ImageSource.gallery);
      if (photo != null) {
        final bytes = await photo.readAsBytes();
        _addPhoto(bytes, photo.name.isNotEmpty ? photo.name : 'label_scan.jpg');
      }
    } catch (e) {
      setState(() {
        _errorMessage = 'Gallery access denied or unavailable.';
      });
    }
  }

  void _addPhoto(Uint8List bytes, String name) {
    if (!mounted) return;
    if (bytes.length > AppConfig.maxUploadSizeBytes) {
      final mb = (bytes.length / (1024 * 1024)).toStringAsFixed(1);
      setState(() => _errorMessage = '$name is $mb MB; the limit is ${AppConfig.maxUploadSizeBytes ~/ (1024 * 1024)} MB per photo.');
      return;
    }
    setState(() {
      _photos.add(_Photo(bytes, name));
      _selectedPhoto = _photos.length - 1;
      _addingMore = false;
      _errorMessage = null;
    });
  }

  void _removePhoto(int index) {
    setState(() {
      _photos.removeAt(index);
      _selectedPhoto = _photos.isEmpty ? 0 : _selectedPhoto.clamp(0, _photos.length - 1);
      _errorMessage = null;
    });
  }

  Future<void> _uploadAndScan() async {
    if (_photos.isEmpty) return;

    final productName = _productNameController.text.trim();
    if (productName.isEmpty) {
      setState(() => _errorMessage = 'Enter the product name as printed on the pack.');
      return;
    }

    final pdpAreaText = _pdpAreaController.text.trim();
    final pdpArea = pdpAreaText.isEmpty ? null : double.tryParse(pdpAreaText);
    if (pdpAreaText.isNotEmpty && (pdpArea == null || pdpArea <= 0)) {
      setState(() => _errorMessage = 'PDP area must be a positive number in cm².');
      return;
    }

    setState(() {
      _isUploading = true;
      _uploadProgress = 0.0;
      _errorMessage = null;
    });

    try {
      // All photos of this product in one request: the server combines them into one inspection.
      final formData = FormData();
      for (final photo in _photos) {
        formData.files.add(MapEntry('images', MultipartFile.fromBytes(photo.bytes, filename: photo.name)));
      }
      formData.fields.add(MapEntry('product_name', productName));
      if (pdpArea != null) formData.fields.add(MapEntry('pdp_area_cm2', pdpArea.toString()));

      final response = await DioClient.instance.dio.post(
        ApiEndpoints.scanProduct,
        data: formData,
        options: Options(
          contentType: 'multipart/form-data',
          // OCR on a CPU takes about a minute per photo; the default 60 s receive timeout would abort the scan.
          sendTimeout: const Duration(minutes: 2),
          receiveTimeout: const Duration(minutes: 15),
        ),
        onSendProgress: (sent, total) {
          if (total > 0) {
            setState(() {
              _uploadProgress = sent / total;
            });
          }
        },
      );

      if (mounted) {
        setState(() {
          _isUploading = false;
          _photos.clear();
          _selectedPhoto = 0;
          _pdpAreaController.clear();
          _productNameController.clear();
        });

        // Navigate to results screen with the compliance report
        context.push('/results', extra: response.data);
      }
    } on DioException catch (e) {
      // Never substitute a result: the captured image is kept so the officer can retry.
      debugPrint('Scan upload failed: ${e.type} ${e.response?.statusCode} ${e.message}');
      if (mounted) {
        setState(() {
          _isUploading = false;
          _errorMessage = _scanErrorMessage(e);
        });
      }
    } catch (e) {
      debugPrint('Scan failed: $e');
      if (mounted) {
        setState(() {
          _isUploading = false;
          _errorMessage = 'Scan failed. Please try again.';
        });
      }
    }
  }

  String _scanErrorMessage(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionError:
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return 'Cannot reach the server. Check the connection and try again.';
      default:
        break;
    }
    final status = e.response?.statusCode;
    if (status == 401) return 'Session expired. Please sign in again.';
    if (status == 403) return 'Your account is not allowed to scan.';
    final detail = e.response?.data is Map ? (e.response!.data as Map)['detail'] : null;
    if (detail is String && detail.isNotEmpty) return detail;
    return 'Scan failed${status != null ? ' ($status)' : ''}. Please try again.';
  }

  void _clearAll() {
    setState(() {
      _photos.clear();
      _selectedPhoto = 0;
      _addingMore = false;
      _errorMessage = null;
    });
  }

  bool get _reviewing => _photos.isNotEmpty && !_addingMore;

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        Scaffold(
          backgroundColor: _reviewing ? LL.paper : _cameraBg,
          body: _reviewing ? _buildImagePreview() : _buildViewfinder(),
        ),
        if (_isUploading) LoadingOverlay(progress: _uploadProgress),
      ],
    );
  }

  static const _cameraBg = Color(0xFF15171C);

  // ── Live camera ──
  Widget _buildViewfinder() {
    return SafeArea(
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(20, 12, 12, 4),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    _addingMore ? 'Photo ${_photos.length + 1} of this product' : 'Scan a label',
                    style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w500),
                  ),
                ),
                if (_addingMore)
                  TextButton(
                    onPressed: () => setState(() => _addingMore = false),
                    style: TextButton.styleFrom(foregroundColor: Colors.white),
                    child: Text('Back to ${_photos.length} photo${_photos.length == 1 ? '' : 's'}'),
                  ),
                if (_isCameraInitialized && _availableCameras.length > 1)
                  _buildIconButton(icon: Icons.flip_camera_android_outlined, tooltip: 'Switch camera', onTap: _switchCamera),
                if (_isCameraInitialized)
                  _buildIconButton(
                    icon: _torchOn ? Icons.flash_on : Icons.flash_off,
                    tooltip: _torchOn ? 'Torch off' : 'Torch on',
                    onTap: _toggleTorch,
                  ),
              ],
            ),
          ),
          Expanded(
            child: Stack(
              children: [
                _buildLiveCameraView(),
                if (_isCameraInitialized) Center(child: IgnorePointer(child: _buildReticle())),
                if (_isCameraInitialized)
                  const Positioned(
                    left: 24,
                    right: 24,
                    bottom: 16,
                    child: Text(
                      'Fit the label and the 40 mm marker inside the frame',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.white70, fontSize: 13),
                    ),
                  ),
                if (_errorMessage != null)
                  Positioned(left: 16, right: 16, bottom: 16, child: _buildErrorNote(dark: true)),
              ],
            ),
          ),
          _buildShutterRow(),
        ],
      ),
    );
  }

  Widget _buildLiveCameraView() {
    if (_isCameraInitialized && _cameraController != null && _cameraController!.value.isInitialized) {
      return GestureDetector(
        onTap: _handleShutterCapture,
        behavior: HitTestBehavior.opaque,
        child: SizedBox.expand(
          child: LayoutBuilder(
            builder: (context, constraints) {
              final size = constraints.biggest;
              var scale = size.aspectRatio * _cameraController!.value.aspectRatio;
              if (scale < 1) scale = 1 / scale;
              return ClipRect(
                child: Center(
                  child: Transform.scale(scale: scale, child: Center(child: CameraPreview(_cameraController!))),
                ),
              );
            },
          ),
        ),
      );
    }

    if (_isCameraInitializing) {
      return const Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white70)),
            SizedBox(height: 14),
            Text('Starting camera…', style: TextStyle(color: Colors.white70, fontSize: 13)),
          ],
        ),
      );
    }

    // Camera unavailable: offer the other ways in.
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 32),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 360),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.no_photography_outlined, size: 32, color: Colors.white38),
              const SizedBox(height: 14),
              const Text('Camera isn\'t available', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w500)),
              const SizedBox(height: 6),
              Text(
                _cameraErrorMessage ?? 'Allow camera access, or upload a photo of the label.',
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.white60, fontSize: 13, height: 1.4),
              ),
              const SizedBox(height: 22),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: _pickFromGallery,
                  style: FilledButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: LL.text,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  icon: const Icon(Icons.upload_outlined, size: 18),
                  label: const Text('Upload a photo', style: TextStyle(fontSize: 14)),
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                alignment: WrapAlignment.center,
                children: [
                  _buildQuietLink('Try camera again', _initCamera),
                  _buildQuietLink('Phone camera app', _captureFromCamera),
                  _buildQuietLink('Use a sample label', _loadSampleLabel),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildQuietLink(String label, VoidCallback onTap) {
    return TextButton(
      onPressed: onTap,
      style: TextButton.styleFrom(foregroundColor: Colors.white70),
      child: Text(label, style: const TextStyle(fontSize: 13)),
    );
  }

  Widget _buildIconButton({required IconData icon, required String tooltip, required VoidCallback onTap}) {
    return IconButton(tooltip: tooltip, onPressed: onTap, icon: Icon(icon, color: Colors.white, size: 22));
  }

  Widget _buildReticle() {
    const side = BorderSide(color: Colors.white, width: 2);
    Widget corner({required bool top, required bool left}) => Positioned(
          top: top ? 0 : null,
          bottom: top ? null : 0,
          left: left ? 0 : null,
          right: left ? null : 0,
          child: Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              border: Border(
                top: top ? side : BorderSide.none,
                bottom: top ? BorderSide.none : side,
                left: left ? side : BorderSide.none,
                right: left ? BorderSide.none : side,
              ),
            ),
          ),
        );
    return SizedBox(
      width: 260,
      height: 340,
      child: Stack(
        children: [
          corner(top: true, left: true),
          corner(top: true, left: false),
          corner(top: false, left: true),
          corner(top: false, left: false),
        ],
      ),
    );
  }

  Widget _buildShutterRow() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(28, 16, 28, 20),
      child: Row(
        children: [
          Expanded(
            child: Align(
              alignment: Alignment.centerLeft,
              child: _buildIconButton(icon: Icons.photo_library_outlined, tooltip: 'Upload a photo', onTap: _pickFromGallery),
            ),
          ),
          Semantics(
            button: true,
            label: 'Take photo',
            child: GestureDetector(
              onTap: _handleShutterCapture,
              child: Container(
                width: 68,
                height: 68,
                padding: const EdgeInsets.all(4),
                decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: Colors.white, width: 3)),
                child: const DecoratedBox(decoration: BoxDecoration(shape: BoxShape.circle, color: Colors.white)),
              ),
            ),
          ),
          const Expanded(child: SizedBox()),
        ],
      ),
    );
  }

  Widget _buildErrorNote({required bool dark}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: dark ? const Color(0xFF2A1715) : LL.surface,
        border: Border.all(color: LL.danger.withValues(alpha: dark ? 0.7 : 0.4)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        _errorMessage!,
        style: TextStyle(fontSize: 13, height: 1.4, color: dark ? const Color(0xFFF4B4AE) : LL.danger),
      ),
    );
  }

  // ── Captured photo: confirm and send ──
  Widget _buildImagePreview() {
    final wide = MediaQuery.of(context).size.width >= 840;
    return SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 640),
          child: Padding(
            padding: EdgeInsets.fromLTRB(wide ? 32 : 16, 16, wide ? 32 : 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        _photos.length == 1 ? 'Check the photo' : '${_photos.length} photos of this product',
                        style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600, color: LL.text),
                      ),
                    ),
                    IconButton(
                      tooltip: 'Discard all photos',
                      onPressed: _isUploading ? null : _clearAll,
                      icon: const Icon(Icons.close, color: LL.muted),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Expanded(
                  child: Container(
                    decoration: BoxDecoration(
                      color: LL.surface,
                      border: Border.all(color: LL.line),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    clipBehavior: Clip.antiAlias,
                    child: Image.memory(_photos[_selectedPhoto].bytes, fit: BoxFit.contain),
                  ),
                ),
                const SizedBox(height: 10),
                _buildPhotoStrip(),
                const SizedBox(height: 16),
                TextField(
                  controller: _productNameController,
                  enabled: !_isUploading,
                  maxLength: 200,
                  textCapitalization: TextCapitalization.words,
                  style: const TextStyle(fontSize: 15, color: LL.text),
                  onChanged: (_) {
                    if (_errorMessage != null) setState(() => _errorMessage = null);
                  },
                  decoration: InputDecoration(
                    labelText: 'Product name',
                    hintText: 'Everest Shahi Paneer Masala 12 g',
                    counterText: '',
                    isDense: true,
                    filled: true,
                    fillColor: LL.surface,
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: const BorderSide(color: LL.line),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: const BorderSide(color: LL.accent),
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _pdpAreaController,
                  enabled: !_isUploading,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  style: const TextStyle(fontSize: 15, color: LL.text),
                  decoration: InputDecoration(
                    labelText: 'Display panel area (optional)',
                    helperText: 'Front face height × width. Sets the Rule 7(2) minimum font size.',
                    helperMaxLines: 2,
                    suffixText: 'cm²',
                    isDense: true,
                    filled: true,
                    fillColor: LL.surface,
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: const BorderSide(color: LL.line),
                    ),
                    focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(8),
                      borderSide: const BorderSide(color: LL.accent),
                    ),
                  ),
                ),
                if (_errorMessage != null) ...[
                  const SizedBox(height: 12),
                  _buildErrorNote(dark: false),
                ],
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _isUploading || _photos.length >= _maxPhotos
                            ? null
                            : () => setState(() {
                                  _addingMore = true;
                                  _errorMessage = null;
                                }),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: LL.text,
                          backgroundColor: LL.surface,
                          side: const BorderSide(color: LL.line),
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        ),
                        icon: const Icon(Icons.add_a_photo_outlined, size: 18),
                        label: const Text('Add photo', style: TextStyle(fontSize: 14)),
                      ),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      flex: 2,
                      child: FilledButton(
                        onPressed: _isUploading ? null : _uploadAndScan,
                        style: FilledButton.styleFrom(
                          backgroundColor: LL.accent,
                          foregroundColor: LL.onAccent,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                        ),
                        child: Text(
                          _photos.length == 1 ? 'Check label' : 'Check product',
                          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  // Matches MAX_PRODUCT_PHOTOS on the server.
  static const _maxPhotos = 8;

  /// Thumbnails of every photo of this product; tap to view, × to remove.
  Widget _buildPhotoStrip() {
    return SizedBox(
      height: 64,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        itemCount: _photos.length,
        separatorBuilder: (_, __) => const SizedBox(width: 8),
        itemBuilder: (context, i) {
          final selected = i == _selectedPhoto;
          return Stack(
            clipBehavior: Clip.none,
            children: [
              GestureDetector(
                onTap: () => setState(() => _selectedPhoto = i),
                child: Container(
                  width: 64,
                  height: 64,
                  decoration: BoxDecoration(
                    border: Border.all(color: selected ? LL.accent : LL.line, width: selected ? 2 : 1),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: Image.memory(_photos[i].bytes, fit: BoxFit.cover),
                ),
              ),
              if (!_isUploading)
                Positioned(
                  top: -6,
                  right: -6,
                  child: Semantics(
                    button: true,
                    label: 'Remove photo ${i + 1}',
                    child: GestureDetector(
                      onTap: () => _removePhoto(i),
                      child: Container(
                        width: 20,
                        height: 20,
                        decoration: BoxDecoration(
                          color: LL.surface,
                          shape: BoxShape.circle,
                          border: Border.all(color: LL.line),
                        ),
                        child: const Icon(Icons.close, size: 12, color: LL.muted),
                      ),
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}
