class TemplateMappingUtils {
  // Helper methods for mapping between DB and UI values
  static String mapBulletTypeToDisplay(String dbValue) {
    const bulletMap = {
      'bullet': 'Filled Circle',
      'dash': 'Dash',
      'asterisk': 'Arrow',
    };
    return bulletMap[dbValue] ?? 'Filled Circle';
  }

  static String mapBulletTypeToDb(String displayValue) {
    const bulletMapReverse = {
      'Filled Circle': 'bullet',
      'Empty Circle': 'bullet',
      'Square': 'bullet',
      'Dash': 'dash',
      'Arrow': 'asterisk',
    };
    return bulletMapReverse[displayValue] ?? 'bullet';
  }

  static String mapNumberedStyleToDisplay(String dbValue) {
    const numberedMap = {
      '1,2,3': '1, 2, 3 (Arabic)',
      'i,ii,iii': 'I, II, III (Roman)',
      'a,b,c': 'a, b, c (Lowercase)',
      'A,B,C': 'A, B, C (Uppercase)',
    };
    return numberedMap[dbValue] ?? '1, 2, 3 (Arabic)';
  }

  static String mapNumberedStyleToDb(String displayValue) {
    const numberedMapReverse = {
      '1, 2, 3 (Arabic)': '1,2,3',
      'I, II, III (Roman)': 'i,ii,iii',
      'a, b, c (Lowercase)': 'a,b,c',
      'A, B, C (Uppercase)': 'A,B,C',
    };
    return numberedMapReverse[displayValue] ?? '1,2,3';
  }
}
