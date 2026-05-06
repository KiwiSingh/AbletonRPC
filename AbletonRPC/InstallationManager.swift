import Foundation
import AppKit

class InstallationManager: ObservableObject {
    @Published var installations: [Installation] = []
    @Published var helperStatus: HelperStatus = .unknown

    static let defaultClientId = "1283406074824753203"
    static let launchAgentLabel = "com.kiwi.AbletonRPC.Helper"

    enum HelperStatus {
        case running, stopped, unknown
        var label: String {
            switch self {
            case .running: return "Helper Running"
            case .stopped: return "Helper Stopped"
            case .unknown: return "Helper Unknown"
            }
        }
        var color: String {
            switch self {
            case .running: return "green"
            case .stopped: return "orange"
            case .unknown: return "gray"
            }
        }
    }

    // MARK: - Paths

    static var configURL: URL {
        let support = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        ).first!
        return support
            .appendingPathComponent("AbletonRPC", isDirectory: true)
            .appendingPathComponent("installations.json")
    }

    static var daemonScriptURL: URL? {
        Bundle.main.url(forResource: "ableton_rpc", withExtension: "py")
    }

    // The Swift helper binary embedded inside the main app bundle
    static var helperBinaryURL: URL {
        Bundle.main.bundleURL
            .appendingPathComponent("Contents/Library/LoginItems/AbletonRPCHelper.app/Contents/MacOS/AbletonRPCHelper")
    }

    static var launchAgentPlistURL: URL {
        let launchAgents = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/LaunchAgents")
        return launchAgents.appendingPathComponent("\(launchAgentLabel).plist")
    }

    static var pythonPath: String {
        // Prefer the Python bundled inside our app bundle
        if let bundled = Bundle.main.url(forResource: "python/bin/python3", withExtension: nil),
           FileManager.default.isExecutableFile(atPath: bundled.path) {
            return bundled.path
        }
        let candidates = [
            "/usr/local/bin/python3.14",
            "/usr/local/bin/python3",
            "/usr/bin/python3",
        ]
        return candidates.first { FileManager.default.isExecutableFile(atPath: $0) }
            ?? "/usr/local/bin/python3"
    }

    // MARK: - Init

    init() {
        load()
        refreshHelperStatus()
    }

    // MARK: - Persistence

    func load() {
        guard FileManager.default.fileExists(atPath: Self.configURL.path) else { return }
        do {
            let data   = try Data(contentsOf: Self.configURL)
            let config = try JSONDecoder().decode(InstallationsConfig.self, from: data)
            installations = config.installations
        } catch {
            print("⚠️  Could not load installations: \(error)")
        }
    }

    func save() {
        do {
            let dir = Self.configURL.deletingLastPathComponent()
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            let data = try JSONEncoder().encode(InstallationsConfig(installations: installations))
            try data.write(to: Self.configURL, options: .atomic)
        } catch {
            print("⚠️  Could not save installations: \(error)")
        }
    }

    // MARK: - CRUD

    func add(name: String, abletonPath: String, logPath: String,
             clientId: String = InstallationManager.defaultClientId) -> Installation {
        let install = Installation(name: name, abletonPath: abletonPath,
                                   logPath: logPath, clientId: clientId)
        installations.append(install)
        save()
        installLaunchAgent()  // ensure helper is registered whenever an installation is added
        return install
    }

    func remove(_ installation: Installation) {
        removeFauxMIDI(installation)
        installations.removeAll { $0.id == installation.id }
        save()
        if installations.isEmpty {
            uninstallLaunchAgent()
        }
    }

    // MARK: - LaunchAgent (points at Swift helper, not Python directly)

    func installLaunchAgent() {
        let helperPath = Self.helperBinaryURL.path
        guard FileManager.default.fileExists(atPath: helperPath) else {
            print("⚠️  Helper binary not found at \(helperPath)")
            return
        }

        let plist: [String: Any] = [
            "Label": Self.launchAgentLabel,
            "ProgramArguments": [helperPath],
            "EnvironmentVariables": [
                "HOME":   NSHomeDirectory(),
                "TMPDIR": NSTemporaryDirectory(),
                "PATH":   "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            ],
            "RunAtLoad": true,
            "KeepAlive": true,
            "ThrottleInterval": 10,
            "LimitLoadToSessionType": "Aqua",
            "StandardOutPath": configDir().appendingPathComponent("helper.log").path,
            "StandardErrorPath": configDir().appendingPathComponent("helper.error").path,
        ]

        do {
            let dir = Self.launchAgentPlistURL.deletingLastPathComponent()
            try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
            let data = try PropertyListSerialization.data(
                fromPropertyList: plist, format: .xml, options: 0)
            try data.write(to: Self.launchAgentPlistURL, options: .atomic)
            print("✅ LaunchAgent plist written")
            bootstrapLaunchAgent()
        } catch {
            print("⚠️  Could not write LaunchAgent plist: \(error)")
        }
    }

    func uninstallLaunchAgent() {
        bootoutLaunchAgent()
        try? FileManager.default.removeItem(at: Self.launchAgentPlistURL)
        print("✅ LaunchAgent removed")
    }

    private func bootstrapLaunchAgent() {
        let uid = getuid()
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        task.arguments = ["bootstrap", "gui/\(uid)", Self.launchAgentPlistURL.path]
        try? task.run()
        task.waitUntilExit()
        DispatchQueue.main.asyncAfter(deadline: .now() + 1) { self.refreshHelperStatus() }
    }

    private func bootoutLaunchAgent() {
        let uid = getuid()
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        task.arguments = ["bootout", "gui/\(uid)", Self.launchAgentPlistURL.path]
        try? task.run()
        task.waitUntilExit()
    }

    func refreshHelperStatus() {
        let task = Process()
        let pipe = Pipe()
        task.executableURL = URL(fileURLWithPath: "/bin/launchctl")
        task.arguments = ["list", Self.launchAgentLabel]
        task.standardOutput = pipe
        task.standardError = Pipe()
        do {
            try task.run()
            task.waitUntilExit()
            helperStatus = task.terminationStatus == 0 ? .running : .stopped
        } catch {
            helperStatus = .unknown
        }
    }

    // MARK: - FauxMIDI

    @discardableResult
    func installFauxMIDI(_ installation: Installation) -> Bool {
        runPython(args: ["--install", installation.installHash]) == 0
    }

    func removeFauxMIDI(_ installation: Installation) {
        runPython(args: ["--remove", installation.installHash])
    }

    @discardableResult
    private func runPython(args: [String]) -> Int32 {
        guard let script = Self.daemonScriptURL else {
            print("⚠️  Could not find ableton_rpc.py in bundle")
            return 1
        }
        let task = Process()
        task.executableURL = URL(fileURLWithPath: Self.pythonPath)
        task.arguments     = [script.path] + args
        task.environment   = Self.daemonEnvironment()
        do {
            try task.run()
            task.waitUntilExit()
            return task.terminationStatus
        } catch {
            print("⚠️  Python call failed: \(error)")
            return 1
        }
    }

    // MARK: - Detected running Ableton versions

    func detectedRunningVersions() -> [String] {
        NSWorkspace.shared.runningApplications.compactMap { app in
            guard let name = app.localizedName,
                  (name == "Live" || name.contains("Ableton")),
                  let url = app.bundleURL
            else { return nil }
            return "\(name) — \(url.path)"
        }
    }

    // MARK: - Helpers

    private func configDir() -> URL {
        let support = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        ).first!
        let dir = support.appendingPathComponent("AbletonRPC")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    static func daemonEnvironment() -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        env["HOME"]   = NSHomeDirectory()
        env["TMPDIR"] = NSTemporaryDirectory()
        env["PATH"]   = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        return env
    }
}
