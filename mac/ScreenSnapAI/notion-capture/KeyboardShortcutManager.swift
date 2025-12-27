//
//  KeyboardShortcutManager.swift
//  ScreenSnapAI
//
//  Created by Maximilian Glasmacher on 29.11.25.
//

import AppKit
import Carbon

// Global reference to the manager for Carbon hotkey callback
private var globalShortcutManager: KeyboardShortcutManager?

// Carbon hotkey event handler
private func hotKeyHandler(nextHandler: EventHandlerCallRef?, theEvent: EventRef?, userData: UnsafeMutableRawPointer?) -> OSStatus {
    guard let theEvent = theEvent else {
        return OSStatus(eventNotHandledErr)
    }
    
    var hotKeyID = EventHotKeyID()
    let err = GetEventParameter(
        theEvent,
        EventParamName(kEventParamDirectObject),
        EventParamType(typeEventHotKeyID),
        nil,
        MemoryLayout<EventHotKeyID>.size,
        nil,
        &hotKeyID
    )
    
    guard err == noErr else {
        return err
    }
    
    // Trigger the action on the main thread
    DispatchQueue.main.async {
        globalShortcutManager?.action?()
    }
    
    return noErr
}

class KeyboardShortcutManager {
    static let shared = KeyboardShortcutManager()
    
    private var eventMonitor: Any?
    private var globalEventMonitor: Any?
    private var hotKeyRef: EventHotKeyRef?
    private var hotKeyID: EventHotKeyID?
    private var eventHandler: EventHandlerRef?
    private var currentShortcut: KeyboardShortcut?
    var action: (() -> Void)?
    
    private init() {
        globalShortcutManager = self
        setupCarbonEventHandler()
    }
    
    private func setupCarbonEventHandler() {
        var eventSpec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: OSType(kEventHotKeyPressed))
        
        InstallEventHandler(
            GetApplicationEventTarget(),
            hotKeyHandler,
            1,
            &eventSpec,
            nil,
            &eventHandler
        )
    }
    
    struct KeyboardShortcut: Codable, Equatable {
        var keyCode: UInt16
        var modifiers: NSEvent.ModifierFlags
        
        // Custom Codable implementation for ModifierFlags
        enum CodingKeys: String, CodingKey {
            case keyCode
            case modifiersRaw
        }
        
        init(keyCode: UInt16, modifiers: NSEvent.ModifierFlags) {
            self.keyCode = keyCode
            self.modifiers = modifiers
        }
        
        init(from decoder: Decoder) throws {
            let container = try decoder.container(keyedBy: CodingKeys.self)
            keyCode = try container.decode(UInt16.self, forKey: .keyCode)
            let modifiersRaw = try container.decode(UInt.self, forKey: .modifiersRaw)
            modifiers = NSEvent.ModifierFlags(rawValue: modifiersRaw)
        }
        
        func encode(to encoder: Encoder) throws {
            var container = encoder.container(keyedBy: CodingKeys.self)
            try container.encode(keyCode, forKey: .keyCode)
            try container.encode(modifiers.rawValue, forKey: .modifiersRaw)
        }
        
        var displayString: String {
            var parts: [String] = []
            
            if modifiers.contains(.command) {
                parts.append("⌘")
            }
            if modifiers.contains(.shift) {
                parts.append("⇧")
            }
            if modifiers.contains(.option) {
                parts.append("⌥")
            }
            if modifiers.contains(.control) {
                parts.append("⌃")
            }
            
            if let keyChar = keyCodeToString(keyCode) {
                parts.append(keyChar.uppercased())
            } else {
                parts.append("Key \(keyCode)")
            }
            
            return parts.joined(separator: " ")
        }
        
        static func fromUserDefaults() -> KeyboardShortcut? {
            guard let data = UserDefaults.standard.data(forKey: "screenshotShortcut"),
                  let shortcut = try? JSONDecoder().decode(KeyboardShortcut.self, from: data) else {
                return nil
            }
            return shortcut
        }
        
        func saveToUserDefaults() {
            if let data = try? JSONEncoder().encode(self) {
                UserDefaults.standard.set(data, forKey: "screenshotShortcut")
            }
        }
        
        static func defaultShortcut() -> KeyboardShortcut {
            // Default: Command + Shift + S
            return KeyboardShortcut(
                keyCode: 1, // 'S' key
                modifiers: [.command, .shift]
            )
        }
    }
    
    func setup(action: @escaping () -> Void) {
        self.action = action
        loadAndRegisterShortcut()
    }
    
    func loadAndRegisterShortcut() {
        // Remove existing monitors and hotkeys
        unregisterShortcut()
        
        // Load shortcut from UserDefaults or use default
        currentShortcut = KeyboardShortcut.fromUserDefaults() ?? KeyboardShortcut.defaultShortcut()
        
        // If no shortcut was saved, save the default
        if KeyboardShortcut.fromUserDefaults() == nil {
            currentShortcut?.saveToUserDefaults()
        }
        
        // Register the shortcut using both global monitor and Carbon hotkeys
        registerShortcut(currentShortcut!)
    }
    
    private func unregisterShortcut() {
        // Remove local monitor
        if let monitor = eventMonitor {
            NSEvent.removeMonitor(monitor)
            eventMonitor = nil
        }
        
        // Remove global monitor
        if let monitor = globalEventMonitor {
            NSEvent.removeMonitor(monitor)
            globalEventMonitor = nil
        }
        
        // Remove Carbon hotkey
        if let hotKeyRef = hotKeyRef {
            UnregisterEventHotKey(hotKeyRef)
            self.hotKeyRef = nil
            self.hotKeyID = nil
        }
    }
    
    private func convertToCarbonModifiers(_ modifiers: NSEvent.ModifierFlags) -> UInt32 {
        var carbonModifiers: UInt32 = 0
        
        if modifiers.contains(.command) {
            carbonModifiers |= UInt32(cmdKey)
        }
        if modifiers.contains(.shift) {
            carbonModifiers |= UInt32(shiftKey)
        }
        if modifiers.contains(.option) {
            carbonModifiers |= UInt32(optionKey)
        }
        if modifiers.contains(.control) {
            carbonModifiers |= UInt32(controlKey)
        }
        
        return carbonModifiers
    }
    
    private func registerShortcut(_ shortcut: KeyboardShortcut) {
        // Unregister any existing Carbon hotkey first
        if let hotKeyRef = hotKeyRef {
            UnregisterEventHotKey(hotKeyRef)
            self.hotKeyRef = nil
        }
        
        // Register Carbon hotkey for global system-wide shortcut
        var hotKeyID = EventHotKeyID()
        hotKeyID.signature = OSType(fourCharCodeFromString("SSAI")) // "SSAI" for ScreenSnapAI
        hotKeyID.id = 1
        
        let carbonModifiers = convertToCarbonModifiers(shortcut.modifiers)
        
        // Register the hotkey
        var hotKeyRef: EventHotKeyRef?
        let status = RegisterEventHotKey(
            UInt32(shortcut.keyCode),
            carbonModifiers,
            hotKeyID,
            GetApplicationEventTarget(),
            0,
            &hotKeyRef
        )
        
        if status == noErr, let ref = hotKeyRef {
            self.hotKeyRef = ref
            self.hotKeyID = hotKeyID
        }
        
        // Always register global event monitor as primary method (works even when app is in background)
        // Note: This requires Accessibility permissions in System Settings
        globalEventMonitor = NSEvent.addGlobalMonitorForEvents(matching: [.keyDown]) { [weak self] event in
            guard let self = self,
                  let currentShortcut = self.currentShortcut else {
                return
            }
            
            guard event.keyCode == currentShortcut.keyCode else {
                return
            }
            
            let requiredModifiers = currentShortcut.modifiers
            let eventModifiers = event.modifierFlags.intersection([.command, .shift, .option, .control])
            
            if eventModifiers == requiredModifiers {
                DispatchQueue.main.async {
                    self.action?()
                }
            }
        }
        
        // Also register a local monitor as fallback (when app is active)
        eventMonitor = NSEvent.addLocalMonitorForEvents(matching: [.keyDown]) { [weak self] event in
            guard let self = self,
                  let currentShortcut = self.currentShortcut else {
                return event
            }
            
            guard event.keyCode == currentShortcut.keyCode else {
                return event
            }
            
            let requiredModifiers = currentShortcut.modifiers
            let eventModifiers = event.modifierFlags.intersection([.command, .shift, .option, .control])
            
            if eventModifiers == requiredModifiers {
                self.action?()
                return nil // Consume the event
            }
            
            return event
        }
    }
    
    deinit {
        unregisterShortcut()
        if let handler = eventHandler {
            RemoveEventHandler(handler)
        }
    }
    
    func updateShortcut(_ shortcut: KeyboardShortcut) {
        currentShortcut = shortcut
        shortcut.saveToUserDefaults()
        loadAndRegisterShortcut()
    }
    
    func getCurrentShortcut() -> KeyboardShortcut? {
        return currentShortcut ?? KeyboardShortcut.fromUserDefaults() ?? KeyboardShortcut.defaultShortcut()
    }
}

// Helper function to convert four-character code string to OSType
private func fourCharCodeFromString(_ string: String) -> FourCharCode {
    guard string.count >= 4,
          let data = string.data(using: .macOSRoman),
          data.count >= 4 else {
        return 0
    }
    
    var result: FourCharCode = 0
    data.withUnsafeBytes { (bytes: UnsafeRawBufferPointer) in
        guard bytes.count >= 4 else { return }
        result = FourCharCode(bytes[0]) << 24 |
                 FourCharCode(bytes[1]) << 16 |
                 FourCharCode(bytes[2]) << 8 |
                 FourCharCode(bytes[3])
    }
    return result
}

// Helper function to convert key code to string
private func keyCodeToString(_ keyCode: UInt16) -> String? {
    // Map common key codes to their characters
    let keyCodeMap: [UInt16: String] = [
        0: "A", 1: "S", 2: "D", 3: "F", 4: "H", 5: "G", 6: "Z", 7: "X", 8: "C", 9: "V",
        11: "B", 12: "Q", 13: "W", 14: "E", 15: "R", 16: "Y", 17: "T", 31: "O", 32: "U",
        34: "I", 35: "P", 37: "L", 38: "J", 40: "K", 45: "N", 46: "M",
        36: "Return", 48: "Tab", 49: "Space", 51: "Delete", 53: "Escape",
        123: "←", 124: "→", 125: "↓", 126: "↑",
        122: "F1", 120: "F2", 99: "F3", 118: "F4", 96: "F5", 97: "F6", 98: "F7", 100: "F8",
        101: "F9", 109: "F10", 103: "F11", 111: "F12"
    ]
    
    return keyCodeMap[keyCode]
}
