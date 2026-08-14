// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "MacOSHostConfirmationHelper",
    platforms: [.macOS(.v13)],
    products: [.executable(name: "macos-host-confirmation", targets: ["ConfirmationHelper"])],
    targets: [.executableTarget(name: "ConfirmationHelper", path: "Sources")]
)
