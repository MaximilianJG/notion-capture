//
//  ContentView.swift
//  Notion Capture
//
//  Stateless backend with BYOC (Bring Your Own Credentials)
//  Frontend stores credentials locally and sends them with each request
//

import SwiftUI
import AppKit
import Security
import Combine

enum TabSelection: Hashable {
    case home
    case configure
}

// MARK: - AI Result Summary for Popup
struct AISummary: Codable {
    let destination: String?
    let database: String?
    let filledFromUser: [[String: String]]?
    let filledByAi: [[String: String]]?
    let leftEmpty: [[String: String]]?
    let assumptions: [String]?
    
    enum CodingKeys: String, CodingKey {
        case destination
        case database
        case filledFromUser = "filled_from_user"
        case filledByAi = "filled_by_ai"
        case leftEmpty = "left_empty"
        case assumptions
    }
}

struct CaptureResult: Identifiable {
    let id = UUID()
    let title: String
    let category: String
    let destination: String
    let success: Bool
    let summary: AISummary?
    let link: String?
    let error: String?
    let timestamp: Date
}

// MARK: - Credential Storage
class CredentialStore: ObservableObject {
    static let shared = CredentialStore()
    
    // Notion OAuth tokens
    @Published var notionTokens: [String: Any]? = nil
    @Published var notionSelectedPageId: String = ""
    // Google OAuth tokens
    @Published var googleTokens: [String: Any]? = nil
    
    private let notionTokensKey = "notion_tokens"
    private let notionPageIdKey = "notion_selected_page_id"
    private let googleTokensKey = "google_tokens"
    
    init() {
        loadCredentials()
    }
    
    func loadCredentials() {
        notionSelectedPageId = UserDefaults.standard.string(forKey: notionPageIdKey) ?? ""
        
        if let data = UserDefaults.standard.data(forKey: notionTokensKey),
           let tokens = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            notionTokens = tokens
        }
        
        if let data = UserDefaults.standard.data(forKey: googleTokensKey),
           let tokens = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            googleTokens = tokens
        }
    }
    
    // Save Notion OAuth tokens
    func saveNotionTokens(_ tokens: [String: Any]) {
        notionTokens = tokens
        if let data = try? JSONSerialization.data(withJSONObject: tokens) {
            UserDefaults.standard.set(data, forKey: notionTokensKey)
        }
    }
    
    func saveGoogleTokens(_ tokens: [String: Any]) {
        googleTokens = tokens
        if let data = try? JSONSerialization.data(withJSONObject: tokens) {
            UserDefaults.standard.set(data, forKey: googleTokensKey)
        }
    }
    
    func clearGoogleTokens() {
        googleTokens = nil
        UserDefaults.standard.removeObject(forKey: googleTokensKey)
    }
    
    func clearNotionCredentials() {
        notionSelectedPageId = ""
        notionTokens = nil
        UserDefaults.standard.removeObject(forKey: notionPageIdKey)
        UserDefaults.standard.removeObject(forKey: notionTokensKey)
    }
    
    var googleTokensJSON: String? {
        guard let tokens = googleTokens,
              let data = try? JSONSerialization.data(withJSONObject: tokens),
              let json = String(data: data, encoding: .utf8) else {
            return nil
        }
        return json
    }
    
    var notionTokensJSON: String? {
        guard let tokens = notionTokens,
              let data = try? JSONSerialization.data(withJSONObject: tokens),
              let json = String(data: data, encoding: .utf8) else {
            return nil
        }
        return json
    }
    
    var notionAccessToken: String? {
        notionTokens?["access_token"] as? String
    }
    
    var hasNotionCredentials: Bool {
        notionAccessToken != nil
    }
    
    var hasGoogleCredentials: Bool {
        googleTokens != nil && (googleTokens?["access_token"] as? String) != nil
    }
    
    var notionWorkspaceName: String? {
        notionTokens?["workspace_name"] as? String
    }
}

struct ContentView: View {
    @EnvironmentObject var screenshotTrigger: ScreenshotTrigger
    @StateObject private var credentials = CredentialStore.shared
    
    @State private var statusMessage: String = "Ready"
    @State private var googleConnected: Bool = false
    @State private var googleEmail: String? = nil
    @State private var notionConnected: Bool = false
    @State private var notionWorkspace: String? = nil
    @State private var selectedTab: TabSelection = .home
    @State private var isPollingGoogleStatus: Bool = false
    @State private var isHoveringHome: Bool = false
    @State private var isHoveringConfigure: Bool = false
    @State private var isHoveringScreenshot: Bool = false
    @State private var isHoveringLogout: Bool = false
    @State private var textInput: String = ""
    @State private var isProcessingText: Bool = false
    @State private var isHoveringSendText: Bool = false
    
    // Notion OAuth
    @State private var isPollingNotionStatus: Bool = false
    
    // Recent captures (in-memory only)
    @State private var recentCaptures: [CaptureResult] = []
    @State private var showResultPopup: Bool = false
    @State private var lastResult: CaptureResult? = nil
    
    // Notion databases
    @State private var notionDatabases: [[String: Any]] = []
    @State private var showDatabasesDropdown: Bool = false
    
    // Backend URL - localhost for development, Railway for production
    #if DEBUG
    private let backendURL = "http://localhost:8000"
    #else
    private let backendURL = "https://notion-capture-production.up.railway.app"
    #endif

    var body: some View {
        ZStack {
            VStack(spacing: 0) {
                // Tab bar
                tabBar
                
                // Tab Content
                ZStack {
                    homeTabView
                        .opacity(selectedTab == .home ? 1 : 0)
                    
                    configureTabView
                        .opacity(selectedTab == .configure ? 1 : 0)
                }
                .frame(minHeight: 316)
            }
            .frame(minWidth: 520, minHeight: 360)
            
            // Result popup overlay
            if showResultPopup, let result = lastResult {
                resultPopupView(result: result)
            }
        }
        .onAppear {
            checkGoogleStatus()
            checkNotionStatus()
            
            // Listen for app becoming active
            NotificationCenter.default.addObserver(
                forName: NSApplication.didBecomeActiveNotification,
                object: nil,
                queue: .main
            ) { _ in
                self.checkGoogleStatus()
                self.checkNotionStatus()
            }
            
            // Listen for status updates from ScreenshotManager
            NotificationCenter.default.addObserver(
                forName: .screenshotStatusUpdate,
                object: nil,
                queue: .main
            ) { notification in
                if let message = notification.userInfo?["message"] as? String {
                    self.statusMessage = message
                }
            }
            
            // Hide window when screenshot starts
            NotificationCenter.default.addObserver(
                forName: .screenshotStarted,
                object: nil,
                queue: .main
            ) { _ in
                if let window = NSApplication.shared.windows.first {
                    window.orderOut(nil)
                }
            }
            
            // Show window when screenshot completes
            NotificationCenter.default.addObserver(
                forName: .screenshotCompleted,
                object: nil,
                queue: .main
            ) { _ in
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                    if let window = NSApplication.shared.windows.first {
                        NSApplication.shared.activate(ignoringOtherApps: true)
                        window.collectionBehavior = [.moveToActiveSpace, .fullScreenAuxiliary]
                        window.makeKeyAndOrderFront(nil)
                    }
                }
            }
            
            // Listen for screenshot upload to handle response
            NotificationCenter.default.addObserver(
                forName: .screenshotUploaded,
                object: nil,
                queue: .main
            ) { notification in
                if let data = notification.userInfo?["responseData"] as? Data {
                    handleCaptureResponse(data: data)
                }
            }
            
            // Listen for Google tokens received via URL scheme
            NotificationCenter.default.addObserver(
                forName: .googleTokensReceived,
                object: nil,
                queue: .main
            ) { notification in
                self.isPollingGoogleStatus = false
                self.statusMessage = "Google Calendar connected!"
                self.checkGoogleStatus()
            }
            
            // Listen for Google auth errors
            NotificationCenter.default.addObserver(
                forName: .googleAuthError,
                object: nil,
                queue: .main
            ) { notification in
                self.isPollingGoogleStatus = false
                if let error = notification.object as? String {
                    self.statusMessage = "Google auth error: \(error)"
                }
            }
            
            // Listen for Notion tokens received via URL scheme
            NotificationCenter.default.addObserver(
                forName: .notionTokensReceived,
                object: nil,
                queue: .main
            ) { notification in
                self.isPollingNotionStatus = false
                self.statusMessage = "Notion connected!"
                self.checkNotionStatus()
            }
            
            // Listen for Notion auth errors
            NotificationCenter.default.addObserver(
                forName: .notionAuthError,
                object: nil,
                queue: .main
            ) { notification in
                self.isPollingNotionStatus = false
                if let error = notification.object as? String {
                    self.statusMessage = "Notion auth error: \(error)"
                }
            }
        }
        .onChange(of: screenshotTrigger.shouldTakeScreenshot) { _, newValue in
            if newValue {
                ScreenshotManager.shared.takeScreenshot(credentials: credentials)
            }
        }
    }
    
    // MARK: - Result Popup
    private func resultPopupView(result: CaptureResult) -> some View {
        ZStack {
            Color.black.opacity(0.4)
                .ignoresSafeArea()
                .onTapGesture {
                    withAnimation { showResultPopup = false }
                }
            
            VStack(alignment: .leading, spacing: 16) {
                HStack {
                    Image(systemName: result.success ? "checkmark.circle.fill" : "xmark.circle.fill")
                        .foregroundColor(result.success ? .green : .red)
                        .font(.system(size: 24))
                    
                    VStack(alignment: .leading) {
                        Text(result.success ? "Success" : "Failed")
                            .font(.headline)
                        Text(result.title)
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                    }
                    
                    Spacer()
                    
                    Button(action: { withAnimation { showResultPopup = false } }) {
                        Image(systemName: "xmark")
                            .foregroundColor(.secondary)
                    }
                    .buttonStyle(.plain)
                }
                
                Divider()
                
                HStack {
                    Text("Destination:")
                        .fontWeight(.medium)
                    Text(result.destination)
                        .foregroundColor(.blue)
                }
                
                if let summary = result.summary {
                    if let database = summary.database {
                        HStack {
                            Text("Database:")
                                .fontWeight(.medium)
                            Text(database)
                        }
                    }
                    
                    if let filled = summary.filledFromUser, !filled.isEmpty {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Filled from your input:")
                                .fontWeight(.medium)
                            ForEach(Array(filled.enumerated()), id: \.offset) { _, item in
                                if let field = item["field"] ?? item["property"] {
                                    Text("• \(field)")
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            }
                        }
                    }
                    
                    if let aiFilledArray = summary.filledByAi, !aiFilledArray.isEmpty {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Filled by AI research:")
                                .fontWeight(.medium)
                            ForEach(Array(aiFilledArray.enumerated()), id: \.offset) { _, item in
                                if let prop = item["property"], let value = item["value"] {
                                    Text("• \(prop): \(value)")
                                        .font(.caption)
                                        .foregroundColor(.purple)
                                }
                            }
                        }
                    }
                    
                    if let empty = summary.leftEmpty, !empty.isEmpty {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Left empty:")
                                .fontWeight(.medium)
                            ForEach(Array(empty.enumerated()), id: \.offset) { _, item in
                                if let prop = item["property"], let reason = item["reason"] {
                                    Text("• \(prop) (\(reason))")
                                        .font(.caption)
                                        .foregroundColor(.orange)
                                }
                            }
                        }
                    }
                }
                
                if let error = result.error {
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.red)
                        .padding(8)
                        .background(Color.red.opacity(0.1))
                        .cornerRadius(6)
                }
                
                if let link = result.link, let url = URL(string: link) {
                    Link(destination: url) {
                        HStack {
                            Image(systemName: "arrow.up.right.square")
                            Text("Open in \(result.destination)")
                        }
                        .frame(maxWidth: .infinity)
                        .padding(8)
                        .background(Color.accentColor)
                        .foregroundColor(.white)
                        .cornerRadius(6)
                    }
                }
            }
            .padding(20)
            .frame(width: 400)
            .background(Color(NSColor.windowBackgroundColor))
            .cornerRadius(12)
            .shadow(radius: 20)
        }
    }
    
    // MARK: - Tab Bar
    private var tabBar: some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                Spacer()
                
                HStack(spacing: 4) {
                    Button(action: { selectedTab = .home }) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 6)
                                .fill((selectedTab == .home || isHoveringHome) ? Color.accentColor.opacity(0.15) : Color.clear)
                            
                            RoundedRectangle(cornerRadius: 6)
                                .stroke(selectedTab == .home ? Color.accentColor.opacity(0.3) : Color.clear, lineWidth: 1)
                            
                            Text("Home")
                                .font(.system(size: 13, weight: selectedTab == .home ? .bold : .medium))
                                .foregroundColor(selectedTab == .home ? .primary : .secondary)
                        }
                        .frame(width: 70, height: 28)
                        .contentShape(RoundedRectangle(cornerRadius: 6))
                    }
                    .buttonStyle(.plain)
                    .onHover { hovering in isHoveringHome = hovering }
                    
                    Button(action: { selectedTab = .configure }) {
                        ZStack {
                            RoundedRectangle(cornerRadius: 6)
                                .fill((selectedTab == .configure || isHoveringConfigure) ? Color.accentColor.opacity(0.15) : Color.clear)
                            
                            RoundedRectangle(cornerRadius: 6)
                                .stroke(selectedTab == .configure ? Color.accentColor.opacity(0.3) : Color.clear, lineWidth: 1)
                            
                            Text("Configure")
                                .font(.system(size: 13, weight: selectedTab == .configure ? .bold : .medium))
                                .foregroundColor(selectedTab == .configure ? .primary : .secondary)
                        }
                        .frame(width: 80, height: 28)
                        .contentShape(RoundedRectangle(cornerRadius: 6))
                    }
                    .buttonStyle(.plain)
                    .onHover { hovering in isHoveringConfigure = hovering }
                }
                .padding(4)
                .background(
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color(NSColor.controlBackgroundColor))
                )
                
                Spacer()
            }
            .frame(minWidth: 520, minHeight: 44)
            
            // Connection Status Bar
            HStack(spacing: 16) {
                HStack(spacing: 6) {
                    Image(systemName: googleConnected ? "checkmark.circle.fill" : "xmark.circle")
                        .foregroundColor(googleConnected ? .green : .gray)
                        .font(.system(size: 12))
                    Text("Google")
                        .font(.system(size: 11))
                        .foregroundColor(googleConnected ? .primary : .secondary)
                }
                
                HStack(spacing: 6) {
                    Image(systemName: notionConnected ? "checkmark.circle.fill" : "xmark.circle")
                        .foregroundColor(notionConnected ? .green : .gray)
                        .font(.system(size: 12))
                    Text("Notion")
                        .font(.system(size: 11))
                        .foregroundColor(notionConnected ? .primary : .secondary)
                }
            }
            .padding(.vertical, 6)
            .frame(maxWidth: .infinity)
            .background(Color(NSColor.controlBackgroundColor).opacity(0.5))
        }
        .background(Color(NSColor.windowBackgroundColor))
        .overlay(
            Rectangle()
                .frame(height: 1)
                .foregroundColor(Color(NSColor.separatorColor).opacity(0.5)),
            alignment: .bottom
        )
    }
    
    // MARK: - Home Tab
    private var homeTabView: some View {
        VStack(alignment: .leading, spacing: 0) {
            VStack(spacing: 12) {
                Text(statusMessage)
                    .font(.system(size: 12))
                    .foregroundColor(.secondary)
                    .lineLimit(2)
                    .multilineTextAlignment(.center)
                
                Button("Take Screenshot") {
                    ScreenshotManager.shared.takeScreenshot(credentials: credentials)
                }
                .buttonStyle(.borderedProminent)
                .scaleEffect(isHoveringScreenshot ? 1.03 : 1.0)
                .animation(.easeInOut(duration: 0.1), value: isHoveringScreenshot)
                .onHover { hovering in isHoveringScreenshot = hovering }
                
                HStack(spacing: 8) {
                    TextField("Type something to capture...", text: $textInput)
                        .textFieldStyle(.plain)
                        .padding(8)
                        .background(Color(NSColor.textBackgroundColor))
                        .cornerRadius(8)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(Color(NSColor.separatorColor), lineWidth: 1)
                        )
                        .onSubmit {
                            if !textInput.isEmpty && !isProcessingText {
                                sendTextToBackend()
                            }
                        }
                    
                    Button(action: {
                        if !textInput.isEmpty && !isProcessingText {
                            sendTextToBackend()
                        }
                    }) {
                        if isProcessingText {
                            ProgressView()
                                .scaleEffect(0.7)
                                .frame(width: 20, height: 20)
                        } else {
                            Image(systemName: "arrow.up.circle.fill")
                                .font(.system(size: 24))
                                .foregroundColor(textInput.isEmpty ? .gray : .accentColor)
                        }
                    }
                    .buttonStyle(.plain)
                    .disabled(textInput.isEmpty || isProcessingText)
                    .scaleEffect(isHoveringSendText && !textInput.isEmpty ? 1.1 : 1.0)
                    .animation(.easeInOut(duration: 0.1), value: isHoveringSendText)
                    .onHover { hovering in isHoveringSendText = hovering }
                }
                .padding(.horizontal, 16)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 12)
            .background(Color(NSColor.controlBackgroundColor))
            
            Divider()
            
            VStack(spacing: 0) {
                if !recentCaptures.isEmpty {
                    ScrollView {
                        LazyVStack(spacing: 10) {
                            ForEach(recentCaptures) { capture in
                                captureRow(capture)
                            }
                        }
                        .padding(16)
                    }
                } else {
                    VStack {
                        Spacer()
                        Image(systemName: "tray")
                            .font(.system(size: 40))
                            .foregroundColor(.secondary.opacity(0.5))
                        Text("No captures yet")
                            .font(.system(size: 13))
                            .foregroundColor(.secondary)
                        Text("Take a screenshot or type to get started")
                            .font(.system(size: 11))
                            .foregroundColor(.secondary.opacity(0.7))
                        Spacer()
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            .frame(maxHeight: .infinity)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    private func captureRow(_ capture: CaptureResult) -> some View {
        CaptureRowView(capture: capture, onTap: {
            lastResult = capture
            withAnimation { showResultPopup = true }
        })
    }
}

// MARK: - Capture Row View (Hoverable)
struct CaptureRowView: View {
    let capture: CaptureResult
    let onTap: () -> Void
    @State private var isHovered: Bool = false
    
    var body: some View {
        HStack(spacing: 12) {
            Image(systemName: capture.category == "event" ? "calendar" : "doc.text")
                .font(.system(size: 16))
                .foregroundColor(capture.success ? (capture.category == "event" ? .blue : .purple) : .red)
                .frame(width: 32, height: 32)
                .background(
                    (capture.success ? (capture.category == "event" ? Color.blue : Color.purple) : Color.red)
                        .opacity(0.15)
                )
                .cornerRadius(8)
            
            VStack(alignment: .leading, spacing: 4) {
                Text(capture.title)
                    .font(.system(size: 13, weight: .medium))
                    .lineLimit(1)
                
                HStack(spacing: 8) {
                    Text(capture.destination)
                        .font(.system(size: 11))
                        .foregroundColor(.secondary)
                    
                    if let db = capture.summary?.database {
                        Text("→ \(db)")
                            .font(.system(size: 11))
                            .foregroundColor(.secondary)
                    }
                }
            }
            
            Spacer()
            
            HStack(spacing: 6) {
                if isHovered {
                    Text("Click for details")
                        .font(.system(size: 10))
                        .foregroundColor(.secondary)
                }
                Image(systemName: capture.success ? "checkmark.circle.fill" : "xmark.circle.fill")
                    .foregroundColor(capture.success ? .green : .red)
                    .font(.system(size: 14))
            }
        }
        .padding(10)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(isHovered ? Color.accentColor.opacity(0.1) : Color(NSColor.controlBackgroundColor))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(isHovered ? Color.accentColor.opacity(0.3) : Color.clear, lineWidth: 1)
        )
        .scaleEffect(isHovered ? 1.01 : 1.0)
        .animation(.easeInOut(duration: 0.15), value: isHovered)
        .onHover { hovering in
            isHovered = hovering
        }
        .onTapGesture {
            onTap()
        }
        .help("Click to see what AI did")
    }
}

// MARK: - ContentView Extensions
extension ContentView {
    // MARK: - Configure Tab
    private var configureTabView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                // Google Calendar Section
                VStack(alignment: .leading, spacing: 12) {
                    Text("Google Calendar")
                        .font(.headline)
                    
                    if googleConnected {
                        HStack {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.green)
                            Text("Connected")
                                .foregroundColor(.primary)
                            Spacer()
                            Button("Disconnect") {
                                logoutGoogle()
                            }
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                        }
                        .padding(12)
                        .background(Color.green.opacity(0.1))
                        .cornerRadius(8)
                    } else {
                        Button("Connect to Google Calendar") {
                            connectGoogle()
                        }
                        .buttonStyle(.borderedProminent)
                    }
                    
                    Text("Events will be saved to your Google Calendar")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Divider()
                
                // Notion Section
                VStack(alignment: .leading, spacing: 12) {
                    Text("Notion")
                        .font(.headline)
                    
                    if notionConnected {
                        HStack {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.green)
                            VStack(alignment: .leading, spacing: 2) {
                            Text("Connected")
                                .foregroundColor(.primary)
                                if let workspace = notionWorkspace ?? credentials.notionWorkspaceName {
                                    Text(workspace)
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                }
                            }
                            Spacer()
                            Button("Disconnect") {
                                credentials.clearNotionCredentials()
                                notionConnected = false
                                notionWorkspace = nil
                                showDatabasesDropdown = false
                            }
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                        }
                        .padding(12)
                        .background(Color.green.opacity(0.1))
                        .cornerRadius(8)
                        
                        if !notionDatabases.isEmpty {
                            VStack(alignment: .leading, spacing: 0) {
                                Button(action: {
                                    withAnimation(.easeInOut(duration: 0.2)) {
                                        showDatabasesDropdown.toggle()
                                    }
                                }) {
                                    HStack {
                                        Image(systemName: "tablecells")
                                            .foregroundColor(.purple)
                                        Text("Available Databases (\(notionDatabases.count))")
                                            .font(.subheadline)
                                        Spacer()
                                        Image(systemName: showDatabasesDropdown ? "chevron.up" : "chevron.down")
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                    }
                                    .padding(10)
                                    .background(Color(NSColor.controlBackgroundColor))
                                    .cornerRadius(showDatabasesDropdown ? 8 : 8)
                                }
                                .buttonStyle(.plain)
                                
                                if showDatabasesDropdown {
                                    VStack(alignment: .leading, spacing: 6) {
                                        ForEach(Array(notionDatabases.enumerated()), id: \.offset) { _, db in
                                            if let title = db["title"] as? String {
                                                HStack {
                                                    Image(systemName: "doc.text")
                                                        .foregroundColor(.purple.opacity(0.7))
                                                        .font(.caption)
                                                    Text(title)
                                                        .font(.caption)
                                                        .foregroundColor(.primary)
                                                }
                                            }
                                        }
                                    }
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 8)
                                    .background(Color(NSColor.controlBackgroundColor).opacity(0.5))
                                    .cornerRadius(8)
                                    .padding(.top, 4)
                                }
                            }
                        }
                    } else {
                        Button("Connect to Notion") {
                            connectNotion()
                                }
                                .buttonStyle(.borderedProminent)
                    }
                    
                    Text("Non-event captures will be saved to Notion databases")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                
                Divider()
                
                // Keyboard Shortcut Section
                VStack(alignment: .leading, spacing: 12) {
                    Text("Keyboard Shortcut")
                        .font(.headline)
                    
                    KeyboardShortcutConfigView()
                }
                
                Divider()
                
                // Developer Tools
                VStack(alignment: .leading, spacing: 12) {
                    Text("Developer Tools")
                        .font(.headline)
                    
                    Menu {
                        Button("Health Check") { healthCheck() }
                        Button("Test Calendar Event") { testCalendar() }
                        Button("Refresh Notion Databases") { fetchNotionDatabases() }
                    } label: {
                        HStack {
                            Image(systemName: "ellipsis.circle")
                            Text("Developer Menu")
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .menuStyle(.borderedButton)
                }
                
                Spacer()
            }
            .padding(16)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
    
    // MARK: - API Functions
    
    private func checkGoogleStatus(continuePolling: Bool = false) {
        guard credentials.hasGoogleCredentials else {
            googleConnected = false
            googleEmail = nil
            return
        }
        
        guard let url = URL(string: "\(backendURL)/google/auth/status") else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        if let tokensData = try? JSONSerialization.data(withJSONObject: credentials.googleTokens ?? [:]) {
            request.httpBody = tokensData
        }
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let data = data,
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    let wasConnected = self.googleConnected
                    self.googleConnected = json["connected"] as? Bool ?? false
                    self.googleEmail = json["email"] as? String
                    
                    if self.googleConnected && !wasConnected {
                        self.isPollingGoogleStatus = false
                        self.statusMessage = "Google Calendar connected!"
                    } else if continuePolling && !self.googleConnected && self.isPollingGoogleStatus {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                            if self.isPollingGoogleStatus {
                                self.checkGoogleStatus(continuePolling: true)
                            }
                        }
                    }
                }
            }
        }.resume()
    }
    
    private func checkNotionStatus() {
        // First check if OAuth is configured (even if not connected)
        guard let statusUrl = URL(string: "\(backendURL)/notion/auth/status") else { return }
        
        var request = URLRequest(url: statusUrl)
        // Send Notion OAuth tokens
        if let tokensJSON = credentials.notionTokensJSON {
            request.setValue(tokensJSON, forHTTPHeaderField: "X-Notion-Api-Key")
        }
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                if let data = data,
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    self.notionConnected = json["connected"] as? Bool ?? false
                    self.notionWorkspace = json["workspace_name"] as? String
                    
                    if self.notionConnected {
                        self.fetchNotionDatabases()
                    }
                }
            }
        }.resume()
    }
    
    private func connectNotion() {
        statusMessage = "Connecting to Notion…"
        
        guard let url = URL(string: "\(backendURL)/notion/auth/url") else {
            statusMessage = "Bad URL"
            return
        }
        
        URLSession.shared.dataTask(with: URLRequest(url: url)) { data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    self.statusMessage = "Error: \(error.localizedDescription)"
                    return
                }
                
                guard let data = data,
                      let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let authUrlString = json["auth_url"] as? String,
                      let authUrl = URL(string: authUrlString) else {
                    self.statusMessage = "Error: Invalid response"
                    return
                }
                
                if NSWorkspace.shared.open(authUrl) {
                    self.statusMessage = "Complete authentication in browser…"
                    self.isPollingNotionStatus = true
                    
                    // Timeout after 2 minutes
                    DispatchQueue.main.asyncAfter(deadline: .now() + 120) {
                        self.isPollingNotionStatus = false
                    }
                }
            }
        }.resume()
    }
    
    private func connectGoogle() {
        statusMessage = "Connecting to Google…"
        
        guard let url = URL(string: "\(backendURL)/google/auth/url") else {
            statusMessage = "Bad URL"
            return
        }
        
        URLSession.shared.dataTask(with: URLRequest(url: url)) { data, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    self.statusMessage = "Error: \(error.localizedDescription)"
                    return
                }
                
                guard let data = data,
                      let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                      let authUrlString = json["auth_url"] as? String,
                      let authUrl = URL(string: authUrlString) else {
                    self.statusMessage = "Error: Invalid response"
                    return
                }
                
                if NSWorkspace.shared.open(authUrl) {
                    self.statusMessage = "Complete authentication in browser…"
                    self.isPollingGoogleStatus = true
                    
                    // Poll for status updates
                    DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
                        if self.isPollingGoogleStatus {
                            self.checkGoogleStatus(continuePolling: true)
                        }
                    }
                    
                    DispatchQueue.main.asyncAfter(deadline: .now() + 120) {
                        self.isPollingGoogleStatus = false
                    }
                }
            }
        }.resume()
    }
    
    private func logoutGoogle() {
        statusMessage = "Disconnecting Google…"
        isPollingGoogleStatus = false
        credentials.clearGoogleTokens()
        googleConnected = false
        googleEmail = nil
        statusMessage = "Google disconnected"
    }
    
    private func fetchNotionDatabases() {
        guard credentials.hasNotionCredentials else { return }
        guard let url = URL(string: "\(backendURL)/notion/databases") else { return }
        
        var request = URLRequest(url: url)
        // Send Notion OAuth tokens
        if let tokensJSON = credentials.notionTokensJSON {
            request.setValue(tokensJSON, forHTTPHeaderField: "X-Notion-Api-Key")
        }
        
        URLSession.shared.dataTask(with: request) { data, _, _ in
            DispatchQueue.main.async {
                if let data = data,
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   let databases = json["databases"] as? [[String: Any]] {
                    self.notionDatabases = databases
                }
            }
        }.resume()
    }
    
    private func sendTextToBackend() {
        guard !textInput.isEmpty else { return }
        
        isProcessingText = true
        statusMessage = "Processing…"
        
        let textToSend = textInput
        textInput = ""
        
        guard let url = URL(string: "\(backendURL)/process-text") else {
            statusMessage = "Bad URL"
            isProcessingText = false
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        // Add credentials to headers
        if credentials.hasNotionCredentials {
            if let tokensJSON = credentials.notionTokensJSON {
                request.setValue(tokensJSON, forHTTPHeaderField: "X-Notion-Api-Key")
            }
            request.setValue(credentials.notionSelectedPageId, forHTTPHeaderField: "X-Notion-Page-Id")
        }
        if let googleTokensJSON = credentials.googleTokensJSON {
            request.setValue(googleTokensJSON, forHTTPHeaderField: "X-Google-Tokens")
        }
        
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["text": textToSend])
        
        URLSession.shared.dataTask(with: request) { data, response, error in
            DispatchQueue.main.async {
                self.isProcessingText = false
                
                if let error = error {
                    self.statusMessage = "Error: \(error.localizedDescription)"
                    return
                }
                
                self.handleCaptureResponse(data: data)
            }
        }.resume()
    }
    
    private func handleCaptureResponse(data: Data?) {
        guard let data = data,
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            statusMessage = "Error: Invalid response"
            return
        }
        
        // Update connection status from response
        if let googleStatus = json["google_status"] as? [String: Any] {
            googleConnected = googleStatus["connected"] as? Bool ?? false
            googleEmail = googleStatus["email"] as? String
        }
        if let notionStatus = json["notion_status"] as? [String: Any] {
            notionConnected = notionStatus["connected"] as? Bool ?? false
            notionWorkspace = notionStatus["workspace_name"] as? String
        }
        
        let title = json["title"] as? String ?? "Untitled"
        let category = json["category"] as? String ?? "other"
        
        var success = false
        var destination = "Unknown"
        var link: String? = nil
        var error: String? = nil
        var summary: AISummary? = nil
        
        if category == "event" {
            destination = "Google Calendar"
            success = json["calendar_event_created"] as? Bool ?? false
            if let eventInfo = json["event_info"] as? [String: Any] {
                link = eventInfo["calendar_link"] as? String
            }
            error = json["calendar_error"] as? String
        } else {
            destination = "Notion"
            success = json["notion_created"] as? Bool ?? false
            if let notionInfo = json["notion_info"] as? [String: Any] {
                link = notionInfo["page_url"] as? String
            }
            error = json["notion_error"] as? String
        }
        
        if let summaryDict = json["summary"] as? [String: Any] {
            let decoder = JSONDecoder()
            if let summaryData = try? JSONSerialization.data(withJSONObject: summaryDict),
               let decoded = try? decoder.decode(AISummary.self, from: summaryData) {
                summary = decoded
            }
        }
        
        let result = CaptureResult(
            title: title,
            category: category,
            destination: destination,
            success: success,
            summary: summary,
            link: link,
            error: error,
            timestamp: Date()
        )
        
        recentCaptures.insert(result, at: 0)
        if recentCaptures.count > 20 {
            recentCaptures.removeLast()
        }
        
        statusMessage = success ? "\(category == "event" ? "Event" : "Item") created" : "Failed: \(error ?? "Unknown error")"
    }
    
    private func healthCheck() {
        statusMessage = "Checking health…"
        
        guard let url = URL(string: "\(backendURL)/health") else { return }
        
        URLSession.shared.dataTask(with: URLRequest(url: url)) { _, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    self.statusMessage = "Error: \(error.localizedDescription)"
                    return
                }
                let status = (response as? HTTPURLResponse)?.statusCode ?? -1
                self.statusMessage = status == 200 ? "Backend is healthy" : "Backend error: \(status)"
            }
        }.resume()
    }
    
    private func testCalendar() {
        guard credentials.hasGoogleCredentials else {
            statusMessage = "Connect Google Calendar first"
            return
        }
        
        statusMessage = "Creating test event…"
        
        guard let url = URL(string: "\(backendURL)/google/test-event") else { return }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        if let googleTokensJSON = credentials.googleTokensJSON {
            request.setValue(googleTokensJSON, forHTTPHeaderField: "X-Google-Tokens")
        }
        
        URLSession.shared.dataTask(with: request) { data, _, error in
            DispatchQueue.main.async {
                if let error = error {
                    self.statusMessage = "Error: \(error.localizedDescription)"
                    return
                }
                
                if let data = data,
                   let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                    if let error = json["error"] as? String {
                        self.statusMessage = "Error: \(error)"
                    } else {
                        self.statusMessage = "Test event created"
                    }
                }
            }
        }.resume()
    }
}
