// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "AgentLab",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "AgentLab",
            resources: [
                .copy("Resources/course.json"),
                .copy("Resources/lesson.js"),
                .copy("Resources/lesson.css"),
                .copy("Resources/trace.js"),
                .copy("Resources/trace.css"),
            ]
        )
    ]
)
