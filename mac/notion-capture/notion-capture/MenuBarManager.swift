//
//  MenuBarManager.swift
//  ScreenSnapAI
//
//  Created by Maximilian Glasmacher on 28.11.25.
//

import SwiftUI
import AppKit

class MenuBarManager {
    private var statusItem: NSStatusItem?
    private var screenshotAction: (() -> Void)?
    private var toggleWindowAction: (() -> Void)?
    
    func setup(screenshotAction: @escaping () -> Void, toggleWindowAction: @escaping () -> Void, quitAction: @escaping () -> Void) {
        self.screenshotAction = screenshotAction
        self.toggleWindowAction = toggleWindowAction
        
        // Create status bar item
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        
        // Set up the status bar button - clicking opens the app (no menu)
        if let button = statusItem?.button {
            // Set icon - using camera icon
            button.image = NSImage(systemSymbolName: "camera.fill", accessibilityDescription: "ScreenSnapAI")
            button.image?.isTemplate = true
            
            // Set click action to open the app window
            button.action = #selector(statusBarButtonClicked)
            button.target = self
            
            // Enable right-click for context menu
            button.sendAction(on: [.leftMouseUp, .rightMouseUp])
        }
    }
    
    @objc private func statusBarButtonClicked(_ sender: NSStatusBarButton) {
        guard let event = NSApp.currentEvent else {
            toggleWindowAction?()
            return
        }
        
        if event.type == .rightMouseUp {
            // Right-click: show context menu
            showContextMenu()
        } else {
            // Left-click: toggle the app window
            toggleWindowAction?()
        }
    }
    
    private func showContextMenu() {
        let menu = NSMenu()
        
        // Take Screenshot menu item
        let screenshotMenuItem = NSMenuItem(title: "Take Screenshot", action: #selector(takeScreenshotClicked), keyEquivalent: "")
        screenshotMenuItem.target = self
        menu.addItem(screenshotMenuItem)
        
        menu.addItem(NSMenuItem.separator())
        
        // Quit menu item
        let quitMenuItem = NSMenuItem(title: "Quit", action: #selector(quitClicked), keyEquivalent: "q")
        quitMenuItem.target = self
        menu.addItem(quitMenuItem)
        
        // Show the menu
        statusItem?.menu = menu
        statusItem?.button?.performClick(nil)
        statusItem?.menu = nil  // Remove menu so left-click works again
    }
    
    @objc private func takeScreenshotClicked() {
        screenshotAction?()
    }
    
    @objc private func quitClicked() {
        NSApplication.shared.terminate(nil)
    }
    
    /// Position a window below the menu bar icon
    func positionWindowBelowMenuBar(_ window: NSWindow) {
        guard let button = statusItem?.button,
              let buttonWindow = button.window else {
            // Fallback: center on screen
            window.center()
            return
        }
        
        // Get the frame of the status bar button in screen coordinates
        let buttonFrame = buttonWindow.convertToScreen(button.frame)
        
        // Calculate window position: centered below the menu bar icon
        let windowWidth = window.frame.width
        let windowHeight = window.frame.height
        
        // X: Center the window under the menu bar icon
        let windowX = buttonFrame.midX - (windowWidth / 2)
        
        // Y: Position just below the menu bar (buttonFrame.minY is the bottom of the menu bar)
        let windowY = buttonFrame.minY - windowHeight - 5  // 5px gap
        
        // Make sure window doesn't go off screen
        if let screen = NSScreen.main {
            let screenFrame = screen.visibleFrame
            var finalX = windowX
            var finalY = windowY
            
            // Keep window within horizontal bounds
            if finalX < screenFrame.minX {
                finalX = screenFrame.minX
            } else if finalX + windowWidth > screenFrame.maxX {
                finalX = screenFrame.maxX - windowWidth
            }
            
            // Keep window within vertical bounds
            if finalY < screenFrame.minY {
                finalY = screenFrame.minY
            }
            
            window.setFrameOrigin(NSPoint(x: finalX, y: finalY))
        } else {
            window.setFrameOrigin(NSPoint(x: windowX, y: windowY))
        }
    }
}

