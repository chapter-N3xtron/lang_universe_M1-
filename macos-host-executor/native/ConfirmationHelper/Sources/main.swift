import AppKit
import AppKit
import Foundation

// Fixed interface: one <=256 KiB server-produced JSON object on stdin, no
// arguments/environment authority, and exactly one JSON decision on stdout.
let input = FileHandle.standardInput.readDataToEndOfFile()
let expectedKeys: Set<String> = [
    "schema_version", "plan_digest", "request_id", "thread_id", "interrupt_id",
    "action", "expected_mutations", "privilege", "timeout_seconds",
    "output_limit_bytes", "rollback", "expiry_seconds", "created_at",
    "expires_at", "execution",
]

guard input.count > 0, input.count <= 262_144,
      let object = try? JSONSerialization.jsonObject(with: input) as? [String: Any],
      Set(object.keys) == expectedKeys,
      let version = object["schema_version"] as? Int, version == 1,
      let digest = object["plan_digest"] as? String,
      digest.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil,
      let requestID = object["request_id"] as? String,
      let threadID = object["thread_id"] as? String,
      let interruptID = object["interrupt_id"] as? String,
      let action = object["action"] as? [String: Any],
      let mutations = object["expected_mutations"] as? [[String: Any]],
      let privilege = object["privilege"] as? String, privilege == "user",
      let timeout = object["timeout_seconds"] as? Int,
      let outputLimit = object["output_limit_bytes"] as? Int,
      let rollback = object["rollback"] as? [String: Any],
      let expirySeconds = object["expiry_seconds"] as? Int,
      let created = object["created_at"] as? String,
      let expires = object["expires_at"] as? String,
      let execution = object["execution"] as? [String: Any] else {
    FileHandle.standardOutput.write(Data("{\"decision\":\"reject\",\"plan_digest\":\"invalid\"}\n".utf8))
    exit(2)
}

func pretty(_ value: Any) -> String {
    guard JSONSerialization.isValidJSONObject(value),
          let data = try? JSONSerialization.data(withJSONObject: value, options: [.prettyPrinted, .sortedKeys]),
          let text = String(data: data, encoding: .utf8) else { return "<invalid>" }
    return text
}

let details = """
Plan digest: \(digest)
Server request: \(requestID)
LangGraph thread: \(threadID)
LangGraph interrupt: \(interruptID)
Action:\n\(pretty(action))
Derived execution (not client-supplied):\n\(pretty(execution))
Expected mutations:\n\(pretty(mutations))
Privilege: \(privilege) (no sudo)
Timeout: \(timeout) seconds
Output limit: \(outputLimit) bytes
Plan expiry: \(expirySeconds) seconds
Created: \(created)
Expires: \(expires)
Rollback limits:\n\(pretty(rollback))
"""

let actionCategory = action["category"] as? String ?? "unknown"
let actionOperation = (action["operation"] as? String) ?? (action["query"] as? String)
let actionSummary = actionOperation.map { "\(actionCategory) — \($0)" } ?? actionCategory
let visibleFrame = (NSScreen.main ?? NSScreen.screens.first)?.visibleFrame
    ?? NSRect(x: 0, y: 0, width: 1024, height: 768)
let detailSize = NSSize(
    width: max(1, min(720, visibleFrame.width * 0.68)),
    height: max(1, min(420, visibleFrame.height * 0.48))
)
let scrollView = NSScrollView(frame: NSRect(origin: .zero, size: detailSize))
scrollView.borderType = .bezelBorder
scrollView.hasVerticalScroller = true
scrollView.hasHorizontalScroller = false
scrollView.autohidesScrollers = true
let textView = NSTextView(frame: NSRect(origin: .zero, size: scrollView.contentSize))
textView.string = details
textView.isEditable = false
textView.isSelectable = true
textView.drawsBackground = false
textView.font = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)
textView.textContainerInset = NSSize(width: 8, height: 8)
textView.isHorizontallyResizable = false
textView.isVerticallyResizable = true
textView.autoresizingMask = [.width]
textView.textContainer?.widthTracksTextView = true
textView.textContainer?.containerSize = NSSize(
    width: scrollView.contentSize.width,
    height: .greatestFiniteMagnitude
)
scrollView.documentView = textView

NSApplication.shared.setActivationPolicy(.accessory)
NSApplication.shared.activate(ignoringOtherApps: true)
let alert = NSAlert()
alert.alertStyle = .critical
alert.messageText = "Approve one macOS host operation?"
alert.informativeText = """
Coder is paused and waiting for your decision.
Requested: \(actionSummary)
Approve Once permits only the exact plan below. Reject or Escape runs nothing.
"""
alert.accessoryView = scrollView
let approveButton = alert.addButton(withTitle: "Approve Once")
approveButton.keyEquivalent = ""
let rejectButton = alert.addButton(withTitle: "Reject — Run Nothing")
rejectButton.keyEquivalent = "\u{1b}"
let decision = alert.runModal() == .alertFirstButtonReturn ? "approve" : "reject"
let response = ["decision": decision, "plan_digest": digest]
let output = try JSONSerialization.data(withJSONObject: response, options: [.sortedKeys])
FileHandle.standardOutput.write(output)
FileHandle.standardOutput.write(Data("\n".utf8))
exit(decision == "approve" ? 0 : 1)
