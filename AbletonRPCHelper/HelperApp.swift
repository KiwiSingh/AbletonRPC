import SwiftUI

// AbletonRPCHelper — runs as a Login Item via SMAppService.
// Its only job: find ableton_rpc.py in the main app bundle and keep it running.

@main
struct HelperApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var delegate

    var body: some Scene {
        // No windows — this is a background helper
        Settings { EmptyView() }
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    var daemonProcess: Process?
    var restartWorkItem: DispatchWorkItem?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.prohibited) // hide from Dock and App Switcher
        launchDaemon()
    }

    func applicationWillTerminate(_ notification: Notification) {
        restartWorkItem?.cancel()
        daemonProcess?.terminate()
    }

    // MARK: - Daemon management

    func launchDaemon() {
        // The helper lives at:
        //   AbletonRPC.app/Contents/Library/LoginItems/AbletonRPCHelper.app
        // So the main bundle is 4 dirs up.
        let helperBundle = Bundle.main.bundleURL
        let mainAppBundle = helperBundle
            .deletingLastPathComponent() // AbletonRPCHelper.app
            .deletingLastPathComponent() // LoginItems/
            .deletingLastPathComponent() // Library/
            .deletingLastPathComponent() // Contents/
                                         // → AbletonRPC.app

        let scriptURL = mainAppBundle
            .appendingPathComponent("Contents/Resources/ableton_rpc.py")

        guard FileManager.default.fileExists(atPath: scriptURL.path) else {
            print("⚠️  Could not find ableton_rpc.py at \(scriptURL.path)")
            scheduleRestart(after: 30)
            return
        }

        let python = bestPython()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: python)
        process.arguments     = [scriptURL.path, "--daemon"]
        process.environment   = daemonEnvironment()

        process.terminationHandler = { [weak self] proc in
            let code = proc.terminationStatus
            print("🔄 Daemon exited (code \(code)) — restarting in 5s")
            self?.daemonProcess = nil
            self?.scheduleRestart(after: 5)
        }

        do {
            try process.run()
            daemonProcess = process
            print("🚀 Daemon launched (PID \(process.processIdentifier))")
        } catch {
            print("⚠️  Daemon launch failed: \(error)")
            scheduleRestart(after: 10)
        }
    }

    private func scheduleRestart(after seconds: TimeInterval) {
        restartWorkItem?.cancel()
        let item = DispatchWorkItem { [weak self] in self?.launchDaemon() }
        restartWorkItem = item
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds, execute: item)
    }

    // MARK: - Helpers

    private func bestPython() -> String {
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
