[app]

# (str) Title of your application
title = Jarvis AI Assistant

# (str) Package name
package.name = jarvis

# (str) Package domain (needed for android/ios packaging)
package.domain = com.hirunthakan432

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,json,txt,md,sqlite3

# (list) Source files to exclude (let empty to not exclude anything)
source.exclude_exts = spec

# (list) List of directory to exclude (let empty to not exclude anything)
source.exclude_dirs = tests, bin, .git, __pycache__, packaging, docs, .github, .buildozer

# (str) Application versioning (method 1)
version = 0.1.0

# (list) Application requirements
# Pin Python 3.11 – Kivy 2.3.x is not yet compatible with Python 3.14 C API changes.
# Keep the set small; desktop-only packages must stay out.
requirements = python3==3.11.10,kivy==2.3.0,plyer,pyjnius,android,openai,anthropic,requests,pypdf,Pillow

# (str) Supported orientation
orientation = portrait

#
# Android specific
#

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (string) Presplash background color
android.presplash_color = #15202B

# (list) Permissions
android.permissions = INTERNET,RECORD_AUDIO,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,VIBRATE

# (int) Target Android API
android.api = 34

# (int) Minimum API
android.minapi = 24

# (bool) Use --private data storage
android.private_storage = True

# (str) Android logcat filters
android.logcat_filters = *:S python:D

# (str) The Android archs to build for
# Start with arm64 only for faster first successful build; add armeabi-v7a later
android.archs = arm64-v8a

# (bool) enables Android auto backup feature
android.allow_backup = True

# (bool) enables AndroidX support
android.enable_androidx = True

#
# Python for android (p4a) specific
#

# Use a stable p4a branch that still defaults to Python 3.11-era recipes
p4a.branch = master

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug)
log_level = 2

# (int) Display warning if buildozer is run as root
warn_on_root = 0
