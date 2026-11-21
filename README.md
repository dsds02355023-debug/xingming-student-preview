# 姓名學・學生版 Preview

Public workflow repository for an isolated Android preview build.

- Original source remains in the private repository `dsds02355023-debug/xingming-android-apps`.
- The workflow checks out private source only at build time using a fine-grained, read-only token stored as Actions secret `SOURCE_REPO_TOKEN`.
- No original source ZIP is committed here.
- Inline JavaScript is minified and mangled before packaging.
- The APK uses a separate preview application ID and Android debug signing.
- No production signing keys, production release workflow, or update-service credentials are used.
- APKs are published only as short-retention Actions artifacts, not official releases.

## One-time setup
Create a fine-grained personal access token with read-only Contents access to `xingming-android-apps`, then add it under Settings → Secrets and variables → Actions as `SOURCE_REPO_TOKEN`. Never paste the token into chat or source files.

Then run Actions → Student obfuscated preview APK → Run workflow.

Obfuscation makes casual copying and reading harder; it does not make client-side code impossible to extract or reverse engineer.
