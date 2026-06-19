# MyApp

iOS utility app built with Swift for the Apple App Store.

## Requirements

- Xcode 16+
- iOS 17.0+ deployment target
- Swift 6.0+
- Apple Developer account

## Project Structure

```
MyApp/
├── MyApp.xcodeproj/          # Xcode project (create with Xcode)
├── MyApp/
│   ├── App/
│   │   ├── MyAppApp.swift    # App entry point (@main)
│   │   └── ContentView.swift
│   ├── Features/             # Feature modules
│   ├── Shared/               # Shared utilities, extensions
│   │   ├── Extensions/
│   │   └── Components/
│   ├── Models/               # Data models
│   ├── Services/             # Business logic, networking
│   ├── Resources/            # Assets, fonts, localization
│   │   ├── Assets.xcassets
│   │   └── Localizable.strings
│   └── Info.plist
├── MyAppTests/               # Unit tests
├── MyAppUITests/             # UI tests
├── .github/workflows/        # CI/CD
├── ExportOptions.plist       # App Store export config
└── README.md
```

## Local Setup

1. Clone the repository
2. Open `MyApp.xcodeproj` in Xcode
3. Set your Apple Developer Team in Signing & Capabilities
4. Select a simulator or device and run (⌘R)

## Branch Strategy

- `main` — production-ready code, triggers App Store release on tag push
- `develop` — integration branch
- `feature/*` — feature branches, merge into develop

## CI/CD

- **Push to main/develop** → build + test on GitHub Actions
- **Push tag `v*.*.*`** → archive and upload to App Store Connect

## GitHub Secrets Required for Release

| Secret | Description |
|--------|-------------|
| `BUILD_CERTIFICATE_BASE64` | Distribution certificate (.p12) in base64 |
| `P12_PASSWORD` | Certificate password |
| `BUILD_PROVISION_PROFILE_BASE64` | Provisioning profile in base64 |
| `KEYCHAIN_PASSWORD` | Temporary keychain password (any string) |
| `APP_STORE_CONNECT_USERNAME` | Apple ID email |
| `APP_STORE_CONNECT_PASSWORD` | App-specific password from appleid.apple.com |

## Creating a Release

```bash
git tag v1.0.0
git push origin v1.0.0
```
