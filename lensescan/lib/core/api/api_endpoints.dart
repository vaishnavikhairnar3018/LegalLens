/// API endpoint constants.
library;

class ApiEndpoints {
  ApiEndpoints._();

  // Auth
  static const String login = '/auth/login';
  static const String register = '/auth/register';
  static const String me = '/auth/me';

  // Scan
  static const String scan = '/scan/';
  static const String scanProduct = '/scan/product';

  // Inspections
  static const String inspections = '/inspections/';
  static String inspectionDetail(String id) => '/inspections/$id';
  static String inspectionPdf(String id) => '/inspections/$id/notice.pdf';
  static String inspectionDocx(String id) => '/inspections/$id/notice.docx';

  // Dashboard
  static const String dashboardSummary = '/dashboard/summary';
}
