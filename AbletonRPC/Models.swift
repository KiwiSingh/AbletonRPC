import Foundation
import CryptoKit

// MARK: - Installation model

struct Installation: Codable, Identifiable, Hashable {
    var id: String { installHash }

    let name: String
    let abletonPath: String
    let logPath: String
    let clientId: String
    let installHash: String

    enum CodingKeys: String, CodingKey {
        case name
        case abletonPath  = "ableton_path"
        case logPath      = "log_path"
        case clientId     = "client_id"
        case installHash  = "install_hash"
    }

    init(name: String, abletonPath: String, logPath: String, clientId: String) {
        self.name        = name
        self.abletonPath = abletonPath
        self.logPath     = logPath
        self.clientId    = clientId
        // MD5 of the ableton path, first 8 chars — matches Python logic
        self.installHash = Insecure.MD5
            .hash(data: Data(abletonPath.utf8))
            .map { String(format: "%02x", $0) }
            .joined()
            .prefix(8)
            .description
    }
}

// MARK: - Config file wrapper

struct InstallationsConfig: Codable {
    var installations: [Installation]
}
