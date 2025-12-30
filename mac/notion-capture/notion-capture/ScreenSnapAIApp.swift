//
//  ScreenSnapAIApp.swift
//  ScreenSnapAI
//
//  Created by Maximilian Glasmacher on 28.11.25.
//

import SwiftUI
import AppKit
import Combine

@main
struct ScreenSnapAIApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var screenshotTrigger = ScreenshotTrigger()
    @State private var window: NSWindow?
    
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(screenshotTrigger)
                .onAppear {
                    // Configure window to remove title bar space
                    configureWindow()
                }
                .background(WindowAccessor(window: $window))
                .onOpenURL { url in
                    // Handle custom URL scheme callbacks (e.g., from Google OAuth)
                    handleIncomingURL(url)
                }
                .handlesExternalEvents(preferring: Set(["notioncapture"]), allowing: Set(["notioncapture"]))
        }
        .handlesExternalEvents(matching: Set(["notioncapture", "*"]))
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentMinSize)
        .commands {
            // Remove default "Quit" from menu since we handle it in menu bar
            CommandGroup(replacing: .appTermination) {}
        }
    }
    
    private func configureWindow() {
        DispatchQueue.main.async {
            if let window = NSApplication.shared.windows.first {
                window.titlebarAppearsTransparent = true
                window.titleVisibility = .hidden
                window.styleMask.insert(.fullSizeContentView)
            }
        }
    }
    
    private func handleIncomingURL(_ url: URL) {
        print("Received URL: \(url)")
        
        guard url.scheme == "notioncapture" else { return }
        
        // Handle Google OAuth callback
        if url.host == "google-callback" {
            handleGoogleCallback(url)
        }
        // Handle Notion OAuth callback
        else if url.host == "notion-callback" {
            handleNotionCallback(url)
        }
    }
    
    private func handleGoogleCallback(_ url: URL) {
        // Parse tokens from URL query parameters
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let queryItems = components.queryItems else {
            print("Failed to parse callback URL")
            return
        }
        
        // Extract tokens JSON from query parameter
        if let tokensParam = queryItems.first(where: { $0.name == "tokens" })?.value,
           let tokensData = tokensParam.data(using: .utf8),
           let tokens = try? JSONSerialization.jsonObject(with: tokensData) as? [String: Any] {
            
            print("Received Google tokens via URL scheme")
            
            // Save tokens to credential store
            CredentialStore.shared.saveGoogleTokens(tokens)
            
            // Post notification for UI update
            NotificationCenter.default.post(name: .googleTokensReceived, object: tokens)
            
            // Bring app to front
            NSApplication.shared.activate(ignoringOtherApps: true)
            if let window = NSApplication.shared.windows.first {
                window.makeKeyAndOrderFront(nil)
            }
        } else if let errorParam = queryItems.first(where: { $0.name == "error" })?.value {
            print("Google auth error: \(errorParam)")
            NotificationCenter.default.post(name: .googleAuthError, object: errorParam)
        }
    }
    
    private func handleNotionCallback(_ url: URL) {
        // Parse tokens from URL query parameters
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let queryItems = components.queryItems else {
            print("Failed to parse Notion callback URL")
            return
        }
        
        // Extract tokens JSON from query parameter
        if let tokensParam = queryItems.first(where: { $0.name == "tokens" })?.value,
           let tokensData = tokensParam.data(using: .utf8),
           let tokens = try? JSONSerialization.jsonObject(with: tokensData) as? [String: Any] {
            
            print("Received Notion tokens via URL scheme")
            
            // Save tokens to credential store
            CredentialStore.shared.saveNotionTokens(tokens)
            
            // Post notification for UI update
            NotificationCenter.default.post(name: .notionTokensReceived, object: tokens)
            
            // Bring app to front
            NSApplication.shared.activate(ignoringOtherApps: true)
            if let window = NSApplication.shared.windows.first {
                window.makeKeyAndOrderFront(nil)
            }
        } else if let errorParam = queryItems.first(where: { $0.name == "error" })?.value {
            print("Notion auth error: \(errorParam)")
            NotificationCenter.default.post(name: .notionAuthError, object: errorParam)
        }
    }
}

// Notification names for auth
extension Notification.Name {
    static let googleTokensReceived = Notification.Name("googleTokensReceived")
    static let googleAuthError = Notification.Name("googleAuthError")
    static let notionTokensReceived = Notification.Name("notionTokensReceived")
    static let notionAuthError = Notification.Name("notionAuthError")
}

// AppDelegate to prevent app from terminating when window is closed
class AppDelegate: NSObject, NSApplicationDelegate {
    private let menuBarManager = MenuBarManager()
    
    func applicationDidFinishLaunching(_ notification: Notification) {
        // Setup menu bar and keyboard shortcuts on app launch
        // This ensures they work even when the window is closed
        menuBarManager.setup(
            screenshotAction: {
                ScreenshotManager.shared.takeScreenshot()
            },
            toggleWindowAction: { [weak self] in
                if let window = NSApplication.shared.windows.first {
                    if window.isVisible && NSApplication.shared.isActive {
                        // Window is visible and app is active - hide it
                        window.orderOut(nil)
                    } else {
                        // Window is hidden or app is not active - show it
                        NSApplication.shared.activate(ignoringOtherApps: true)
                        window.collectionBehavior = [.moveToActiveSpace, .fullScreenAuxiliary]
                        self?.menuBarManager.positionWindowBelowMenuBar(window)
                        window.makeKeyAndOrderFront(nil)
                    }
                }
            },
            quitAction: {
                NSApplication.shared.terminate(nil)
            }
        )
        
        // Setup keyboard shortcut (works globally, even when window is closed)
        KeyboardShortcutManager.shared.setup {
            ScreenshotManager.shared.takeScreenshot()
        }
    }
    
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return false // Keep app running when window is closed
    }
    
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        // When app is reopened (e.g., clicked in dock), show existing window instead of creating new one
        if !flag {
            if let window = NSApplication.shared.windows.first {
                window.makeKeyAndOrderFront(nil)
            }
        }
        return true
    }
    
    func application(_ application: NSApplication, open urls: [URL]) {
        // Handle URL scheme - close any extra windows and focus the main one
        DispatchQueue.main.async {
            // Close any duplicate windows (keep only the first one)
            let windows = NSApplication.shared.windows.filter { $0.isVisible || $0.isMiniaturized }
            if windows.count > 1 {
                for window in windows.dropFirst() {
                    window.close()
                }
            }
            
            // Focus the main window
            if let mainWindow = NSApplication.shared.windows.first {
                NSApplication.shared.activate(ignoringOtherApps: true)
                mainWindow.makeKeyAndOrderFront(nil)
            }
        }
    }
}

// Helper to access the window
struct WindowAccessor: NSViewRepresentable {
    @Binding var window: NSWindow?
    
    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        DispatchQueue.main.async {
            self.window = view.window
        }
        return view
    }
    
    func updateNSView(_ nsView: NSView, context: Context) {}
}
