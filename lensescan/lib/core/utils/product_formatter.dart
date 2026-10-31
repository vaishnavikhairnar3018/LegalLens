/// Standard product display name formatter for LenseScan presentation & UI.
/// Formats raw dataset filenames into clean, professional product names.
library;

/// Display name for an inspection record: the officer-entered product name when present,
/// otherwise a name derived from the photo file name (older records).
String inspectionDisplayName(Map<String, dynamic> insp, {int maxLength = 28}) {
  final entered = (insp['product_name'] as String?)?.trim();
  if (entered != null && entered.isNotEmpty) return entered;
  return formatProductName(insp['image_filename'] as String?, maxLength: maxLength);
}

String formatProductName(String? filename, {int maxLength = 28}) {
  if (filename == null || filename.isEmpty) return 'Packaged Commodity';

  // Multi-photo product inspections store the photo names comma-separated.
  if (filename.contains(', ')) {
    final count = filename.split(', ').length;
    return 'Product inspection · $count photos';
  }

  final lower = filename.toLowerCase();

  // 1. Direct dataset brand & product mapping for presentation perfection
  if (lower.contains('balaji_gathiya')) return 'Balaji Papdi Gathiya';
  if (lower.contains('balaji_mungdal')) return 'Balaji Mung Dal Namkeen';
  if (lower.contains('balaji_sev_murmura')) return 'Balaji Sev Murmura';
  if (lower.contains('balaji_khatta_mitha')) return 'Balaji Khatta Mitha Mix';
  if (lower.contains('maggi_pichkoo')) return 'Maggi Pichkoo Ketchup';
  if (lower.contains('britannia_nutrichoice')) return 'Britannia NutriChoice Oats';
  if (lower.contains('dark_fantasy')) return 'Dark Fantasy Bourbon';
  if (lower.contains('surf_excel')) return 'Surf Excel Stain Eraser';
  if (lower.contains('vim_dishwash_gel')) return 'Vim Lemon Dishwash Gel';
  if (lower.contains('vim_lemon') || lower.contains('vim_dishwash')) return 'Vim Lemon Dishwash Bar';
  if (lower.contains('samrat_khaman')) return 'Samrat Khaman Dhokla Mix';
  if (lower.contains('samrat_maida')) return 'Samrat MP Maida Flour';
  if (lower.contains('goodknight_flash')) return 'GoodKnight Flash Repellent';
  if (lower.contains('haldiram_rusky')) return 'Haldiram Rusky Atta Toast';
  if (lower.contains('bishnoi_toast')) return 'Bishnoi Premium Toast';
  if (lower.contains('ram_bandhu')) return 'Ram Bandhu Chakali Mix';
  if (lower.contains('ponds_talc')) return "Pond's Dreamflower Talc";
  if (lower.contains('chings_manchow')) return "Ching's Manchow Soup";
  if (lower.contains('amin_persian')) return 'Amin Persian Dates Pack';
  if (lower.contains('suruchi_soy')) return 'Suruchi Dark Soy Sauce';
  if (lower.contains('mysore_sandal')) return 'Mysore Sandal Kleenol Soap';
  if (lower.contains('royal_toast')) return 'Royal Elaichi Toast';
  if (lower.contains('packaged_staple')) return 'Packaged Food Grain';
  if (lower.contains('beverage_pouch')) return 'Fruit Drink Pouch';
  if (lower.contains('snack_pouch')) return 'Namkeen Mixture Pouch';

  // 2. Intelligent regex fallback for newly scanned commodities
  String clean = filename
      .replaceAll(RegExp(r'\.[^.]+$'), '') // strip extension
      .replaceFirst(RegExp(r'^\d+[\s_-]*'), '') // strip leading numbers like 01_
      .replaceAll(
        RegExp(
          r'(_front|_back|_pdp|_missing.*|_compliant|_violation|_review|_crimp|_stamp|_window|_panel|_angle|_details|_care|_composition|_side|_top|_packaging|_wrapper).*$',
          caseSensitive: false,
        ),
        '',
      )
      .replaceAll('_', ' ')
      .replaceAll('-', ' ');

  final words = clean.split(' ').where((w) => w.isNotEmpty).map(
        (w) => w[0].toUpperCase() + (w.length > 1 ? w.substring(1).toLowerCase() : ''),
      );

  final result = words.join(' ');
  if (result.length > maxLength) {
    return '${result.substring(0, maxLength - 1)}…';
  }
  return result.isEmpty ? 'Packaged Commodity' : result;
}
