[app]
title           = Pocket Option Bot
package.name    = pocketoptionbot
package.domain  = org.bottrader
source.dir      = .
source.include_exts = py,png,jpg,kv,atlas,json
version         = 1.0

requirements    = python3,kivy==2.3.0,requests,android

orientation     = portrait
fullscreen       = 0

android.permissions = INTERNET, ACCESS_NETWORK_STATE, WAKE_LOCK
android.api         = 33
android.minapi      = 26
android.ndk         = 25b
android.sdk         = 33
android.archs       = arm64-v8a

# WebView مدمج في Android — لا حاجة لحزمة خارجية
android.enable_androidx = True
android.add_compile_options = "sourceCompatibility = JavaVersion.VERSION_11"

# منع النوم أثناء التداول
android.wakelock = True

[buildozer]
log_level = 2
warn_on_root = 1
