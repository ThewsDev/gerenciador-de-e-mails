[app]
title = Gerenciador de E-mails
package.name = emailmanager
package.domain = org.emailmanager
source.dir = .
source.include_exts = py,png,jpg,svg,kv,json,ttf
source.exclude_dirs = .buildozer,bin,venv,data,tests,__pycache__
version = 1.0.0

# sqlite3 e openssl são receitas do python-for-android; requests+certifi cuidam do TLS.
requirements = python3,kivy,pyjnius,android,sqlite3,openssl,requests,certifi,urllib3,idna,charset-normalizer
p4a.branch = v2024.01.21

orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/assets/images/icon.png

# Somente INTERNET: leitura de e-mail via API não exige outras permissões.
android.permissions = INTERNET
android.api = 34
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = False

# Google Identity Services: autorização nativa para APIs Google.
android.gradle_dependencies = com.google.android.gms:play-services-auth:22.0.0
android.enable_androidx = True
android.add_compile_options = "sourceCompatibility = 1.8", "targetCompatibility = 1.8"

[buildozer]
log_level = 2
warn_on_root = 1
