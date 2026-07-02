#!/bin/bash

# Get Flutter dependencies
flutter pub get

# Enable desktop support (if not already enabled)
flutter config --enable-windows-desktop
flutter config --enable-macos-desktop
flutter config --enable-linux-desktop

# Run the app
flutter run -d windows  # or -d macos or -d linux
