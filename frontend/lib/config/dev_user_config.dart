/// Resolves `--dart-define=USER_ID=member1|member2` to seeded backend users.
///
/// Terminal 1: flutter run -d macos --dart-define=USER_ID=member1  → user id 1 (admin)
/// Terminal 2: flutter run -d macos --dart-define=USER_ID=member2  → user id 2 (student)
class DevUserConfig {
  static String memberKey = 'member1';
  static int backendUserId = 1;
  static String username = 'student2';
  static String email = 'student2@comsats.edu.pk';
  static String role = 'student';

  static void initialize(String key) {
    memberKey = key;
    switch (key) {
      case 'member2':
        backendUserId = 2;
        username = 'student1';
        email = 'student1@comsats.edu.pk';
        role = 'student';
        break;
      case 'member1':
      default:
        backendUserId = 1;
        username = 'student2';
        email = 'student2@comsats.edu.pk';
        role = 'student';
        break;
    }
  }

  static bool get isDevSession => memberKey.isNotEmpty;
}
