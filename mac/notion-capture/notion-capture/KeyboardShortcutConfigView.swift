//
//  KeyboardShortcutConfigView.swift
//  ScreenSnapAI
//
//  Created by Maximilian Glasmacher on 29.11.25.
//

import SwiftUI
import AppKit

struct KeyboardShortcutConfigView: View {
    @State private var currentShortcut: KeyboardShortcutManager.KeyboardShortcut
    @State private var isRecording: Bool = false
    @State private var eventMonitor: Any?
    
    init() {
        // Load current shortcut or use default
        _currentShortcut = State(initialValue: KeyboardShortcutManager.shared.getCurrentShortcut() ?? KeyboardShortcutManager.KeyboardShortcut.defaultShortcut())
    }
    
    var body: some View {
        HStack(spacing: 12) {
            // Display current shortcut
            if isRecording {
                Text("Press keys...")
                    .font(.system(size: 13, design: .monospaced))
                    .foregroundColor(.orange)
            } else {
                Text(currentShortcut.displayString)
                    .font(.system(size: 13, design: .monospaced))
                    .foregroundColor(.primary)
            }
            
            if isRecording {
                Button("Cancel") {
                    cancelRecording()
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            } else {
                Button("Change") {
                    startRecording()
                }
                .buttonStyle(.bordered)
                .controlSize(.small)
            }
        }
        .onAppear {
            // Refresh shortcut when view appears
            if let shortcut = KeyboardShortcutManager.shared.getCurrentShortcut() {
                currentShortcut = shortcut
            }
        }
        .onDisappear {
            // Clean up event monitor if view disappears
            if let monitor = eventMonitor {
                NSEvent.removeMonitor(monitor)
                eventMonitor = nil
            }
        }
    }
    
    private func startRecording() {
        isRecording = true
        
        // Set up a global event monitor to capture the next key press
        eventMonitor = NSEvent.addLocalMonitorForEvents(matching: [.keyDown]) { event in
            // Filter to only the modifiers we care about
            let relevantModifiers = event.modifierFlags.intersection([.command, .shift, .option, .control])
            
            // Require at least one modifier key
            guard !relevantModifiers.isEmpty else {
                return event
            }
            
            let newShortcut = KeyboardShortcutManager.KeyboardShortcut(
                keyCode: event.keyCode,
                modifiers: relevantModifiers
            )
            
            // Update the shortcut
            DispatchQueue.main.async {
                self.currentShortcut = newShortcut
                KeyboardShortcutManager.shared.updateShortcut(newShortcut)
                self.cancelRecording()
            }
            
            // Consume the event so it doesn't trigger other actions
            return nil
        }
    }
    
    private func cancelRecording() {
        isRecording = false
        
        // Remove the event monitor
        if let monitor = eventMonitor {
            NSEvent.removeMonitor(monitor)
            eventMonitor = nil
        }
    }
}
