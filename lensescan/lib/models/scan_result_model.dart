/// Scan result model — maps backend ComplianceReport JSON.
library;

class ScanResultModel {
  final String scanId;
  final String timestamp;
  final String imageFilename;
  final String? productName;
  final String? imageHashSha256;
  final int dpiUsed;
  final bool overallCompliant;
  final int totalFields;
  final int compliantFields;
  final int nonCompliantFields;
  final List<DeclarationFieldModel> declarations;
  final String summary;
  final bool placementReviewRequired;
  final bool coverageReviewRequired;
  final bool fontReviewRequired;
  final double technicalVerificationCoverage;
  final List<PhotoEvidenceModel> photos;

  ScanResultModel({
    required this.scanId,
    required this.timestamp,
    required this.imageFilename,
    this.productName,
    this.imageHashSha256,
    required this.dpiUsed,
    required this.overallCompliant,
    this.placementReviewRequired = false,
    this.coverageReviewRequired = false,
    this.fontReviewRequired = false,
    this.technicalVerificationCoverage = 0.0,
    required this.totalFields,
    required this.compliantFields,
    required this.nonCompliantFields,
    required this.declarations,
    required this.summary,
    this.photos = const [],
  });

  factory ScanResultModel.fromJson(Map<String, dynamic> json) {
    var rawDecls = json['declarations'];
    List<dynamic> declList = [];
    if (rawDecls is List) {
      declList = rawDecls;
    }

    return ScanResultModel(
      scanId: json['scan_id'] ?? json['id'] ?? '',
      timestamp: json['timestamp'] ?? json['created_at'] ?? '',
      imageFilename: json['image_filename'] ?? '',
      productName: json['product_name'],
      imageHashSha256: json['image_hash_sha256'],
      dpiUsed: json['dpi_used'] ?? 300,
      overallCompliant: json['overall_compliant'] ?? false,
      placementReviewRequired: json['placement_review_required'] ?? false,
      coverageReviewRequired: json['coverage_review_required'] ?? false,
      fontReviewRequired: json['font_review_required'] ?? false,
      technicalVerificationCoverage:
          (json['technical_verification_coverage'] as num?)?.toDouble() ?? 0.0,
      totalFields: json['total_fields'] ?? 0,
      compliantFields: json['compliant_fields'] ?? 0,
      nonCompliantFields: json['non_compliant_fields'] ?? 0,
      declarations: declList
          .map((d) => DeclarationFieldModel.fromJson(d is Map<String, dynamic> ? d : {}))
          .toList(),
      summary: json['summary'] ?? '',
      photos: (json['photos'] as List<dynamic>? ?? [])
          .whereType<Map<String, dynamic>>()
          .map(PhotoEvidenceModel.fromJson)
          .toList(),
    );
  }
}

/// One photo of a multi-photo product inspection.
class PhotoEvidenceModel {
  final String filename;
  final String sha256;
  final bool hasMarker;

  PhotoEvidenceModel({required this.filename, required this.sha256, required this.hasMarker});

  factory PhotoEvidenceModel.fromJson(Map<String, dynamic> json) => PhotoEvidenceModel(
        filename: json['filename'] ?? '',
        sha256: json['image_hash_sha256'] ?? '',
        hasMarker: json['pixels_per_mm'] != null,
      );
}

class DeclarationFieldModel {
  final String fieldName;
  final String displayName;
  final bool detected;
  final String? detectionStatus;
  final String? value;
  final bool compliant;
  final List<String> violations;
  final double? fontHeightMm;
  final double? requiredFontHeightMm;
  final double? confidence;
  final bool placementCompliant;
  final List<String> placementViolations;
  final bool placementReviewRequired;
  final String? placementReviewReason;
  final bool coverageReviewRequired;
  final String? coverageReviewReason;
  final bool fontReviewRequired;
  final String? fontReviewReason;
  final bool priceReviewRequired;
  final String? priceReviewReason;
  final String? note;

  DeclarationFieldModel({
    required this.fieldName,
    required this.displayName,
    required this.detected,
    this.detectionStatus,
    this.value,
    required this.compliant,
    required this.violations,
    this.fontHeightMm,
    this.requiredFontHeightMm,
    this.confidence,
    this.placementCompliant = true,
    this.placementViolations = const [],
    this.placementReviewRequired = false,
    this.placementReviewReason,
    this.coverageReviewRequired = false,
    this.coverageReviewReason,
    this.fontReviewRequired = false,
    this.fontReviewReason,
    this.priceReviewRequired = false,
    this.priceReviewReason,
    this.note,
  });

  /// Any flag that means an officer must confirm this declaration by hand.
  bool get needsReview =>
      coverageReviewRequired || placementReviewRequired || fontReviewRequired || priceReviewRequired;

  /// The first reason an officer should read: a hard violation, else the review reason.
  String? get primaryReason {
    if (violations.isNotEmpty) return violations.first;
    return fontReviewReason ?? placementReviewReason ?? coverageReviewReason ?? priceReviewReason ?? note;
  }

  factory DeclarationFieldModel.fromJson(Map<String, dynamic> json) {
    return DeclarationFieldModel(
      fieldName: json['field_name'] ?? '',
      displayName: json['display_name'] ?? '',
      detected: json['detected'] ?? false,
      detectionStatus: json['detection_status'],
      value: json['value'],
      compliant: json['compliant'] ?? false,
      violations: (json['violations'] as List<dynamic>?)
              ?.map((v) => v.toString())
              .toList() ??
          [],
      fontHeightMm: (json['font_height_mm'] as num?)?.toDouble(),
      requiredFontHeightMm:
          (json['required_font_height_mm'] as num?)?.toDouble(),
      confidence: (json['confidence'] as num?)?.toDouble(),
      placementCompliant: json['placement_compliant'] ?? true,
      placementViolations: (json['placement_violations'] as List<dynamic>?)
              ?.map((v) => v.toString())
              .toList() ??
          [],
      placementReviewRequired: json['placement_review_required'] ?? false,
      placementReviewReason: json['placement_review_reason'],
      coverageReviewRequired: json['coverage_review_required'] ?? false,
      coverageReviewReason: json['coverage_review_reason'],
      fontReviewRequired: json['font_review_required'] ?? false,
      fontReviewReason: json['font_review_reason'],
      priceReviewRequired: json['price_review_required'] ?? false,
      priceReviewReason: json['price_review_reason'],
      note: json['note'],
    );
  }
}
