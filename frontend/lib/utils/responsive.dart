import 'package:flutter/material.dart';

/// Shared compact/mobile layout threshold for Formatify.
///
/// Matches the existing login-screen check (`width < 900`) so login and the
/// student shell agree. Material's phone breakpoint is often 600, but 900 is
/// the better fit here: the desktop student chrome is a fixed 200px sidebar
/// plus dense top bar, and product scope intentionally limits phones *and*
/// narrow tablets to the four-tab mobile shell.
const double kCompactBreakpoint = 900;

/// True when [MediaQuery] width is below [kCompactBreakpoint].
bool isCompact(BuildContext context) =>
    MediaQuery.sizeOf(context).width < kCompactBreakpoint;

/// True when the layout should use the full desktop chrome (sidebar, etc.).
bool isWide(BuildContext context) => !isCompact(context);
