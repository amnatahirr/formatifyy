import argostranslate.package as pkg

pkg.update_package_index()
available = pkg.get_available_packages()

for code in ["ur", "ar", "hi", "fr", "es"]:
    match = [p for p in available if p.from_code == "en" and p.to_code == code]
    if match:
        pkg.install_from_path(match[0].download())
        print("installed:", code)
    else:
        print("NOT available:", code)