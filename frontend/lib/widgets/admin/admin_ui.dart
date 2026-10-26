import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../theme/app_theme.dart';
import '../../utils/responsive.dart';

import '../tr.dart';
class AdminColors {
  // Aligned with AppPalette.dark (admin/supervisor/super-admin are dark-only) so
  // these consoles share the student side's visual language.
  static const background = Color(0xFF0A0E1A); // scaffold
  static const surface = Color(0xFF151A3A); // AppPalette.dark.surface
  static const surfaceAlt = Color(0xFF0D1220); // AppPalette.dark.surfaceAlt
  static const card = Color(0xFF1A2040); // surfaceElevated
  static const inputFill = Color(0xFF0C1028);
  // Solid approximations of the translucent palette borders — kept const so
  // `const BorderSide(...)` call sites keep compiling.
  static const border = Color(0xFF272C5C); // ≈ purple@18% on navy
  static const borderStrong = Color(0xFF34387C); // ≈ indigo@35% on surface
  static const primary = Color(0xFF6366F1); // accentAlt / gradient start
  static const accent = Color(0xFFA855F7); // AppPalette.dark.accent
  static const accentBright = Color(0xFFC084FC); // gradient end
  // Semantic status — keep recognizable.
  static const success = Color(0xFF10B981);
  static const warning = Color(0xFFF59E0B);
  static const danger = Color(0xFFEF4444);

  static const primaryGradient = LinearGradient(
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
    colors: [primary, accent, accentBright],
  );
}

/// Card corner radius shared with `AppPalette.dark.cardRadius`.
const double adminCardRadius = 18;

/// Smaller radius for inner tiles, chips and list rows.
const double adminTileRadius = 12;

/// Indigo glow + depth shadow used by every elevated admin surface.
List<BoxShadow> adminCardGlow({double opacity = 0.26}) => [
      BoxShadow(
        color: AdminColors.primary.withOpacity(opacity),
        blurRadius: 30,
        spreadRadius: 1,
        offset: const Offset(0, 12),
      ),
      BoxShadow(
        color: Colors.black.withOpacity(0.32),
        blurRadius: 20,
        offset: const Offset(0, 8),
      ),
    ];

BoxDecoration adminCardDecoration({
  Color? color,
  Color? borderColor,
  double? radius,
  bool glow = true,
}) =>
    BoxDecoration(
      color: color ?? AdminColors.card,
      borderRadius: BorderRadius.circular(radius ?? adminCardRadius),
      border: Border.all(color: borderColor ?? AdminColors.borderStrong),
      boxShadow: glow ? adminCardGlow() : null,
    );

/// Tinted square that holds a leading icon on cards, headers and list rows.
class AdminIconBadge extends StatelessWidget {
  final IconData icon;
  final Color color;
  final double size;
  final double padding;

  const AdminIconBadge({
    super.key,
    required this.icon,
    this.color = AdminColors.primary,
    this.size = 20,
    this.padding = 10,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.all(padding),
      decoration: BoxDecoration(
        color: color.withOpacity(0.16),
        borderRadius: BorderRadius.circular(adminTileRadius),
        border: Border.all(color: color.withOpacity(0.28)),
      ),
      child: Icon(icon, color: color, size: size),
    );
  }
}

/// Pill used for statuses, counts and filters.
class AdminPill extends StatelessWidget {
  final String label;
  final Color color;
  final IconData? icon;

  const AdminPill({
    super.key,
    required this.label,
    this.color = AdminColors.primary,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: color.withOpacity(0.14),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withOpacity(0.35)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 12, color: color),
            const SizedBox(width: 5),
          ],
          Text(
            label,
            style: TextStyle(
              color: color,
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.2,
            ),
          ),
        ],
      ),
    );
  }
}

/// Selectable filter chip matching the sidebar's selected-pill treatment.
class AdminFilterChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;
  final IconData? icon;

  const AdminFilterChip({
    super.key,
    required this.label,
    required this.selected,
    required this.onTap,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(999),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        padding: const EdgeInsets.symmetric(horizontal: 15, vertical: 9),
        decoration: BoxDecoration(
          color: selected
              ? AdminColors.primary.withOpacity(0.2)
              : AdminColors.surfaceAlt,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(
            color: selected
                ? AdminColors.accent.withOpacity(0.6)
                : AdminColors.borderStrong,
            width: selected ? 1.4 : 1,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(
                icon,
                size: 14,
                color: selected
                    ? AdminColors.accentBright
                    : Colors.white.withOpacity(0.55),
              ),
              const SizedBox(width: 6),
            ],
            Text(
              label,
              style: TextStyle(
                fontSize: 12.5,
                fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                color: selected ? Colors.white : Colors.white.withOpacity(0.65),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Shared dialog frame so every admin/supervisor dialog matches the cards.
RoundedRectangleBorder adminDialogShape() => RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(20),
      side: const BorderSide(color: AdminColors.borderStrong),
    );

/// Rounded gradient progress bar used for group/document progress.
class AdminProgressBar extends StatelessWidget {
  /// Fraction between 0 and 1.
  final double value;
  final double height;
  final Color? color;

  const AdminProgressBar({
    super.key,
    required this.value,
    this.height = 8,
    this.color,
  });

  @override
  Widget build(BuildContext context) {
    final fraction = value.isNaN ? 0.0 : value.clamp(0.0, 1.0);
    return ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: Container(
        height: height,
        decoration: BoxDecoration(
          color: AdminColors.surfaceAlt,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: AdminColors.border, width: 0.8),
        ),
        child: Align(
          alignment: Alignment.centerLeft,
          child: FractionallySizedBox(
            widthFactor: fraction,
            child: Container(
              decoration: BoxDecoration(
                color: color,
                gradient: color == null ? AdminColors.primaryGradient : null,
                borderRadius: BorderRadius.circular(999),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class AdminPage extends StatelessWidget {
  final Widget child;
  final Future<void> Function()? onRefresh;
  final bool scrollable;

  const AdminPage({
    super.key,
    required this.child,
    this.onRefresh,
    this.scrollable = true,
  });

  @override
  Widget build(BuildContext context) {
    final compact = isCompact(context);
    final content = Padding(
      padding: EdgeInsets.fromLTRB(
        compact ? 16 : 32,
        compact ? 16 : 26,
        compact ? 16 : 32,
        compact ? 20 : 32,
      ),
      child: child,
    );
    Widget body;
    if (!scrollable) {
      body = content;
    } else if (onRefresh == null) {
      body = SingleChildScrollView(child: content);
    } else {
      body = RefreshIndicator(
        onRefresh: onRefresh!,
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          child: content,
        ),
      );
    }
    // Inner backdrop (no orbs): AdminPage always renders inside a shell or a
    // detail route, where orb circles would be clipped into visible blobs.
    return AppPalette.dark.innerGlowBackdrop(child: body);
  }
}

class AdminSubPage extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget child;
  final Widget? floatingActionButton;
  final Future<void> Function()? onRefresh;
  final VoidCallback? onBack;

  const AdminSubPage({
    super.key,
    required this.title,
    this.subtitle,
    required this.child,
    this.floatingActionButton,
    this.onRefresh,
    this.onBack,
  });

  void _handleBack(BuildContext context) {
    if (onBack != null) {
      onBack!();
    } else {
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final content = onRefresh == null
        ? child
        : RefreshIndicator(onRefresh: onRefresh!, child: child);
    final compact = isCompact(context);

    if (compact) {
      return Scaffold(
        backgroundColor: Colors.transparent,
        floatingActionButton: floatingActionButton,
        appBar: AppBar(
          backgroundColor: AdminColors.surface,
          elevation: 0,
          shape: const Border(
            bottom: BorderSide(color: AdminColors.borderStrong),
          ),
          leading: IconButton(
            icon: const Icon(Icons.arrow_back_rounded),
            onPressed: () => _handleBack(context),
          ),
          title: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
              ),
              if (subtitle != null)
                Text(
                  subtitle!,
                  style: TextStyle(
                    fontSize: 11,
                    color: Colors.white.withOpacity(0.55),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
            ],
          ),
        ),
        body: AppPalette.dark.innerGlowBackdrop(child: content),
      );
    }

    return Scaffold(
      backgroundColor: Colors.transparent,
      floatingActionButton: floatingActionButton,
      body: AppPalette.dark.innerGlowBackdrop(
        child: Row(
        children: [
          Container(
            width: 224,
            decoration: const BoxDecoration(
              color: AdminColors.surface,
              border: Border(
                right: BorderSide(color: AdminColors.borderStrong),
              ),
            ),
            child: SafeArea(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(18, 22, 18, 18),
                    child: Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(9),
                          decoration: BoxDecoration(
                            gradient: AdminColors.primaryGradient,
                            borderRadius: BorderRadius.circular(10),
                            boxShadow: [
                              BoxShadow(
                                color: AdminColors.primary.withOpacity(0.4),
                                blurRadius: 14,
                                offset: const Offset(0, 5),
                              ),
                            ],
                          ),
                          child: const Icon(
                            Icons.shield_rounded,
                            color: Colors.white,
                            size: 18,
                          ),
                        ),
                        const SizedBox(width: 11),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Tr('FORMATIFY',
                                style: TextStyle(
                                  fontSize: 13.5,
                                  fontWeight: FontWeight.w700,
                                  color: Colors.white,
                                  letterSpacing: 0.4,
                                ),
                              ),
                              Tr('Admin Panel',
                                style: TextStyle(
                                  fontSize: 10,
                                  color: Colors.white.withOpacity(0.5),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const Divider(height: 1, color: AdminColors.border),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(12, 16, 12, 8),
                    child: InkWell(
                      onTap: () => _handleBack(context),
                      borderRadius: BorderRadius.circular(adminTileRadius),
                      child: Container(
                        width: double.infinity,
                        padding: const EdgeInsets.symmetric(
                          horizontal: 14,
                          vertical: 12,
                        ),
                        decoration: BoxDecoration(
                          color: AdminColors.surfaceAlt,
                          borderRadius: BorderRadius.circular(adminTileRadius),
                          border: Border.all(color: AdminColors.borderStrong),
                        ),
                        child: Row(
                          children: [
                            Icon(
                              Icons.arrow_back_rounded,
                              size: 17,
                              color: Colors.white.withOpacity(0.8),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Tr('Back',
                                style: TextStyle(
                                  fontSize: 12.5,
                                  fontWeight: FontWeight.w600,
                                  color: Colors.white.withOpacity(0.88),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(12, 6, 12, 12),
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 12,
                      ),
                      decoration: BoxDecoration(
                        color: AdminColors.primary.withOpacity(0.16),
                        borderRadius: BorderRadius.circular(adminTileRadius),
                        border: Border.all(
                          color: AdminColors.accent.withOpacity(0.55),
                          width: 1.4,
                        ),
                      ),
                      child: Text(
                        title,
                        style: const TextStyle(
                          fontSize: 12.5,
                          fontWeight: FontWeight.w700,
                          color: AdminColors.accentBright,
                        ),
                      ),
                    ),
                  ),
                  const Spacer(),
                  Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        Container(
                          width: 7,
                          height: 7,
                          decoration: const BoxDecoration(
                            color: AdminColors.success,
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Tr('Live backend data',
                          style: TextStyle(
                            fontSize: 11,
                            color: Colors.white.withOpacity(0.45),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.fromLTRB(32, 24, 32, 20),
                  decoration: const BoxDecoration(
                    color: AdminColors.surface,
                    border: Border(
                      bottom: BorderSide(color: AdminColors.borderStrong),
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        title,
                        style: const TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                          letterSpacing: -0.3,
                        ),
                      ),
                      if (subtitle != null) ...[
                        const SizedBox(height: 5),
                        Text(
                          subtitle!,
                          style: TextStyle(
                            color: Colors.white.withOpacity(0.62),
                            fontSize: 13,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                Expanded(child: content),
              ],
            ),
          ),
        ],
        ),
      ),
    );
  }
}

class AdminPageHeader extends StatelessWidget {
  final String title;
  final String subtitle;
  final Widget? trailing;

  const AdminPageHeader({
    super.key,
    required this.title,
    required this.subtitle,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    final compact = isCompact(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: TextStyle(
                  fontSize: compact ? 20 : 28,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                  letterSpacing: -0.3,
                  height: 1.15,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                subtitle,
                style: TextStyle(
                  fontSize: compact ? 12 : 13.5,
                  color: Colors.white.withOpacity(0.62),
                  height: 1.4,
                ),
              ),
            ],
          ),
        ),
        if (trailing != null) ...[
          const SizedBox(width: 16),
          trailing!,
        ],
      ],
    );
  }
}

/// One-line contextual status for pages whose title already lives in the shell
/// top bar — counts, filters, "N unread" — so the heading is never repeated.
class AdminPageMeta extends StatelessWidget {
  final String text;
  final IconData? icon;

  const AdminPageMeta({super.key, required this.text, this.icon});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        if (icon != null)
          Icon(icon, size: 15, color: AdminColors.accent.withOpacity(0.85))
        else
          Container(
            width: 7,
            height: 7,
            decoration: const BoxDecoration(
              gradient: AdminColors.primaryGradient,
              shape: BoxShape.circle,
            ),
          ),
        const SizedBox(width: 9),
        Expanded(
          child: Text(
            text,
            style: TextStyle(
              fontSize: 13,
              color: Colors.white.withOpacity(0.6),
              height: 1.4,
            ),
          ),
        ),
      ],
    );
  }
}

/// Small caps label that separates groups of cards on a page.
class AdminSectionLabel extends StatelessWidget {
  final String label;
  final Widget? trailing;

  const AdminSectionLabel({super.key, required this.label, this.trailing});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 3,
          height: 15,
          decoration: BoxDecoration(
            gradient: AdminColors.primaryGradient,
            borderRadius: BorderRadius.circular(99),
          ),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            label,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 14,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.1,
            ),
          ),
        ),
        if (trailing != null) trailing!,
      ],
    );
  }
}

class AdminStatCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color? accent;

  const AdminStatCard({
    super.key,
    required this.title,
    required this.value,
    required this.icon,
    this.accent,
  });

  @override
  Widget build(BuildContext context) {
    final color = accent ?? AdminColors.primary;
    final compact = isCompact(context);
    return Container(
      width: double.infinity,
      padding: EdgeInsets.all(compact ? 14 : 20),
      decoration: adminCardDecoration(borderColor: color.withOpacity(0.32)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center,
        mainAxisSize: MainAxisSize.min,
        children: [
          AdminIconBadge(
            icon: icon,
            color: color,
            size: compact ? 18 : 22,
            padding: compact ? 8 : 10,
          ),
          SizedBox(height: compact ? 10 : 18),
          Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: compact ? 24 : 30,
              fontWeight: FontWeight.w700,
              color: Colors.white,
              height: 1.1,
              letterSpacing: -0.5,
            ),
          ),
          SizedBox(height: compact ? 4 : 6),
          Text(
            title,
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              fontSize: compact ? 12 : 13,
              color: Colors.white.withOpacity(0.62),
              height: 1.25,
            ),
          ),
        ],
      ),
    );
  }
}

class AdminActionTile extends StatelessWidget {
  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback onTap;

  const AdminActionTile({
    super.key,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final compact = isCompact(context);
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(adminCardRadius),
      child: Container(
        width: compact ? double.infinity : 220,
        padding: EdgeInsets.all(compact ? 14 : 18),
        decoration: adminCardDecoration(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            AdminIconBadge(icon: icon, size: compact ? 20 : 22, padding: 9),
            SizedBox(height: compact ? 10 : 14),
            Text(
              title,
              style: TextStyle(
                fontWeight: FontWeight.w700,
                color: Colors.white,
                fontSize: compact ? 14 : 15,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              subtitle,
              style: TextStyle(
                color: Colors.white.withOpacity(0.6),
                fontSize: compact ? 11.5 : 12,
                height: 1.35,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class AdminDepartmentTile extends StatelessWidget {
  final String title;
  final String subtitle;
  final String badge;
  final VoidCallback onTap;

  const AdminDepartmentTile({
    super.key,
    required this.title,
    required this.subtitle,
    required this.badge,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(adminCardRadius),
        child: Container(
          padding: const EdgeInsets.all(18),
          decoration: adminCardDecoration(),
          child: Row(
            children: [
              const AdminIconBadge(icon: Icons.apartment_rounded, padding: 12),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(fontWeight: FontWeight.w700, color: Colors.white, fontSize: 16)),
                    const SizedBox(height: 4),
                    Text(subtitle, style: TextStyle(color: Colors.white.withOpacity(0.62), fontSize: 13)),
                  ],
                ),
              ),
              AdminPill(label: badge),
              const SizedBox(width: 8),
              Icon(Icons.chevron_right_rounded, color: Colors.white.withOpacity(0.45)),
            ],
          ),
        ),
      ),
    );
  }
}

class AdminSectionCard extends StatelessWidget {
  final String title;
  final Widget child;
  final String? subtitle;
  final IconData? icon;
  final Color? accent;
  final Widget? trailing;

  const AdminSectionCard({
    super.key,
    required this.title,
    required this.child,
    this.subtitle,
    this.icon,
    this.accent,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    final color = accent ?? AdminColors.primary;
    return Container(
      padding: const EdgeInsets.all(22),
      decoration: adminCardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (icon != null) ...[
                AdminIconBadge(icon: icon!, color: color, size: 18, padding: 9),
                const SizedBox(width: 12),
              ],
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                    if (subtitle != null) ...[
                      const SizedBox(height: 4),
                      Text(
                        subtitle!,
                        style: TextStyle(
                          fontSize: 12.5,
                          color: Colors.white.withOpacity(0.6),
                          height: 1.4,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              if (trailing != null) trailing!,
            ],
          ),
          const SizedBox(height: 18),
          child,
        ],
      ),
    );
  }
}

class AdminLoadingView extends StatelessWidget {
  final String? label;

  const AdminLoadingView({super.key, this.label});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const SizedBox(
            width: 30,
            height: 30,
            child: CircularProgressIndicator(
              color: AdminColors.accent,
              strokeWidth: 2.6,
            ),
          ),
          if (label != null) ...[
            const SizedBox(height: 14),
            Text(
              label!,
              style: TextStyle(
                color: Colors.white.withOpacity(0.6),
                fontSize: 12.5,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class AdminEmptyView extends StatelessWidget {
  final String message;
  final String? actionLabel;
  final Future<void> Function()? onAction;
  final IconData icon;
  final String? title;

  const AdminEmptyView({
    super.key,
    required this.message,
    this.actionLabel,
    this.onAction,
    this.icon = Icons.inbox_rounded,
    this.title,
  });

  @override
  Widget build(BuildContext context) {
    return AdminStateCard(
      icon: icon,
      iconColor: AdminColors.accent,
      title: title,
      message: message,
      action: onAction == null
          ? null
          : OutlinedButton.icon(
              onPressed: onAction,
              icon: const Icon(Icons.refresh_rounded, size: 16),
              label: Text(actionLabel ?? 'Refresh'),
              style: OutlinedButton.styleFrom(
                foregroundColor: AdminColors.accent,
                side: BorderSide(color: AdminColors.accent.withOpacity(0.5)),
                padding: const EdgeInsets.symmetric(
                  horizontal: 18,
                  vertical: 12,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(adminTileRadius),
                ),
              ),
            ),
    );
  }
}

/// Centered glowing card used by the empty and error states so a mostly blank
/// pane still has the layered look of the auth screens.
class AdminStateCard extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String? title;
  final String message;
  final Widget? action;

  const AdminStateCard({
    super.key,
    required this.icon,
    required this.iconColor,
    required this.message,
    this.title,
    this.action,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 20),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 460),
          child: Container(
            padding: const EdgeInsets.fromLTRB(32, 34, 32, 34),
            decoration: adminCardDecoration(
              borderColor: iconColor.withOpacity(0.3),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  padding: const EdgeInsets.all(18),
                  decoration: BoxDecoration(
                    color: iconColor.withOpacity(0.14),
                    shape: BoxShape.circle,
                    border: Border.all(color: iconColor.withOpacity(0.3)),
                    boxShadow: [
                      BoxShadow(
                        color: iconColor.withOpacity(0.3),
                        blurRadius: 22,
                        spreadRadius: 1,
                      ),
                    ],
                  ),
                  child: Icon(icon, size: 30, color: iconColor),
                ),
                const SizedBox(height: 20),
                Text(
                  title ?? 'Nothing here yet',
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                    letterSpacing: -0.2,
                  ),
                ),
                const SizedBox(height: 9),
                Text(
                  message,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.6),
                    fontSize: 13,
                    height: 1.55,
                  ),
                ),
                if (action != null) ...[
                  const SizedBox(height: 20),
                  action!,
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class AdminErrorView extends StatelessWidget {
  final String message;
  final Future<void> Function() onRetry;

  const AdminErrorView({super.key, required this.message, required this.onRetry});

  @override
  Widget build(BuildContext context) {
    return AdminStateCard(
      icon: Icons.error_outline_rounded,
      iconColor: AdminColors.danger,
      title: 'Something went wrong',
      message: message,
      action: ElevatedButton.icon(
        onPressed: onRetry,
        icon: const Icon(Icons.refresh_rounded, size: 16),
        label: const Tr('Retry'),
      ),
    );
  }
}

InputDecoration adminFieldDecoration({
  required String label,
  String? hint,
  IconData? prefixIcon,
  Widget? suffixIcon,
}) {
  const radius = 14.0;
  return InputDecoration(
    labelText: label,
    hintText: hint,
    filled: true,
    fillColor: AdminColors.inputFill,
    prefixIcon: prefixIcon == null ? null : Icon(prefixIcon, size: 20, color: AdminColors.accent.withOpacity(0.9)),
    suffixIcon: suffixIcon,
    labelStyle: TextStyle(color: Colors.white.withOpacity(0.68), fontSize: 13.5),
    floatingLabelStyle: const TextStyle(color: AdminColors.accent, fontWeight: FontWeight.w600),
    hintStyle: TextStyle(color: Colors.white.withOpacity(0.32)),
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(radius),
      borderSide: const BorderSide(color: AdminColors.border),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(radius),
      borderSide: const BorderSide(color: AdminColors.borderStrong),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(radius),
      borderSide: const BorderSide(color: AdminColors.accent, width: 1.6),
    ),
    disabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(radius),
      borderSide: BorderSide(color: AdminColors.border.withOpacity(0.5)),
    ),
    errorBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(radius),
      borderSide: const BorderSide(color: AdminColors.danger),
    ),
    focusedErrorBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(radius),
      borderSide: const BorderSide(color: AdminColors.danger, width: 1.6),
    ),
  );
}

Future<void> showAdminBottomSheet({
  required BuildContext context,
  required String title,
  required Widget child,
  String? subtitle,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (context) {
      return Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
        child: Container(
          margin: const EdgeInsets.fromLTRB(12, 0, 12, 12),
          decoration: BoxDecoration(
            color: AdminColors.surface,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: AdminColors.borderStrong),
            boxShadow: adminCardGlow(opacity: 0.22),
          ),
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(22, 12, 22, 22),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Center(
                  child: Container(
                    width: 42,
                    height: 4,
                    margin: const EdgeInsets.only(bottom: 16),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.22),
                      borderRadius: BorderRadius.circular(99),
                    ),
                  ),
                ),
                Row(
                  children: [
                    const AdminIconBadge(icon: Icons.edit_note_rounded, size: 22),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            title,
                            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Colors.white),
                          ),
                          if (subtitle != null) ...[
                            const SizedBox(height: 4),
                            Text(subtitle, style: TextStyle(color: Colors.white.withOpacity(0.6), fontSize: 13)),
                          ],
                        ],
                      ),
                    ),
                    IconButton(
                      onPressed: () => Navigator.pop(context),
                      icon: Icon(Icons.close_rounded, color: Colors.white.withOpacity(0.7)),
                    ),
                  ],
                ),
                const SizedBox(height: 18),
                child,
              ],
            ),
          ),
        ),
      );
    },
  );
}

void showAdminSnackBar(BuildContext context, String message, {bool isError = false}) {
  final accent = isError ? AdminColors.danger : AdminColors.success;
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Row(
        children: [
          Icon(
            isError ? Icons.error_outline_rounded : Icons.check_circle_rounded,
            color: accent,
            size: 20,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              message,
              style: const TextStyle(
                color: Colors.white,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ],
      ),
      backgroundColor: AdminColors.card,
      behavior: SnackBarBehavior.floating,
      elevation: 8,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(adminTileRadius),
        side: BorderSide(color: accent.withOpacity(0.45)),
      ),
    ),
  );
}

Future<void> showSupervisorCredentialsDialog({
  required BuildContext context,
  required String name,
  required String email,
  required String temporaryPassword,
  required Future<void> Function() onSendEmail,
}) {
  return showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (dialogContext) {
      var sending = false;
      return StatefulBuilder(
        builder: (context, setDialogState) {
          return AlertDialog(
            backgroundColor: AdminColors.surface,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(20),
              side: const BorderSide(color: AdminColors.borderStrong),
            ),
            title: const Row(
              children: [
                Icon(Icons.check_circle_rounded, color: AdminColors.success),
                SizedBox(width: 10),
                Tr('Supervisor Added!'),
              ],
            ),
            content: SizedBox(
              width: 420,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Name:  $name', style: const TextStyle(color: Colors.white)),
                  const SizedBox(height: 6),
                  Text('Email: $email', style: const TextStyle(color: Colors.white)),
                  const SizedBox(height: 18),
                  Tr('Temporary Password:', style: TextStyle(color: Colors.white.withOpacity(0.7))),
                  const SizedBox(height: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                    decoration: BoxDecoration(
                      color: AdminColors.inputFill,
                      borderRadius: BorderRadius.circular(adminTileRadius),
                      border: Border.all(color: AdminColors.borderStrong),
                    ),
                    child: Row(
                      children: [
                        Expanded(
                          child: SelectableText(
                            temporaryPassword,
                            style: const TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 16,
                              fontWeight: FontWeight.w700,
                              color: Colors.white,
                            ),
                          ),
                        ),
                        IconButton(
                          tooltip: 'Copy password',
                          onPressed: () async {
                            await Clipboard.setData(ClipboardData(text: temporaryPassword));
                            if (context.mounted) {
                              showAdminSnackBar(context, 'Password copied to clipboard.');
                            }
                          },
                          icon: const Icon(Icons.copy_rounded, size: 20),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  Tr('Share this password with the supervisor. The password is also sent by email to that supervisor. They will be asked to change it on first login.',
                    style: TextStyle(color: Colors.white.withOpacity(0.7), height: 1.4),
                  ),
                ],
              ),
            ),
            actions: [
              TextButton(
                onPressed: sending ? null : () => Navigator.pop(dialogContext),
                child: const Tr('Close'),
              ),
                      ElevatedButton.icon(
                onPressed: sending
                    ? null
                    : () async {
                        setDialogState(() => sending = true);
                        try {
                          await onSendEmail();
                          if (!dialogContext.mounted) return;
                          Navigator.pop(dialogContext);
                          if (context.mounted) {
                            showAdminSnackBar(context, 'Credentials email sent.');
                          }
                        } catch (e) {
                          if (context.mounted) {
                            showAdminSnackBar(context, e.toString(), isError: true);
                          }
                          if (context.mounted) setDialogState(() => sending = false);
                        }
                      },
                icon: sending
                    ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2))
                    : const Icon(Icons.email_outlined),
                label: Text(sending ? 'Sending...' : 'Send Email'),
              ),
            ],
          );
        },
      );
    },
  );
}

Widget adminResponsiveGrid({
  required int itemCount,
  required Widget Function(BuildContext context, int index) itemBuilder,
}) {
  return LayoutBuilder(
    builder: (context, constraints) {
      final width = constraints.maxWidth;
      final columns = width >= 1200
          ? 4
          : width >= 900
              ? 3
              : width >= 620
                  ? 2
                  : 1;
      // Mobile: fixed row height so padding + icon + value + title fit.
      // Wide layouts: aspect ratio keeps cards squat in multi-column grids.
      final useFixedExtent = width < 620;
      return GridView.builder(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: columns.clamp(1, 4),
          crossAxisSpacing: width < 620 ? 10 : 18,
          mainAxisSpacing: width < 620 ? 10 : 18,
          mainAxisExtent: useFixedExtent ? 132 : null,
          childAspectRatio: useFixedExtent ? 1 : (columns == 1 ? 2.8 : 1.45),
        ),
        itemCount: itemCount,
        itemBuilder: itemBuilder,
      );
    },
  );
}
