# 姓名學・學生版 Preview

Public workflow repository for an isolated Android preview build.

## Security model
- The original source remains in the private repository `dsds02355023-debug/xingming-android-apps`.
- The workflow checks out the private source only at build time using a fine-grained, read-only GitHub token stored as the Actions secret `SOURCE_REPO_TOKEN`.
- No original source ZIP is committed to this public repository.
- Inline JavaScript is minified and mangled before packaging.
- The APK uses a separate preview application ID and Android debug signing.
- No production signing keys, production release workflow, or update-service credentials are used.
- APKs are published only as short-retention Actions artifacts, not official releases.

## One-time setup
Create a fine-grained personal access token with read-only Contents access to `xingming-android-apps`, then add it in this repository under Settings → Secrets and variables → Actions as `SOURCE_REPO_TOKEN`. Never paste the token into an issue, chat, source file, or workflow YAML.

Run the workflow manually from Actions → Student obfuscated preview APK → Run workflow.

Obfuscation makes casual copying and reading harder; it does not make client-side code impossible to extract or reverse engineer.
