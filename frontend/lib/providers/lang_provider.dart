import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:shared_preferences/shared_preferences.dart';

class AppLanguage {
  final String code;
  final String name;
  final bool rtl;
  const AppLanguage(this.code, this.name, {this.rtl = false});
}

const kLanguages = [
  AppLanguage('en', 'English'),
  AppLanguage('ur', 'اردو', rtl: true),
  AppLanguage('ar', 'العربية', rtl: true),
  AppLanguage('hi', 'हिन्दी'),
  AppLanguage('fr', 'Français'),
  AppLanguage('es', 'Español'),
];

class LangProvider extends ChangeNotifier {
  String code = 'en';
  Map<String, String> _map = {};

  bool get isRtl => kLanguages.firstWhere((l) => l.code == code).rtl;

  Future<void> _loadMap() async {
    if (code == 'en') {
      _map = {};
      return;
    }
    try {
      final raw = await rootBundle.loadString('assets/lang/$code.json');
      _map = (jsonDecode(raw) as Map<String, dynamic>)
          .map((k, v) => MapEntry(k, v as String));
    } catch (_) {
      _map = {};
    }
  }

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    code = p.getString('lang') ?? 'en';
    await _loadMap();
    notifyListeners();
  }

  Future<void> setLang(String c) async {
    code = c;
    final p = await SharedPreferences.getInstance();
    await p.setString('lang', c);
    await _loadMap();
    notifyListeners();
  }

  String t(String s) => code == 'en' ? s : (_map[s] ?? s);
}