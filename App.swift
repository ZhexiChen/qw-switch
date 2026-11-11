import AppKit
import WebKit

final class SwitchApp: NSObject, NSApplicationDelegate, WKScriptMessageHandler {
    private var window: NSWindow?
    private var webView: WKWebView?
    private var gateway: Process?
    private var readyDirectory: URL?
    private var consoleURL: URL?
    private var startupTimer: Timer?

    func applicationDidFinishLaunching(_ notification: Notification) {
        startGateway()
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        window?.makeKeyAndOrderFront(nil)
        return true
    }

    func applicationWillTerminate(_ notification: Notification) {
        startupTimer?.invalidate()
        if let gateway, gateway.isRunning {
            gateway.terminate()
        }
        if let readyDirectory {
            try? FileManager.default.removeItem(at: readyDirectory)
        }
    }

    private func startGateway() {
        do {
            guard let resources = Bundle.main.resourceURL else {
                fail("应用包缺少网关文件。")
                return
            }
            let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
            try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: false,
                                                    attributes: [.posixPermissions: 0o700])
            readyDirectory = directory
            let readyFile = directory.appendingPathComponent("port")
            let process = Process()
            process.executableURL = resources.appendingPathComponent("Python/bin/python3.12")
            process.arguments = ["-E", "-s", "-B", "-u", resources.appendingPathComponent("gateway.py").path]
            var environment = ProcessInfo.processInfo.environment
            environment["QW_SWITCH_READY_FILE"] = readyFile.path
            process.environment = environment
            process.standardOutput = FileHandle.nullDevice
            process.standardError = FileHandle.nullDevice
            try process.run()
            gateway = process

            let deadline = Date().addingTimeInterval(8)
            startupTimer = Timer.scheduledTimer(withTimeInterval: 0.08, repeats: true) { [weak self] timer in
                guard let self else { timer.invalidate(); return }
                if process.isRunning, let text = try? String(contentsOf: readyFile, encoding: .utf8),
                   let port = UInt16(text), let url = URL(string: "http://127.0.0.1:\(port)/qw-switch") {
                    timer.invalidate()
                    self.showConsole(url)
                } else if !process.isRunning || Date() >= deadline {
                    timer.invalidate()
                    self.fail("网关未能启动。请检查 18747 端口是否已被占用，然后重新打开 QW Switch。")
                }
            }
        } catch {
            fail("无法启动应用内的网关。请重新安装 QW Switch。")
        }
    }

    private func showConsole(_ url: URL) {
        consoleURL = url
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        configuration.userContentController.add(self, name: "copy")
        let view = WKWebView(frame: .zero, configuration: configuration)
        webView = view
        view.load(URLRequest(url: url))
        let main = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 940, height: 780),
                            styleMask: [.titled, .closable, .miniaturizable, .resizable],
                            backing: .buffered, defer: false)
        main.title = "QW Switch"
        main.minSize = NSSize(width: 420, height: 480)
        main.isReleasedWhenClosed = false
        main.contentView = view
        main.center()
        main.makeKeyAndOrderFront(nil)
        window = main
        NSApp.activate(ignoringOtherApps: true)
    }

    private func fail(_ message: String) {
        NSApp.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.messageText = "QW Switch 启动失败"
        alert.informativeText = message
        alert.runModal()
        NSApp.terminate(nil)
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.frameInfo.isMainFrame, message.frameInfo.request.url == consoleURL,
              let text = message.body as? String else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(text, forType: .string)
    }
}

let application = NSApplication.shared
let delegate = SwitchApp()
application.setActivationPolicy(.regular)
application.delegate = delegate
let menu = NSMenu()
let appItem = NSMenuItem()
menu.addItem(appItem)
let appMenu = NSMenu()
appMenu.addItem(withTitle: "退出 QW Switch", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
appItem.submenu = appMenu
let editItem = NSMenuItem()
menu.addItem(editItem)
let edit = NSMenu(title: "编辑")
edit.addItem(withTitle: "撤销", action: Selector(("undo:")), keyEquivalent: "z")
edit.addItem(withTitle: "剪切", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
edit.addItem(withTitle: "复制", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
edit.addItem(withTitle: "粘贴", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
edit.addItem(withTitle: "全选", action: #selector(NSText.selectAll(_:)), keyEquivalent: "a")
editItem.submenu = edit
application.mainMenu = menu
application.run()
