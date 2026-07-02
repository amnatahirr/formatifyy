with open("lib/screens/analyze_screen.dart", "r") as f:
    lines = f.readlines()

# 6. Delete 7086 to 7259 (index 7085 to 7259)
del lines[7085:7259]

# 5. Fix 6388-6391 (now offset by 0 since it is before 7085)
# old:
# 6388:             shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
# 6389:           ),
# 6390:           const Spacer(),
lines[6388] = "          ),\n        ),\n"
# now lines are offset +1

# 4. Fix 5816-5825 (offset 0)
# replace 5815-5824 with:
replacement_4 = """            if (_selectedTableIndices.isNotEmpty) ...[
              const SizedBox(width: 6),
              _Tag('${_selectedTableIndices.length} selected', _purple),
            ],
          ]),
          const SizedBox(height: 16),
          ...tablesWithIssues.map((t) => _buildTableCard(t)),
        ])),

        // ── Right: sidebar ─────────────────────────────────────────────────
        _buildTablesSidebar(),
      ])),
"""
lines[5815:5825] = [replacement_4]

# 3. Delete 5777-5784 (offset 0)
del lines[5776:5784]

# 2. Fix 5615-5619 (offset 0)
lines[5614:5619] = [
"          ],\n",
"        ],\n",
"      ]),\n",
"    );\n",
"  }\n"
]

# 1. Fix 5558-5573 (offset 0)
lines[5557:5573] = [
"        SizedBox(\n",
"          width: double.infinity,\n",
"          child: ElevatedButton.icon(\n",
"            icon: const Icon(Icons.image, size: 16),\n",
"            label: const Text('Format Images'),\n",
"            onPressed: () => Navigator.push(\n",
"              context,\n",
"              MaterialPageRoute(\n",
"                builder: (_) => ImageFormatterScreen(\n",
"                  documentId:   widget.documentId,\n",
"                  documentName: widget.documentName,\n",
"                ),\n",
"              ),\n",
"            ),\n",
"          ),\n",
"        ),\n",
"      ]),\n"
]

with open("lib/screens/analyze_screen.dart", "w") as f:
    f.writelines(lines)
