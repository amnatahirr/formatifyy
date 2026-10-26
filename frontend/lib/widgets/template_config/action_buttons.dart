import 'package:flutter/material.dart';

import '../tr.dart';
class ActionButtons extends StatelessWidget {
  final int? selectedTemplateId;
  final bool isSaving;
  final bool canSubmit;
  final VoidCallback onCreateTemplate;
  final VoidCallback onSaveTemplate;
  final VoidCallback onClearSelection;

  const ActionButtons({
    super.key,
    required this.selectedTemplateId,
    required this.isSaving,
    required this.canSubmit,
    required this.onCreateTemplate,
    required this.onSaveTemplate,
    required this.onClearSelection,
  });

  @override
  Widget build(BuildContext context) {
    final isCreatingNew = selectedTemplateId == null;

    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        if (!isCreatingNew) ...[
          OutlinedButton(
            onPressed: onClearSelection,
            style: OutlinedButton.styleFrom(
              foregroundColor: Colors.white,
              side: const BorderSide(color: Color(0xFF2D3748)),
            ),
            child: const Tr('Clear Selection'),
          ),
          const SizedBox(width: 12),
        ],
        ElevatedButton.icon(
          onPressed: !canSubmit || isSaving
              ? null
              : (isCreatingNew ? onCreateTemplate : onSaveTemplate),
          icon: isSaving
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                  ),
                )
              : Icon(isCreatingNew ? Icons.add : Icons.save),
          label: Text(
            isSaving
                ? 'Processing...'
                : (isCreatingNew ? 'Create Template' : 'Save Changes'),
          ),
          style: ElevatedButton.styleFrom(
            backgroundColor: isCreatingNew
                ? const Color(0xFF10B981)
                : const Color(0xFF3B82F6),
            foregroundColor: Colors.white,
            disabledBackgroundColor: const Color(0xFF4A5568),
            disabledForegroundColor: Colors.white70,
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
          ),
        ),
      ],
    );
  }
}
