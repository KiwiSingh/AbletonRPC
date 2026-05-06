import SwiftUI

struct ContentView: View {
    @StateObject private var manager = InstallationManager()
    @State private var showingAdd    = false
    @State private var selectedId: String?
    @State private var alertMessage  = ""
    @State private var showAlert     = false

    var body: some View {
        VStack(spacing: 0) {
            header
            Divider()
            detectedVersionsSection
            Divider()
            installationsSection
            Divider()
            toolbar
            infoFooter
        }
        .background(Color(NSColor.windowBackgroundColor))
        .sheet(isPresented: $showingAdd) {
            AddInstallationView(manager: manager)
        }
        .alert("AbletonRPC", isPresented: $showAlert) {
            Button("OK") {}
        } message: {
            Text(alertMessage)
        }
    }

    // MARK: - Header

    private var header: some View {
        VStack(spacing: 2) {
            Text("Ableton Discord RPC v3.1.0")
                .font(.system(size: 22, weight: .bold))
            Text("One More Day")
                .font(.system(size: 13))
                .foregroundColor(.accentColor)
        }
        .padding(.vertical, 14)
    }

    // MARK: - Detected versions

    private var detectedVersionsSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Label("Detected Running Ableton Versions", systemImage: "magnifyingglass")
                    .font(.headline)
                Spacer()
                Button("Refresh") { manager.objectWillChange.send() }
                    .buttonStyle(.bordered)
            }

            let running = manager.detectedRunningVersions()
            Group {
                if running.isEmpty {
                    Text("No Ableton Live instances currently running")
                        .foregroundColor(.secondary)
                } else {
                    VStack(alignment: .leading, spacing: 2) {
                        ForEach(running, id: \.self) { Text("• \($0)") }
                    }
                }
            }
            .font(.system(.body, design: .monospaced))
            .padding(8)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color(NSColor.textBackgroundColor))
            .cornerRadius(6)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
    }

    // MARK: - Installations list

    private var installationsSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("Configured Installations", systemImage: "list.bullet.rectangle")
                .font(.headline)

            Table(manager.installations, selection: $selectedId) {
                TableColumn("Name", value: \.name).width(min: 140)
                TableColumn("Version") { install in
                    Text(URL(fileURLWithPath: install.abletonPath).lastPathComponent)
                }.width(min: 160)
                TableColumn("Log Path", value: \.logPath).width(min: 200)
            }
            .frame(minHeight: 180)
            .cornerRadius(6)
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 12)
    }

    // MARK: - Toolbar

    private var toolbar: some View {
        HStack(spacing: 10) {
            Button {
                showingAdd = true
            } label: {
                Label("Add Installation", systemImage: "plus")
            }
            .buttonStyle(.borderedProminent)
            .tint(.green)

            Button { removeSelected() } label: {
                Label("Remove", systemImage: "trash")
            }
            .buttonStyle(.borderedProminent)
            .tint(.red)
            .disabled(selectedId == nil)

            Spacer()

            Button { manager.refreshHelperStatus() } label: {
                Label("Refresh", systemImage: "arrow.clockwise")
            }
            .buttonStyle(.bordered)

            HStack(spacing: 4) {
                Circle()
                    .fill(manager.helperStatus == .running ? Color.green : Color.orange)
                    .frame(width: 8, height: 8)
                Text(manager.helperStatus.label)
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
        .padding(.horizontal, 20)
        .padding(.vertical, 10)
    }

    // MARK: - Footer

    private var infoFooter: some View {
        Text(
            "💡 Each Ableton version gets its own service and log file  •  " +
            "Services run independently — no conflicts between versions  •  " +
            "Discord shows which specific Ableton version is active"
        )
        .font(.system(size: 11, design: .monospaced))
        .foregroundColor(.secondary)
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(NSColor.textBackgroundColor))
    }

    // MARK: - Actions

    private func removeSelected() {
        guard let id = selectedId,
              let install = manager.installations.first(where: { $0.id == id })
        else { return }
        manager.remove(install)
        selectedId = nil
        alertMessage = "'\(install.name)' removed.\n\nPlease restart Ableton Live to complete the uninstall."
        showAlert = true
    }
}
