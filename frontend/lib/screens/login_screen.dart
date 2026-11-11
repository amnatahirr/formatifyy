import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import '../config/api_config.dart';
import '../config/dev_user_config.dart';
import '../providers/auth_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/login_credentials_store.dart';

import '../services/super_admin_api_service.dart';

import '../theme/app_theme.dart';
import '../utils/responsive.dart';

import '../widgets/tr.dart';
/// Auth palette for the dark two-panel login / signup experience.
class _AuthColors {
  static const navy = Color(0xFF0B0F2E);
  static const panel = Color(0xFF0E1335);
  static const card = Color(0xFF151A3A);
  static const inputFill = Color(0xFF0C1028);
  static const border = Color(0xFF2A3158);
  static const accent = Color(0xFF818CF8);
  static const accentDeep = Color(0xFF6366F1);
  static const purple = Color(0xFFA855F7);
  static const muted = Color(0xFF94A3B8);
  static const mutedSoft = Color(0xFF64748B);
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({Key? key}) : super(key: key);

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  bool _isPasswordVisible = false;
  bool _rememberMe = true;
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _firstNameController = TextEditingController();
  final _lastNameController = TextEditingController();

  final _emailFocusNode = FocusNode();
  bool _isSignupMode = false;
  List<SavedLoginAccount> _savedAccounts = const [];

  final _orgCodeController = TextEditingController();
  static const _recentOrgsKey = 'recent_org_codes';
List<String> _recentOrgCodes = const [];
  /// false until user continues with a valid organization code
  bool _orgResolved = false;
  bool _resolvingOrg = false;
  String? _orgResolveError;
  bool _allowSelfSignup = true;

  int _logoTapCount = 0;
  DateTime? _lastLogoTapAt;


  List<Map<String, dynamic>> _departments = const [];
  bool _loadingDepartments = false;
  String? _departmentsError;
  int? _selectedDepartmentId;
  int? _selectedSemester;

  List<String> get _savedEmails =>
      _savedAccounts.map((a) => a.email).toList(growable: false);

  @override
  void initState() {
    super.initState();
    _emailFocusNode.addListener(_onEmailFocusChanged);
    _loadSavedCredentials();
    _loadRecentOrgCodes();
  }

  void _onEmailFocusChanged() {
    if (!_emailFocusNode.hasFocus || _savedAccounts.isEmpty) return;
    // Re-notify the controller so RawAutocomplete refreshes suggestions on tap.
    final text = _emailController.text;
    _emailController.value = TextEditingValue(
      text: text,
      selection: TextSelection.collapsed(offset: text.length),
    );
  }

  Future<void> _loadSavedCredentials() async {
    final accounts = await LoginCredentialsStore.suggestedAccounts();
    final prefill = await LoginCredentialsStore.loadPrefill();
    if (!mounted) return;
    setState(() {
      _savedAccounts = accounts;
      _rememberMe = prefill.rememberMe;
      if (prefill.email != null && prefill.email!.isNotEmpty) {
        _emailController.text = prefill.email!;
        if (prefill.password != null && prefill.password!.isNotEmpty) {
          _passwordController.text = prefill.password!;
        }
      }
    });
  }

  Future<void> _loadRecentOrgCodes() async {
  final prefs = await SharedPreferences.getInstance();
  final list = prefs.getStringList(_recentOrgsKey) ?? const [];
  if (!mounted) return;
  setState(() => _recentOrgCodes = list);
}

Future<void> _saveRecentOrgCode(String code) async {
  final normalized = code.trim().toUpperCase();
  if (normalized.isEmpty) return;
  final updated = [
    normalized,
    ..._recentOrgCodes.where((c) => c != normalized),
  ].take(5).toList();
  final prefs = await SharedPreferences.getInstance();
  await prefs.setStringList(_recentOrgsKey, updated);
  if (mounted) setState(() => _recentOrgCodes = updated);
}

Future<void> _removeRecentOrgCode(String code) async {
  final updated = _recentOrgCodes.where((c) => c != code).toList();
  final prefs = await SharedPreferences.getInstance();
  await prefs.setStringList(_recentOrgsKey, updated);
  if (mounted) setState(() => _recentOrgCodes = updated);
}

  

  Future<void> _applySuggestedAccount(String email) async {
    final normalized = email.trim().toLowerCase();
    _emailController.value = TextEditingValue(
      text: normalized,
      selection: TextSelection.collapsed(offset: normalized.length),
    );
    SavedLoginAccount? known;
    for (final a in _savedAccounts) {
      if (a.email == normalized) {
        known = a;
        break;
      }
    }
    final password =
        known?.password ?? await LoginCredentialsStore.passwordFor(normalized);
    if (!mounted) return;
    if (password != null && password.isNotEmpty) {
      _passwordController.text = password;
    } else {
      _passwordController.clear();
    }
  }

  @override
  void dispose() {
    _emailFocusNode.removeListener(_onEmailFocusChanged);
    _emailController.dispose();
    _passwordController.dispose();
    _firstNameController.dispose();
    _lastNameController.dispose();
    _emailFocusNode.dispose();
    _orgCodeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final compact = isCompact(context);

    return Scaffold(
      backgroundColor: _AuthColors.navy,
      body: compact ? _buildMobileLayout() : _buildDesktopLayout(),
    );
  }

  // ── Layouts ─────────────────────────────────────────────────────────────

  Widget _buildDesktopLayout() {
    return Row(
      children: [
        Expanded(flex: 45, child: _buildBrandingPanel()),
        Expanded(flex: 55, child: _buildFormPanel()),
      ],
    );
  }

  Widget _buildMobileLayout() {
    return SafeArea(
      child: LayoutBuilder(
        builder: (context, constraints) {
          return SingleChildScrollView(
            child: ConstrainedBox(
              constraints: BoxConstraints(
                minWidth: constraints.maxWidth,
                minHeight: constraints.maxHeight,
              ),
              child: Align(
                alignment: Alignment.center,
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(20, 28, 20, 32),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 440),
                    child: _buildAuthCard(showCompactBrand: true),
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildFormPanel() {
    return ColoredBox(
      color: _AuthColors.panel,
      child: LayoutBuilder(
        builder: (context, constraints) {
          return SingleChildScrollView(
            // No outer padding here — it would inflate minHeight past the
            // viewport and push the card off true center.
            child: ConstrainedBox(
              constraints: BoxConstraints(
                minWidth: constraints.maxWidth,
                minHeight: constraints.maxHeight,
              ),
              child: Align(
                alignment: Alignment.center,
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 48,
                    vertical: 40,
                  ),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 420),
                    child: _buildAuthCard(showCompactBrand: false),
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  // ── Left branding panel ─────────────────────────────────────────────────
  Widget _buildBrandingPanel() {
    return Container(
      color: _AuthColors.navy,
      child: Stack(
        clipBehavior: Clip.hardEdge,
        children: [
          // Ambient glow — top-left
          Positioned(
            left: -140,
            top: -120,
            child: _GlowOrb(
              diameter: 440,
              colors: [
                const Color(0xFF7C3AED).withOpacity(0.38),
                const Color(0xFF6366F1).withOpacity(0.14),
                Colors.transparent,
              ],
            ),
          ),
          // Ambient glow — bottom-left
          Positioned(
            left: -100,
            bottom: -160,
            child: _GlowOrb(
              diameter: 480,
              colors: [
                const Color(0xFF3B82F6).withOpacity(0.30),
                const Color(0xFF6366F1).withOpacity(0.10),
                Colors.transparent,
              ],
            ),
          ),
          // Dot grids
          Positioned(
            left: 28,
            top: 36,
            child: CustomPaint(
              size: const Size(120, 100),
              painter: _DotGridPainter(),
            ),
          ),
          Positioned(
            left: 48,
            bottom: 48,
            child: CustomPaint(
              size: const Size(140, 110),
              painter: _DotGridPainter(opacity: 0.18),
            ),
          ),
          // Content
          Padding(
            padding: const EdgeInsets.fromLTRB(48, 56, 40, 56),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center, // centers vertically
              crossAxisAlignment:
                  CrossAxisAlignment.center, // centers horizontally
              children: [
                _buildBrandMark(),
                const SizedBox(height: 40),
                RichText(
                  textAlign: TextAlign.center,
                  text: const TextSpan(
                    style: TextStyle(
                      fontSize: 44,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                      height: 1.18,
                      letterSpacing: -0.6,
                    ),
                    children: [
                      TextSpan(text: 'Format your reports\nin '),
                      TextSpan(
                        text: 'seconds',
                        style: TextStyle(color: _AuthColors.accent),
                      ),
                      TextSpan(text: ', not days.'),
                    ],
                  ),
                ),
                const SizedBox(height: 20),
                const Text(
                  'Join 10,000+ students using AI to perfect their project '
                  'reports according to pre-defined standards.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 15,
                    height: 1.55,
                    color: _AuthColors.muted,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBrandMark({bool centered = false}) {
    final mark = Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        ClipRRect(
  borderRadius: BorderRadius.circular(14),
  child: Image.asset(
    'assets/images/formatify-icon.png',
    width: 48,
    height: 48,
    fit: BoxFit.cover,
  ),
),
        const SizedBox(width: 14),
        const Tr('FORMATIFY',
          style: TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.w800,
            letterSpacing: 1.4,
            color: Colors.white,
          ),
        ),
      ],
    );
    final tappable = GestureDetector(
      onTap: _onLogoTapped,
      behavior: HitTestBehavior.opaque,
      child: mark,
    );
    return centered ? Center(child: tappable) : tappable;
  }

  void _onLogoTapped() {
    final now = DateTime.now();
    if (_lastLogoTapAt == null ||
        now.difference(_lastLogoTapAt!) > const Duration(seconds: 2)) {
      _logoTapCount = 1;
    } else {
      _logoTapCount += 1;
    }
    _lastLogoTapAt = now;
    if (_logoTapCount >= 5) {
      _logoTapCount = 0;
      _lastLogoTapAt = null;
      Navigator.of(context).pushNamed('/super-admin');
    }
  }

  // ── Auth card ───────────────────────────────────────────────────────────

  Widget _buildAuthCard({required bool showCompactBrand}) {
    return Container(
      padding: EdgeInsets.fromLTRB(
        showCompactBrand ? 24 : 40,
        showCompactBrand ? 28 : 44,
        showCompactBrand ? 24 : 40,
        showCompactBrand ? 24 : 40,
      ),
      decoration: BoxDecoration(
        color: _AuthColors.card,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(
          color: _AuthColors.accentDeep.withOpacity(0.35),
          width: 1,
        ),
        boxShadow: [
          BoxShadow(
            color: _AuthColors.accentDeep.withOpacity(0.18),
            blurRadius: 32,
            spreadRadius: 0,
            offset: const Offset(0, 12),
          ),
          BoxShadow(
            color: Colors.black.withOpacity(0.35),
            blurRadius: 24,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: !_orgResolved
          ? _buildOrgCodeFields(showCompactBrand: showCompactBrand)
          : _isSignupMode
              ? _buildSignupFields(showCompactBrand: showCompactBrand)
              : _buildLoginFields(showCompactBrand: showCompactBrand),
    );
  }

  Widget _buildOrgCodeFields({required bool showCompactBrand}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (showCompactBrand) ...[
          _buildBrandMark(centered: true),
          const SizedBox(height: 28),
        ],
        const Tr('Welcome to Formatify',
          style: TextStyle(
            fontSize: 26,
            fontWeight: FontWeight.w800,
            color: Colors.white,
            letterSpacing: -0.3,
          ),
        ),
        const SizedBox(height: 8),
        const Tr('Enter your organization code to continue.',
          style: TextStyle(fontSize: 14, color: _AuthColors.muted, height: 1.4),
        ),
        const SizedBox(height: 28),
        _buildTextField(
          controller: _orgCodeController,
          hint: 'Organization Code (e.g. COMSATS-LHR)',
          icon: Icons.apartment_rounded,
          textCapitalization: TextCapitalization.characters,
        ),
        if (_recentOrgCodes.isNotEmpty) ...[
  const SizedBox(height: 14),
  const Tr('Recently used',
    style: TextStyle(
      fontSize: 11.5,
      fontWeight: FontWeight.w700,
      letterSpacing: 0.6,
      color: _AuthColors.mutedSoft,
    ),
  ),
  const SizedBox(height: 8),
  Wrap(
    spacing: 8,
    runSpacing: 8,
    children: _recentOrgCodes.map((code) {
      return InkWell(
        borderRadius: BorderRadius.circular(999),
        onTap: _resolvingOrg
            ? null
            : () {
                _orgCodeController.text = code;
                _resolveOrganization();
              },
        child: Container(
          padding: const EdgeInsets.fromLTRB(12, 7, 6, 7),
          decoration: BoxDecoration(
            color: _AuthColors.inputFill,
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: _AuthColors.border),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.history,
                  size: 14, color: _AuthColors.accent),
              const SizedBox(width: 6),
              Text(
                code,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 12.5,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(width: 4),
              InkWell(
                onTap: () => _removeRecentOrgCode(code),
                borderRadius: BorderRadius.circular(999),
                child: const Padding(
                  padding: EdgeInsets.all(3),
                  child: Icon(Icons.close,
                      size: 13, color: _AuthColors.mutedSoft),
                ),
              ),
            ],
          ),
        ),
      );
    }).toList(),
  ),
],
        const SizedBox(height: 14),
        if (_orgResolveError != null) ...[
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFF3F1D2E),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFFE11D48).withOpacity(0.5)),
            ),
            child: Text(
              _orgResolveError!,
              style: const TextStyle(color: Color(0xFFFFB4C0), fontSize: 13),
            ),
          ),
          const SizedBox(height: 14),
        ],
        _buildPrimaryButton(
          label: _resolvingOrg ? 'Checking…' : 'Continue',
          onPressed: _resolvingOrg ? () {} : () => _resolveOrganization(),
        ),
      ],
    );
  }

  Future<void> _resolveOrganization() async {
    final code = _orgCodeController.text.trim();
    if (code.isEmpty) {
      setState(() => _orgResolveError = 'Please enter an organization code.');
      return;
    }
    setState(() {
      _resolvingOrg = true;
      _orgResolveError = null;
    });
    try {
      final info = await SuperAdminApiService().resolveOrganization(code);
      DevUserConfig.bindTenant(
        code: (info['org_code'] ?? code).toString(),
        name: (info['org_name'] ?? '').toString(),
        plan: (info['plan'] ?? '').toString(),
        type: (info['type'] ?? '').toString(),
        modules: info['modules'] is List ? info['modules'] as List : null,
        allowSignup: info['allow_self_signup'] == true,
        color: (info['primary_color'] ?? '').toString(),
      );
      await _saveRecentOrgCode((info['org_code'] ?? code).toString());
      if (!mounted) return;
      setState(() {
        _orgResolved = true;
        _allowSelfSignup = DevUserConfig.allowSelfSignup;
        _isSignupMode = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _orgResolveError = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => _resolvingOrg = false);
    }
  }

Widget _buildLoginFields({required bool showCompactBrand}) {
  return AutofillGroup(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (showCompactBrand) ...[
          _buildBrandMark(centered: true),
          const SizedBox(height: 28),
        ],

        const Tr('Welcome Back',
          style: TextStyle(
            fontSize: 26,
            fontWeight: FontWeight.w800,
            color: Colors.white,
            letterSpacing: -0.3,
          ),
        ),

        const SizedBox(height: 8),

        Text(
          DevUserConfig.orgName,
          style: const TextStyle(
            fontSize: 14,
            color: _AuthColors.accent,
            fontWeight: FontWeight.w600,
          ),
        ),

        const SizedBox(height: 4),

        Row(
          children: [
            Expanded(
              child: Text(
                'Org: ${DevUserConfig.orgCode}',
                style: const TextStyle(
                  fontSize: 12,
                  color: _AuthColors.muted,
                ),
              ),
            ),
            TextButton(
              onPressed: () => setState(() {
                _orgResolved = false;
                _isSignupMode = false;
                context.read<AuthProvider>().clearError();
              }),
              style: TextButton.styleFrom(
                foregroundColor: _AuthColors.accent,
                padding: EdgeInsets.zero,
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
              child: const Tr('Change',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),

        const SizedBox(height: 8),

        const Tr('Enter your details to access your dashboard.',
          style: TextStyle(
            fontSize: 14,
            color: _AuthColors.muted,
            height: 1.4,
          ),
        ),

        const SizedBox(height: 28),

        _buildEmailAutocompleteField(),

        const SizedBox(height: 14),

        _buildTextField(
          controller: _passwordController,
          hint: 'Password',
          icon: Icons.lock_outline_rounded,
          obscure: !_isPasswordVisible,
          autofillHints: const [AutofillHints.password],
          textInputAction: TextInputAction.done,
          onSubmitted: (_) => _login(context),
          suffix: IconButton(
            onPressed: () =>
                setState(() => _isPasswordVisible = !_isPasswordVisible),
            icon: Icon(
              _isPasswordVisible
                  ? Icons.visibility_off_outlined
                  : Icons.visibility_outlined,
              color: _AuthColors.mutedSoft,
              size: 20,
            ),
          ),
        ),

        const SizedBox(height: 14),

        Row(
          children: [
            SizedBox(
              height: 20,
              width: 20,
              child: Checkbox(
                value: _rememberMe,
                onChanged: (v) => setState(() => _rememberMe = v ?? true),
                activeColor: _AuthColors.accentDeep,
                checkColor: Colors.white,
                side: const BorderSide(
                  color: _AuthColors.border,
                  width: 1.4,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(4),
                ),
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                visualDensity: VisualDensity.compact,
              ),
            ),
            const SizedBox(width: 8),
            const Tr('Remember me',
              style: TextStyle(
                fontSize: 13,
                color: _AuthColors.muted,
                fontWeight: FontWeight.w500,
              ),
            ),
            const Spacer(),
            TextButton(
              onPressed: () {},
              style: TextButton.styleFrom(
                foregroundColor: _AuthColors.accent,
                padding: EdgeInsets.zero,
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
              child: const Tr('Forgot password?',
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          ],
        ),

        const SizedBox(height: 18),

        _buildErrorBanner(),

        _buildPrimaryButton(
          label: 'Sign In',
          onPressed: () => _login(context),
        ),

        const SizedBox(height: 22),

        _buildOrDivider(),

        const SizedBox(height: 18),

        _buildGoogleButton(),

        const SizedBox(height: 12),

        _buildMicrosoftButton(),

        const SizedBox(height: 24),
        _buildFooterToggle(
          prefix: "Don't have an account? ",
          action: 'Sign Up',
        ),
      ],
    ),
  );
}

  /// Signup form — dark-theme card matching login, plus department/semester.
  Widget _buildSignupFields({required bool showCompactBrand}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (showCompactBrand) ...[
          _buildBrandMark(centered: true),
          const SizedBox(height: 28),
        ],
        const Tr('Create Account',
          style: TextStyle(
            fontSize: 26,
            fontWeight: FontWeight.w800,
            color: Colors.white,
            letterSpacing: -0.3,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          '${DevUserConfig.orgName} · ${DevUserConfig.orgCode}',
          style: const TextStyle(fontSize: 13, color: _AuthColors.accent, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 22),
        _buildTextField(
          controller: _firstNameController,
          hint: 'Full name',
          icon: Icons.person_outline_rounded,
        ),
        const SizedBox(height: 14),
        _buildTextField(
          controller: _emailController,
          hint: DevUserConfig.signupEmailHint,
          icon: Icons.mail_outline_rounded,
          keyboardType: TextInputType.emailAddress,
        ),
        const SizedBox(height: 14),
        _buildTextField(
          controller: _passwordController,
          hint: 'Password',
          icon: Icons.lock_outline_rounded,
          obscure: !_isPasswordVisible,
          suffix: IconButton(
            onPressed: () =>
                setState(() => _isPasswordVisible = !_isPasswordVisible),
            icon: Icon(
              _isPasswordVisible
                  ? Icons.visibility_off_outlined
                  : Icons.visibility_outlined,
              color: _AuthColors.mutedSoft,
              size: 20,
            ),
          ),
        ),
        const SizedBox(height: 14),
        _buildDepartmentDropdown(),
        if (DevUserConfig.requiresSemesterOnSignup) ...[
          const SizedBox(height: 14),
          _buildSemesterDropdown(),
        ],
        const SizedBox(height: 18),
        _buildErrorBanner(),
        _buildPrimaryButton(
          label: 'Create Account',
          onPressed: () => _signup(context),
        ),
        const SizedBox(height: 24),
        _buildFooterToggle(
          prefix: 'Already have an account? ',
          action: 'Sign In',
        ),
      ],
    );
  }

  Widget _buildDepartmentDropdown() {
    if (_loadingDepartments) {
      return Container(
        height: 52,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: _AuthColors.inputFill,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: _AuthColors.border),
        ),
        child: const SizedBox(
          width: 20,
          height: 20,
          child: CircularProgressIndicator(strokeWidth: 2, color: _AuthColors.accent),
        ),
      );
    }

    if (_departmentsError != null && _departments.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFFEF4444).withOpacity(0.12),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFEF4444).withOpacity(0.35)),
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                _departmentsError!,
                style: const TextStyle(color: Color(0xFFEF4444), fontSize: 12),
              ),
            ),
            TextButton(
              onPressed: _loadDepartments,
              child: const Tr('Retry', style: TextStyle(fontSize: 12)),
            ),
          ],
        ),
      );
    }

    return DropdownButtonFormField<int>(
      value: _selectedDepartmentId,
      isExpanded: true,
      dropdownColor: _AuthColors.card,
      iconEnabledColor: _AuthColors.mutedSoft,
      style: const TextStyle(color: Colors.white, fontSize: 14),
      decoration: _dropdownDecoration(
        hint: 'Department',
        icon: Icons.apartment_outlined,
      ),
      hint: const Tr('Department',
        style: TextStyle(color: _AuthColors.mutedSoft, fontSize: 14),
      ),
      items: _departments
          .map(
            (d) => DropdownMenuItem<int>(
              value: d['id'] as int,
              child: Text(
                (d['name'] ?? '').toString(),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          )
          .toList(),
      onChanged: (v) => setState(() => _selectedDepartmentId = v),
    );
  }

  Widget _buildSemesterDropdown() {
    return DropdownButtonFormField<int>(
      value: _selectedSemester,
      isExpanded: true,
      dropdownColor: _AuthColors.card,
      iconEnabledColor: _AuthColors.mutedSoft,
      style: const TextStyle(color: Colors.white, fontSize: 14),
      decoration: _dropdownDecoration(
        hint: 'Current semester',
        icon: Icons.school_outlined,
      ),
      hint: const Tr('Current semester',
        style: TextStyle(color: _AuthColors.mutedSoft, fontSize: 14),
      ),
      items: const [
        DropdownMenuItem(value: 6, child: Tr('Semester 6')),
        DropdownMenuItem(value: 7, child: Tr('Semester 7')),
      ],
      onChanged: (v) => setState(() => _selectedSemester = v),
    );
  }

  InputDecoration _dropdownDecoration({
    required String hint,
    required IconData icon,
  }) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: _AuthColors.mutedSoft, fontSize: 14),
      filled: true,
      fillColor: _AuthColors.inputFill,
      prefixIcon: Icon(icon, size: 20, color: _AuthColors.mutedSoft),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 16),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: _AuthColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: _AuthColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: _AuthColors.accentDeep, width: 1.5),
      ),
    );
  }

  Future<void> _loadDepartments() async {
    setState(() {
      _loadingDepartments = true;
      _departmentsError = null;
    });
    try {
      final uri = Uri.parse('${ApiConfig.getBaseUrl()}/auth/departments').replace(
        queryParameters: {
          if (DevUserConfig.orgCode.trim().isNotEmpty)
            'org_code': DevUserConfig.orgCode.trim(),
        },
      );
      final response = await http.get(uri).timeout(const Duration(seconds: 10));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final list = List<Map<String, dynamic>>.from(
          (data['departments'] as List? ?? const []).map(
            (e) => Map<String, dynamic>.from(e as Map),
          ),
        );
        if (!mounted) return;
        setState(() {
          _departments = list;
          if (_selectedDepartmentId != null &&
              !_departments.any((d) => d['id'] == _selectedDepartmentId)) {
            _selectedDepartmentId = null;
          }
        });
      } else {
        if (!mounted) return;
        setState(() => _departmentsError = 'Could not load departments.');
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _departmentsError = 'Could not load departments.');
      debugPrint('[LoginScreen] loadDepartments error: $e');
    } finally {
      if (mounted) setState(() => _loadingDepartments = false);
    }
  }

  // ── Shared field / button widgets ───────────────────────────────────────

  InputDecoration _fieldDecoration({
    required String hint,
    required IconData icon,
    Widget? suffix,
  }) {
    return InputDecoration(
      hintText: hint,
      hintStyle: const TextStyle(color: _AuthColors.mutedSoft, fontSize: 14),
      filled: true,
      fillColor: _AuthColors.inputFill,
      prefixIcon: Icon(icon, size: 20, color: _AuthColors.mutedSoft),
      suffixIcon: suffix,
      contentPadding: const EdgeInsets.symmetric(
        horizontal: 14,
        vertical: 16,
      ),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: _AuthColors.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: _AuthColors.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(
          color: _AuthColors.accentDeep,
          width: 1.5,
        ),
      ),
    );
  }

  /// Email field with saved-account suggestions (fills password when available).
  Widget _buildEmailAutocompleteField() {
    return RawAutocomplete<String>(
      textEditingController: _emailController,
      focusNode: _emailFocusNode,
      optionsBuilder: (TextEditingValue value) {
        if (_savedAccounts.isEmpty) return const Iterable<String>.empty();
        final emails = _savedEmails;
        final q = value.text.trim().toLowerCase();
        // If empty OR exactly a saved account (pre-filled), show ALL accounts
        // so testers can switch student / admin / supervisor quickly.
        if (q.isEmpty || emails.contains(q)) {
          return emails;
        }
        return emails.where((e) => e.contains(q));
      },
      onSelected: (String selection) {
        _applySuggestedAccount(selection);
      },
      optionsViewBuilder: (context, onSelected, options) {
        final opts = options.toList(growable: false);
        if (opts.isEmpty) return const SizedBox.shrink();
        final byEmail = {
          for (final a in _savedAccounts) a.email: a,
        };
        return Align(
          alignment: Alignment.topLeft,
          child: Material(
            elevation: 6,
            color: _AuthColors.card,
            borderRadius: BorderRadius.circular(12),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 260, minWidth: 300),
              child: ListView.separated(
                padding: const EdgeInsets.symmetric(vertical: 6),
                shrinkWrap: true,
                itemCount: opts.length,
                separatorBuilder: (_, __) => Divider(
                  height: 1,
                  color: Colors.white.withOpacity(0.08),
                ),
                itemBuilder: (context, index) {
                  final email = opts[index];
                  final account = byEmail[email];
                  final role = account?.roleLabel;
                  return ListTile(
                    dense: true,
                    leading: Icon(
                      role == 'Admin'
                          ? Icons.admin_panel_settings_outlined
                          : role == 'Supervisor'
                              ? Icons.school_outlined
                              : Icons.person_outline,
                      color: _AuthColors.accent,
                      size: 22,
                    ),
                    title: Text(
                      email,
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    subtitle: Text(
                      role != null && role.isNotEmpty
                          ? '$role · Tap to autofill'
                          : 'Tap to autofill',
                      style: const TextStyle(
                        color: _AuthColors.mutedSoft,
                        fontSize: 11,
                      ),
                    ),
                    onTap: () => onSelected(email),
                  );
                },
              ),
            ),
          ),
        );
      },
      fieldViewBuilder: (context, controller, focusNode, onFieldSubmitted) {
        return TextField(
          controller: controller,
          focusNode: focusNode,
          keyboardType: TextInputType.emailAddress,
          autofillHints: const [AutofillHints.username, AutofillHints.email],
          textInputAction: TextInputAction.next,
          style: const TextStyle(color: Colors.white, fontSize: 14),
          cursorColor: _AuthColors.accent,
          decoration: _fieldDecoration(
            hint: 'Email address',
            icon: Icons.mail_outline_rounded,
          ),
          onSubmitted: (_) => onFieldSubmitted(),
        );
      },
    );
  }

Widget _buildTextField({
  required TextEditingController controller,
  required String hint,
  required IconData icon,
  bool obscure = false,
  TextInputType? keyboardType,
  Widget? suffix,
  Iterable<String>? autofillHints,
  TextInputAction? textInputAction,
  ValueChanged<String>? onSubmitted,
  TextCapitalization textCapitalization = TextCapitalization.none,
}) {
  return TextField(
    controller: controller,
    obscureText: obscure,
    keyboardType: keyboardType,
    autofillHints: autofillHints,
    textInputAction: textInputAction,
    onSubmitted: onSubmitted,
    textCapitalization: textCapitalization,
    style: const TextStyle(color: Colors.white, fontSize: 14),
    cursorColor: _AuthColors.accent,
    decoration: _fieldDecoration(hint: hint, icon: icon, suffix: suffix),
  );
}

  Widget _buildErrorBanner() {
    return Consumer<AuthProvider>(
      builder: (context, auth, _) {
        if (auth.errorMessage == null) return const SizedBox.shrink();
        return Container(
          width: double.infinity,
          margin: const EdgeInsets.only(bottom: 14),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: const Color(0xFFEF4444).withOpacity(0.12),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: const Color(0xFFEF4444).withOpacity(0.35),
            ),
          ),
          child: Text(
            auth.errorMessage!,
            style: const TextStyle(
              color: Color(0xFFEF4444),
              fontSize: 12,
              fontWeight: FontWeight.w500,
            ),
          ),
        );
      },
    );
  }

  Widget _buildPrimaryButton({
    required String label,
    required VoidCallback onPressed,
  }) {
    return Consumer<AuthProvider>(
      builder: (context, auth, _) {
        return SizedBox(
          height: 52,
          child: DecoratedBox(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              gradient: LinearGradient(
                colors: auth.isLoading
                    ? [
                        _AuthColors.accentDeep.withOpacity(0.5),
                        _AuthColors.purple.withOpacity(0.5),
                      ]
                    : const [_AuthColors.accentDeep, _AuthColors.purple],
              ),
              boxShadow: auth.isLoading
                  ? null
                  : [
                      BoxShadow(
                        color: _AuthColors.accentDeep.withOpacity(0.4),
                        blurRadius: 16,
                        offset: const Offset(0, 6),
                      ),
                    ],
            ),
            child: ElevatedButton(
              onPressed: auth.isLoading ? null : onPressed,
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.transparent,
                disabledBackgroundColor: Colors.transparent,
                shadowColor: Colors.transparent,
                foregroundColor: Colors.white,
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
              child: auth.isLoading
                  ? const SizedBox(
                      height: 22,
                      width: 22,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.2,
                        color: Colors.white,
                      ),
                    )
                  : Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          label,
                          style: const TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const SizedBox(width: 8),
                        const Icon(Icons.arrow_forward_rounded, size: 18),
                      ],
                    ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildOrDivider() {
    return Row(
      children: [
        Expanded(
          child: Divider(color: Colors.white.withOpacity(0.12), thickness: 1),
        ),
        const Padding(
          padding: EdgeInsets.symmetric(horizontal: 14),
          child: Tr('OR',
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: _AuthColors.mutedSoft,
              letterSpacing: 0.8,
            ),
          ),
        ),
        Expanded(
          child: Divider(color: Colors.white.withOpacity(0.12), thickness: 1),
        ),
      ],
    );
  }

  Widget _buildGoogleButton() {
    return SizedBox(
      height: 48,
      child: ElevatedButton(
        onPressed: () => _signInWithGoogle(context),
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.white,
          foregroundColor: const Color(0xFF1F2937),
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const _GoogleGIcon(size: 18),
            const SizedBox(width: 10),
            Tr('Continue with Google',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: Colors.grey.shade800,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMicrosoftButton() {
    return SizedBox(
      height: 48,
      child: OutlinedButton(
        onPressed: () {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Tr('Microsoft sign-in is not wired up yet — ask if you want it next.',
              ),
            ),
          );
        },
        style: OutlinedButton.styleFrom(
          foregroundColor: Colors.white,
          backgroundColor: _AuthColors.inputFill,
          side: const BorderSide(color: _AuthColors.border),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        child: const Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _MicrosoftLogo(size: 16),
            SizedBox(width: 10),
            Tr('Continue with Microsoft',
              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFooterToggle({required String prefix, required String action}) {
    return Center(
      child: GestureDetector(
        onTap: () {
          final next = !_isSignupMode;
          setState(() => _isSignupMode = next);
          context.read<AuthProvider>().clearError();
          if (next && _departments.isEmpty && !_loadingDepartments) {
            _loadDepartments();
          }
        },
        child: RichText(
          text: TextSpan(
            text: prefix,
            style: const TextStyle(fontSize: 13, color: _AuthColors.muted),
            children: [
              TextSpan(
                text: action,
                style: const TextStyle(
                  fontSize: 13,
                  color: _AuthColors.accent,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  // ── Auth actions (unchanged logic) ──────────────────────────────────────

  String? _friendlyRoleLabel(String? role) {
    switch ((role ?? '').toLowerCase()) {
      case 'admin':
        return 'Admin';
      case 'supervisor':
        return 'Supervisor';
      case 'student':
        return 'Student';
      default:
        return role;
    }
  }

  void _login(BuildContext context) async {
    final auth = context.read<AuthProvider>();
    final theme = context.read<ThemeProvider>();
    final email = _emailController.text.trim();
    final password = _passwordController.text;
    final success = await auth.login(
      email,
      password,
      rememberMe: _rememberMe,
    );

    if (success && mounted) {
      await LoginCredentialsStore.saveSuccessfulLogin(
        email: email,
        password: password,
        rememberMe: _rememberMe,
        roleLabel: _friendlyRoleLabel(auth.userRole),
      );
      TextInput.finishAutofillContext(shouldSave: _rememberMe);
      final accounts = await LoginCredentialsStore.suggestedAccounts();
      if (mounted) setState(() => _savedAccounts = accounts);

      await theme.bindToUser(auth.userId);
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Tr('Login successful!')));
    }
  }

  void _signup(BuildContext context) async {
    final auth = context.read<AuthProvider>();
    final theme = context.read<ThemeProvider>();

    if (_selectedDepartmentId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Tr('Please select your department.')),
      );
      return;
    }
    final requiresSemester = DevUserConfig.requiresSemesterOnSignup;
    if (requiresSemester && _selectedSemester == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Tr('Please select your current semester.')),
      );
      return;
    }

    final success = await auth.signup(
      _firstNameController.text.trim(),
      _emailController.text.trim(),
      _passwordController.text,
      departmentId: _selectedDepartmentId!,
      currentSemester: requiresSemester ? _selectedSemester : null,
      rememberMe: true,
    );

    if (success && mounted) {
      await LoginCredentialsStore.saveSuccessfulLogin(
        email: _emailController.text.trim(),
        password: _passwordController.text,
        rememberMe: true,
        roleLabel: _friendlyRoleLabel(auth.userRole) ?? 'Student',
      );
      final accounts = await LoginCredentialsStore.suggestedAccounts();
      if (mounted) setState(() => _savedAccounts = accounts);

      await theme.bindToUser(auth.userId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Tr('Signup successful!')),
      );
    }
  }

  void _signInWithGoogle(BuildContext context) async {
    final auth = context.read<AuthProvider>();
    final theme = context.read<ThemeProvider>();
    final success = await auth.googleSignIn();

    if (success && mounted) {
      await theme.bindToUser(auth.userId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Tr('Google Sign-In successful!')),
      );
    }
  }

  // Kept for existing AuthProvider.githubSignIn support; not shown in UI
  // (Microsoft is visual-only until OAuth is approved).
  // ignore: unused_element
  void _signInWithGitHub(BuildContext context) async {
    final auth = context.read<AuthProvider>();
    final theme = context.read<ThemeProvider>();
    final success = await auth.githubSignIn();

    if (success && mounted) {
      await theme.bindToUser(auth.userId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Tr('GitHub Sign-In successful!')),
      );
    }
  }
}

// ── Decorative helpers ────────────────────────────────────────────────────

class _GlowOrb extends StatelessWidget {
  final double diameter;
  final List<Color> colors;

  const _GlowOrb({required this.diameter, required this.colors});

  @override
  Widget build(BuildContext context) {
    // Soft radial wash (no ImageFilter.blur — keeps paint cheap & screenshot-safe).
    return Container(
      width: diameter,
      height: diameter,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: RadialGradient(colors: colors, stops: const [0.0, 0.45, 1.0]),
      ),
    );
  }
}

class _DotGridPainter extends CustomPainter {
  final double opacity;

  _DotGridPainter({this.opacity = 0.22});

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white.withOpacity(opacity)
      ..style = PaintingStyle.fill;
    const step = 14.0;
    const radius = 1.2;
    for (double y = 0; y < size.height; y += step) {
      for (double x = 0; x < size.width; x += step) {
        canvas.drawCircle(Offset(x, y), radius, paint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _DotGridPainter oldDelegate) =>
      oldDelegate.opacity != opacity;
}

class _GoogleGIcon extends StatelessWidget {
  final double size;

  const _GoogleGIcon({required this.size});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: size,
      height: size,
      child: CustomPaint(painter: _GoogleGPainter()),
    );
  }
}

class _GoogleGPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final stroke = size.width * 0.18;
    final rect = Offset.zero & size;
    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.butt;

    // Simplified multicolor G arc segments
    paint.color = const Color(0xFF4285F4);
    canvas.drawArc(rect.deflate(stroke / 2), -0.4, 1.6, false, paint);
    paint.color = const Color(0xFF34A853);
    canvas.drawArc(rect.deflate(stroke / 2), 1.2, 1.0, false, paint);
    paint.color = const Color(0xFFFBBC05);
    canvas.drawArc(rect.deflate(stroke / 2), 2.2, 0.9, false, paint);
    paint.color = const Color(0xFFEA4335);
    canvas.drawArc(rect.deflate(stroke / 2), 3.1, 1.0, false, paint);

    // Horizontal bar of the G
    final bar = Paint()
      ..color = const Color(0xFF4285F4)
      ..style = PaintingStyle.fill;
    canvas.drawRect(
      Rect.fromLTWH(
        size.width * 0.45,
        size.height * 0.42,
        size.width * 0.45,
        stroke,
      ),
      bar,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _MicrosoftLogo extends StatelessWidget {
  final double size;

  const _MicrosoftLogo({required this.size});

  @override
  Widget build(BuildContext context) {
    final gap = size * 0.12;
    final cell = (size - gap) / 2;
    return SizedBox(
      width: size,
      height: size,
      child: Column(
        children: [
          Row(
            children: [
              _sq(const Color(0xFFF25022), cell),
              SizedBox(width: gap),
              _sq(const Color(0xFF7FBA00), cell),
            ],
          ),
          SizedBox(height: gap),
          Row(
            children: [
              _sq(const Color(0xFF00A4EF), cell),
              SizedBox(width: gap),
              _sq(const Color(0xFFFFB900), cell),
            ],
          ),
        ],
      ),
    );
  }

  Widget _sq(Color color, double size) =>
      Container(width: size, height: size, color: color);
}
