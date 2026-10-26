import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/lang_provider.dart';

class Tr extends StatelessWidget {
  final String data;
  final TextStyle? style;
  final TextAlign? textAlign;
  final int? maxLines;
  final TextOverflow? overflow;
  final bool? softWrap;

  const Tr(this.data,
      {super.key, this.style, this.textAlign, this.maxLines, this.overflow, this.softWrap});

  @override
  Widget build(BuildContext context) {
    final lang = context.watch<LangProvider>();
    return Text(
      lang.t(data),
      style: style,
      textAlign: textAlign,
      maxLines: maxLines,
      overflow: overflow,
      softWrap: softWrap,
    );
  }
}