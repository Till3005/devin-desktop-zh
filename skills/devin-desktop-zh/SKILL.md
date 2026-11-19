---
name: devin-desktop-zh
description: Localize Devin Desktop to Chinese (zh-CN / zh-TW / zh-HK / zh-MO) by applying the devin-desktop-zh language pack on the machine where the app is installed.
---

# Devin Desktop Chinese localization

Applies the full Chinese language pack (91k+ strings, 4 regional packs, purely
additive — English and other languages are untouched) to the Devin Desktop app
installed on this machine.

## Steps

1. Fetch the language pack (shallow clone is enough):

   ```bash
   git clone --depth 1 https://github.com/Till3005/devin-desktop-zh.git /tmp/devin-desktop-zh
   ```

   If `/tmp/devin-desktop-zh` already exists, `git -C /tmp/devin-desktop-zh pull --ff-only` instead.

2. Apply — pick the script matching this machine's OS:

   - macOS / Linux: `bash /tmp/devin-desktop-zh/install.sh`
   - Windows (Git Bash or PowerShell): `powershell -ExecutionPolicy Bypass -File /tmp/devin-desktop-zh/install.ps1`

   The script auto-detects the Devin install directory; if it fails, locate the
   app's `resources/app` directory and pass it with `--app <path>`.

3. Verify: run `python3 /tmp/devin-desktop-zh/src/patch_app.py status --app <resources/app dir>` —
   expect `patched` plus `zh locales registered` for devin-webapp-host.

4. Tell the user to restart Devin Desktop, then open the command palette →
   "Configure Display Language" and pick 简体中文 / 繁體中文(台灣) / 繁體中文(香港) / 繁體中文(澳門).

## Notes

- Idempotent and additive: re-running after an OTA update re-applies cleanly.
- Undo: `bash /tmp/devin-desktop-zh/install.sh restore` removes the patch while
  keeping the language packs installed (switch back to English in settings).
- Requires a locally installed Devin Desktop; does nothing in headless CI.
