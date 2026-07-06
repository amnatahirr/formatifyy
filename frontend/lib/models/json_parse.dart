/// Safe JSON numeric parsing — backend returns doubles (e.g. 95.0) for scores.
library;

int? jsonInt(dynamic value) {
  if (value == null) return null;
  if (value is int) return value;
  if (value is double) return value.toInt();
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value);
  return null;
}

int jsonIntOr(dynamic value, int fallback) => jsonInt(value) ?? fallback;

double? jsonDouble(dynamic value) {
  if (value == null) return null;
  if (value is double) return value;
  if (value is int) return value.toDouble();
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value);
  return null;
}

double jsonDoubleOr(dynamic value, double fallback) => jsonDouble(value) ?? fallback;

/// Normalize confidence: backend may send 0-100 int or 0.0-1.0 double.
double normalizedConfidence(dynamic value) {
  final d = jsonDouble(value);
  if (d == null) return 0;
  return d > 1.0 ? d / 100.0 : d;
}
