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
        }
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
}

// Notification names for Google auth
extension Notification.Name {
    static let googleTokensReceived = Notification.Name("googleTokensReceived")
    static let googleAuthError = Notification.Name("googleAuthError")
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
