import SwiftUI
import AppKit

struct AddInstallationView: View {
    @ObservedObject var manager: InstallationManager
    @Environment(\.dismiss) private var dismiss

    @State private var name        = ""
    @State private var abletonPath = ""
    @State private var logPath     = ""
    @State private var clientId    = InstallationManager.defaultClientId
    @State private var isInstalling = false
    @State private var errorMessage: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("Add Ableton Installation")
                .font(.title2.bold())
                .padding(.bottom, 4)

            fieldRow("Installation Name", binding: $name,
                     placeholder: "e.g. Ableton Live 12 Suite")

            filePickerRow("Ableton Live Application", path: $abletonPath,
                          prompt: "Select .app bundle") {
                pickApp()
            }

            savePickerRow("Log File Location", path: $logPath,
                          prompt: "Choose log file location") {
                pickSaveLocation()
            }

            fieldRow("Discord Client ID (optional)", binding: $clientId,
                     placeholder: InstallationManager.defaultClientId)

            if let error = errorMessage {
                Text(error)
                    .foregroundColor(.red)
                    .font(.caption)
            }

            HStack {
                Button("Cancel") { dismiss() }
                    .keyboardShortcut(.escape)
                Spacer()
                Button {
                    addInstallation()
                } label: {
                    if isInstalling {
                        HStack {
                            ProgressView().scaleEffect(0.7)
                            Text("Installing…")
                        }
                    } else {
                        Text("Add Installation")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(name.isEmpty || abletonPath.isEmpty || logPath.isEmpty || isInstalling)
                .keyboardShortcut(.return)
            }
        }
        .padding(24)
        .frame(width: 500)
    }

    // MARK: - Field helpers

    @ViewBuilder
    private func fieldRow(_ label: String, binding: Binding<String>, placeholder: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(.headline)
            TextField(placeholder, text: binding)
                .textFieldStyle(.roundedBorder)
        }
    }

    @ViewBuilder
    private func filePickerRow(_ label: String, path: Binding<String>,
                               prompt: String, action: @escaping () -> Void) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(.headline)
            HStack {
                TextField(prompt, text: path)
                    .textFieldStyle(.roundedBorder)
                Button("Choose…", action: action)
            }
        }
    }

    @ViewBuilder
    private func savePickerRow(_ label: String, path: Binding<String>,
                               prompt: String, action: @escaping () -> Void) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label).font(.headline)
            HStack {
                TextField(prompt, text: path)
                    .textFieldStyle(.roundedBorder)
                Button("Choose…", action: action)
            }
        }
    }

    // MARK: - Native file pickers

    private func pickApp() {
        let panel = NSOpenPanel()
        panel.title = "Select Ableton Live .app bundle"
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.directoryURL = URL(fileURLWithPath: "/Applications")
        panel.allowedContentTypes = [.applicationBundle]
        if panel.runModal() == .OK, let url = panel.url {
            abletonPath = url.path
            if name.isEmpty {
                name = url.deletingPathExtension().lastPathComponent
            }
        }
    }

    private func pickSaveLocation() {
        let panel = NSSavePanel()
        panel.title = "Choose Log File Location"
        panel.nameFieldStringValue = "CurrentProjectLog.txt"
        panel.canCreateDirectories = true
        if panel.runModal() == .OK, let url = panel.url {
            logPath = url.path
        }
    }

    // MARK: - Add action

    private func addInstallation() {
        guard !name.isEmpty, !abletonPath.isEmpty, !logPath.isEmpty else { return }
        isInstalling = true
        errorMessage = nil

        let install = manager.add(
            name: name,
            abletonPath: abletonPath,
            logPath: logPath,
            clientId: clientId.isEmpty ? InstallationManager.defaultClientId : clientId
        )

        DispatchQueue.global(qos: .userInitiated).async {
            let success = manager.installFauxMIDI(install)
            DispatchQueue.main.async {
                isInstalling = false
                if success {
                    dismiss()
                } else {
                    errorMessage = "FauxMIDI installation failed — check that Ableton path is correct."
                }
            }
        }
    }
}
