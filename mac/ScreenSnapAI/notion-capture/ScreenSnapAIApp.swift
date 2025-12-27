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
