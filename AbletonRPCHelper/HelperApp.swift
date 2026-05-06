import SwiftUI
import Foundation

// AbletonRPCHelper — background Login Item.
// Launches one Python daemon process per configured installation,
// restarts each independently on crash.

@main
struct HelperApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate
    var body: some Scene {
        Settings { EmptyView() }
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {

    // One supervisor per installation hash
    var supervisors: [String: DaemonSupervisor] = [:]
    var configWatchTimer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.prohibited)
        startAll()
        // Poll config every 30s so newly added installations start automatically
        configWatchTimer = Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { [weak self] _ in
            self?.syncWithConfig()
        }
    }

    func applicationWillTerminate(_ notification: Notification) {
        configWatchTimer?.invalidate()
        supervisors.values.forEach { $0.stop() }
    }

    // MARK: - Config sync

    func startAll() {
        let hashes = loadInstallationHashes()
        for hash in hashes {
            if supervisors[hash] == nil {
                let sup = DaemonSupervisor(installHash: hash)
                supervisors[hash] = sup
                sup.start()
            }
        }
    }

    func syncWithConfig() {
        let hashes = Set(loadInstallationHashes())
        let running = Set(supervisors.keys)

        // Start newly added installations
        for hash in hashes.subtracting(running) {
            let sup = DaemonSupervisor(installHash: hash)
            supervisors[hash] = sup
            sup.start()
        }

        // Stop removed installations
        for hash in running.subtracting(hashes) {
            supervisors[hash]?.stop()
            supervisors.removeValue(forKey: hash)
        }
    }

    func loadInstallationHashes() -> [String] {
        let support = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        ).first!
        let configURL = support
            .appendingPathComponent("AbletonRPC")
            .appendingPathComponent("installations.json")

        guard let data = try? Data(contentsOf: configURL),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let installs = json["installations"] as? [[String: Any]]
        else { return [] }

        return installs.compactMap { $0["install_hash"] as? String }
    }
}

// MARK: - Per-installation daemon supervisor

class DaemonSupervisor {
    let installHash: String
    private var process: Process?
    private var restartWorkItem: DispatchWorkItem?
    private var stopped = false

    init(installHash: String) {
        self.installHash = installHash
    }

    func start() {
        stopped = false
        launch()
    }

    func stop() {
        stopped = true
        restartWorkItem?.cancel()
        process?.terminate()
        process = nil
    }

    private func launch() {
        guard !stopped else { return }

        let helperBundle  = Bundle.main.bundleURL
        let mainAppBundle = helperBundle
            .deletingLastPathComponent()   // AbletonRPCHelper.app
            .deletingLastPathComponent()   // LoginItems/
            .deletingLastPathComponent()   // Library/
            .deletingLastPathComponent()   // Contents/
                                           // → AbletonRPC.app

        let scriptURL = mainAppBundle
            .appendingPathComponent("Contents/Resources/ableton_rpc.py")

        guard FileManager.default.fileExists(atPath: scriptURL.path) else {
            print("⚠️  [\(installHash)] ableton_rpc.py not found — retrying in 30s")
            scheduleRestart(after: 30)
            return
        }

        let python = bestPython(mainAppBundle: mainAppBundle)
        let proc   = Process()
        proc.executableURL = URL(fileURLWithPath: python)
        proc.arguments     = [scriptURL.path, "--daemon", installHash]
        proc.environment   = daemonEnvironment()

        proc.terminationHandler = { [weak self] p in
            guard let self = self, !self.stopped else { return }
            let code = p.terminationStatus
            print("🔄 [\(self.installHash)] Daemon exited (code \(code)) — restarting in 5s")
            self.process = nil
            self.scheduleRestart(after: 5)
        }

        do {
            try proc.run()
            process = proc
            print("🚀 [\(installHash)] Daemon launched (PID \(proc.processIdentifier))")
        } catch {
            print("⚠️  [\(installHash)] Launch failed: \(error) — retrying in 10s")
            scheduleRestart(after: 10)
        }
    }

    private func scheduleRestart(after seconds: TimeInterval) {
        restartWorkItem?.cancel()
        let item = DispatchWorkItem { [weak self] in self?.launch() }
        restartWorkItem = item
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds, execute: item)
    }

    // MARK: - Helpers

    private func bestPython(mainAppBundle: URL) -> String {
        let bundled = mainAppBundle
            .appendingPathComponent("Contents/Resources/python/bin/python3")
            .path
        if FileManager.default.isExecutableFile(atPath: bundled) {
            return bundled
        }
        let candidates = [
            "/usr/local/bin/python3.14",
            "/usr/local/bin/python3",
            "/usr/bin/python3",
        ]
        return candidates.first {
            FileManager.default.isExecutableFile(atPath: $0)
        } ?? "/usr/local/bin/python3"
    }

    private func daemonEnvironment() -> [String: String] {
        var env = ProcessInfo.processInfo.environment
        env["HOME"]   = NSHomeDirectory()
        env["TMPDIR"] = NSTemporaryDirectory()
        env["PATH"]   = "/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        return env
    }
}
