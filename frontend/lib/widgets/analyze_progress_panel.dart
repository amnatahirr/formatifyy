import 'dart:async';

import 'package:flutter/material.dart';

import 'tr.dart';
/// Named stages shown while document analysis is in flight.
class AnalyzeProgressStage {
  final String title;
  final String subtitle;

  const AnalyzeProgressStage({
    required this.title,
    required this.subtitle,
  });
}

const List<AnalyzeProgressStage> kAnalyzeProgressStages = [
  AnalyzeProgressStage(
    title: 'Reading document',
    subtitle: 'Loading your file…',
  ),
  AnalyzeProgressStage(
    title: 'Sifting through content',
    subtitle: 'Scanning text and layout…',
  ),
  AnalyzeProgressStage(
    title: 'Mulling over structure',
    subtitle: 'Detecting headings and sections…',
  ),
  AnalyzeProgressStage(
    title: 'Extracting key details',
    subtitle: 'Pulling out required fields…',
  ),
  AnalyzeProgressStage(
    title: 'Applying formatting',
    subtitle: 'Reformatting against the template…',
  ),
  AnalyzeProgressStage(
    title: 'Finalizing',
    subtitle: 'Preparing your analysis report…',
  ),
];

/// Self-contained staged progress UI for the Analyze screen loading state.
///
/// Advances through [kAnalyzeProgressStages] on a timer while analysis runs.
/// Caps before the last stage until [isComplete] is true, then finishes.
class AnalyzeProgressPanel extends StatefulWidget {
  final String documentName;
  final Color accent;
  final Color textPrimary;
  final Color textSecondary;
  final Color surface;
  final Color border;
  final Color track;

  /// When true, jumps to the final stage and fills the bar (briefly before
  /// the parent swaps to results).
  final bool isComplete;

  const AnalyzeProgressPanel({
    super.key,
    required this.documentName,
    required this.accent,
    required this.textPrimary,
    required this.textSecondary,
    required this.surface,
    required this.border,
    required this.track,
    this.isComplete = false,
  });

  @override
  State<AnalyzeProgressPanel> createState() => _AnalyzeProgressPanelState();
}

class _AnalyzeProgressPanelState extends State<AnalyzeProgressPanel> {
  static const int _maxActiveBeforeComplete =
      4; // "Applying formatting" — hold until done

  Timer? _timer;
  int _step = 0;
  double _intra = 0.0;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: 700), _onTick);
  }

  @override
  void didUpdateWidget(covariant AnalyzeProgressPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.isComplete && !oldWidget.isComplete) {
      setState(() {
        _step = kAnalyzeProgressStages.length - 1;
        _intra = 1.0;
      });
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _onTick(Timer timer) {
    if (!mounted || widget.isComplete) return;
    setState(() {
      // Hold on second-to-last stage until the request finishes.
      if (_step < _maxActiveBeforeComplete) {
        _intra += 0.22;
        if (_intra >= 1.0) {
          _intra = 0.0;
          _step += 1;
        }
      } else {
        // Soft pulse while waiting on the network / backend.
        _intra = (_intra + 0.04).clamp(0.0, 0.92);
      }
    });
  }

  double get _barValue {
    final n = kAnalyzeProgressStages.length;
    if (widget.isComplete) return 1.0;
    return ((_step + _intra) / n).clamp(0.02, 0.96);
  }

  @override
  Widget build(BuildContext context) {
    final stages = kAnalyzeProgressStages;
    final current = stages[_step.clamp(0, stages.length - 1)];

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 440),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Tr('Analyzing',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: widget.textPrimary,
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.3,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                widget.documentName,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: widget.textSecondary,
                  fontSize: 13,
                ),
              ),
              const SizedBox(height: 28),
              ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: LinearProgressIndicator(
                  value: _barValue,
                  minHeight: 8,
                  backgroundColor: widget.track,
                  valueColor: AlwaysStoppedAnimation<Color>(widget.accent),
                ),
              ),
              const SizedBox(height: 10),
              Text(
                '${(_barValue * 100).round()}%',
                textAlign: TextAlign.right,
                style: TextStyle(
                  color: widget.textSecondary,
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 20),
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 280),
                switchInCurve: Curves.easeOut,
                switchOutCurve: Curves.easeIn,
                child: Column(
                  key: ValueKey<int>(_step),
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      current.title,
                      style: TextStyle(
                        color: widget.accent,
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      current.subtitle,
                      style: TextStyle(
                        color: widget.textSecondary,
                        fontSize: 13,
                        height: 1.35,
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 28),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 12,
                ),
                decoration: BoxDecoration(
                  color: widget.surface,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: widget.border),
                ),
                child: Column(
                  children: [
                    for (var i = 0; i < stages.length; i++) ...[
                      if (i > 0) const SizedBox(height: 8),
                      _StageRow(
                        label: stages[i].title,
                        state: i < _step
                            ? _StageState.done
                            : i == _step
                                ? _StageState.active
                                : _StageState.pending,
                        accent: widget.accent,
                        textPrimary: widget.textPrimary,
                        textSecondary: widget.textSecondary,
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

enum _StageState { pending, active, done }

class _StageRow extends StatelessWidget {
  final String label;
  final _StageState state;
  final Color accent;
  final Color textPrimary;
  final Color textSecondary;

  const _StageRow({
    required this.label,
    required this.state,
    required this.accent,
    required this.textPrimary,
    required this.textSecondary,
  });

  @override
  Widget build(BuildContext context) {
    final Color iconColor;
    final IconData icon;
    final Color labelColor;
    switch (state) {
      case _StageState.done:
        icon = Icons.check_circle_rounded;
        iconColor = accent;
        labelColor = textPrimary.withOpacity(0.75);
        break;
      case _StageState.active:
        icon = Icons.radio_button_checked;
        iconColor = accent;
        labelColor = textPrimary;
        break;
      case _StageState.pending:
        icon = Icons.circle_outlined;
        iconColor = textSecondary.withOpacity(0.45);
        labelColor = textSecondary.withOpacity(0.7);
        break;
    }

    return Row(
      children: [
        Icon(icon, size: 18, color: iconColor),
        const SizedBox(width: 10),
        Expanded(
          child: Text(
            label,
            style: TextStyle(
              color: labelColor,
              fontSize: 13,
              fontWeight:
                  state == _StageState.active ? FontWeight.w600 : FontWeight.w400,
            ),
          ),
        ),
        if (state == _StageState.active)
          SizedBox(
            width: 14,
            height: 14,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: accent,
            ),
          ),
      ],
    );
  }
}
