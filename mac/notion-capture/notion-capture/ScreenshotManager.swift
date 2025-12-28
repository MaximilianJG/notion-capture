//
//  ScreenshotManager.swift
//  Notion Capture
//
//  Handles background screenshot capture and upload with credentials
//

import Foundation
import AppKit

class ScreenshotManager {
    static let shared = ScreenshotManager()
    
    private var screenshotProcess: Process?
    private let backendURL = "http://localhost:8000"
    
    private init() {}
    
    private func postStatus(_ message: String) {
        DispatchQueue.main.async {
            NotificationCenter.default.post(
                name: .screenshotStatusUpdate,
                object: nil,
                userInfo: ["message": message]
            )
        }
    }
    
    func takeScreenshot(credentials: CredentialStore? = nil) {
        print("📸 takeScreenshot() called")
        
        DispatchQueue.main.async {
            NotificationCenter.default.post(name: .screenshotStarted, object: nil)
        }
        
        postStatus("Select a region to capture…")
        
        if let existingProcess = screenshotProcess {
            if existingProcess.isRunning {
                print("⚠️ Terminating existing screenshot process")
                existingProcess.terminate()
                existingProcess.waitUntilExit()
            }
            screenshotProcess = nil
        }
        
        let tempDir = FileManager.default.temporaryDirectory
        let screenshotURL = tempDir.appendingPathComponent("screenshot_\(UUID().uuidString).png")
        print("📁 Screenshot will be saved to: \(screenshotURL.path)")
        
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/sbin/screencapture")
        process.arguments = ["-i", "-x", screenshotURL.path]
        let errorPipe = Pipe()
        process.standardError = errorPipe
        screenshotProcess = process
        
        // Capture credentials reference for the closure
        let creds = credentials ?? CredentialStore.shared
        
        process.terminationHandler = { [weak self] process in
            print("📸 Screenshot process terminated with status: \(process.terminationStatus)")
            
            let errorData = errorPipe.fileHandleForReading.readDataToEndOfFile()
            if let errorString = String(data: errorData, encoding: .utf8), !errorString.isEmpty {
                print("⚠️ Screenshot stderr: \(errorString)")
            }
            
            DispatchQueue.main.async {
                self?.screenshotProcess = nil
                
                NotificationCenter.default.post(name: .screenshotCompleted, object: nil)
                
                if process.terminationStatus == 0 {
                    if FileManager.default.fileExists(atPath: screenshotURL.path) {
                        print("✅ Screenshot file exists")
                        if let imageData = try? Data(contentsOf: screenshotURL) {
                            print("✅ Screenshot data loaded: \(imageData.count) bytes")
                            self?.postStatus("Screenshot captured. Analyzing…")
                            self?.sendScreenshotToBackend(imageData: imageData, credentials: creds)
                        } else {
                            print("❌ Failed to read screenshot data")
                            self?.postStatus("Error: Could not read screenshot file")
                            self?.resetToReady(after: 3)
                        }
                    } else {
                        print("❌ Screenshot file does not exist (user may have cancelled)")
                        self?.postStatus("Screenshot cancelled")
                        self?.resetToReady(after: 2)
                    }
                    try? FileManager.default.removeItem(at: screenshotURL)
                } else {
                    print("❌ Screenshot cancelled or failed (status: \(process.terminationStatus))")
                    self?.postStatus("Screenshot cancelled")
                    self?.resetToReady(after: 2)
                    try? FileManager.default.removeItem(at: screenshotURL)
                }
            }
        }
        
        do {
            try process.run()
            print("✅ Screenshot process started")
        } catch {
            print("❌ Error starting screenshot: \(error.localizedDescription)")
            postStatus("Error: Could not start screenshot")
            resetToReady(after: 3)
            screenshotProcess = nil
        }
    }
    
    private func resetToReady(after seconds: Double) {
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds) { [weak self] in
            self?.postStatus("Ready")
        }
    }
    
    private func sendScreenshotToBackend(imageData: Data, credentials: CredentialStore) {
        print("📤 Sending screenshot to backend...")
        postStatus("Analyzing with AI…")
        
        guard let url = URL(string: "\(backendURL)/upload-screenshot") else {
            print("❌ Invalid backend URL")
            postStatus("Error: Invalid backend URL")
            resetToReady(after: 3)
            return
        }
        
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 60
        
        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        
        // Add credentials as headers
        if credentials.hasNotionCredentials {
            request.setValue(credentials.notionApiKey, forHTTPHeaderField: "X-Notion-Api-Key")
            request.setValue(credentials.notionSelectedPageId, forHTTPHeaderField: "X-Notion-Page-Id")
        }
        if let googleTokensJSON = credentials.googleTokensJSON {
            request.setValue(googleTokensJSON, forHTTPHeaderField: "X-Google-Tokens")
        }
        
        var body = Data()
        
        // Add image data
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"screenshot\"; filename=\"screenshot.png\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: image/png\r\n\r\n".data(using: .utf8)!)
        body.append(imageData)
        body.append("\r\n".data(using: .utf8)!)
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)
        
        request.httpBody = body
        print("📤 Request body size: \(body.count) bytes")
        
        let task = URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            if let error = error {
                print("❌ Error uploading screenshot: \(error.localizedDescription)")
                if error.localizedDescription.contains("Could not connect") {
                    self?.postStatus("Error: Backend server not running")
                } else {
                    self?.postStatus("Error: \(error.localizedDescription)")
                }
                self?.resetToReady(after: 4)
                return
            }
            
            if let httpResponse = response as? HTTPURLResponse {
                print("📥 Response status: \(httpResponse.statusCode)")
                
                if httpResponse.statusCode == 200 {
                    print("✅ Screenshot uploaded successfully")
                    
                    if let data = data {
                        self?.handleSuccessResponse(data: data)
                    } else {
                        self?.postStatus("Capture processed")
                        self?.resetToReady(after: 2)
                    }
                    
                    DispatchQueue.main.async {
                        NotificationCenter.default.post(
                            name: .screenshotUploaded,
                            object: nil,
                            userInfo: data != nil ? ["responseData": data!] : nil
                        )
                    }
                } else {
                    print("❌ Failed to upload screenshot: HTTP \(httpResponse.statusCode)")
                    if let data = data, let errorString = String(data: data, encoding: .utf8) {
                        print("❌ Error response: \(errorString)")
                    }
                    self?.postStatus("Error: Server returned status \(httpResponse.statusCode)")
                    self?.resetToReady(after: 3)
                }
            }
        }
        
        task.resume()
    }
    
    private func handleSuccessResponse(data: Data) {
        do {
            if let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] {
                let category = json["category"] as? String ?? "other"
                let title = json["title"] as? String ?? "Untitled"
                
                if category == "event" {
                    let calendarCreated = json["calendar_event_created"] as? Bool ?? false
                    let calendarError = json["calendar_error"] as? String
                    
                    if calendarCreated {
                        postStatus("✓ Event created: \(title)")
                    } else if let error = calendarError, !error.isEmpty {
                        if error.contains("not connected") {
                            postStatus("Connect to Google Calendar first")
                        } else {
                            postStatus("Calendar error: \(error)")
                        }
                    } else {
                        postStatus("Event processing failed")
                    }
                } else {
                    let notionCreated = json["notion_created"] as? Bool ?? false
                    let notionError = json["notion_error"] as? String
                    
                    if notionCreated {
                        if let notionInfo = json["notion_info"] as? [String: Any],
                           let database = notionInfo["database"] as? String {
                            postStatus("✓ Added to \(database)")
                        } else {
                            postStatus("✓ Added to Notion")
                        }
                    } else if let error = notionError, !error.isEmpty {
                        if error.contains("not connected") {
                            postStatus("Connect to Notion first")
                        } else if error.contains("No Notion databases") {
                            postStatus("No databases found in Notion")
                        } else {
                            postStatus("Notion error: \(error)")
                        }
                    } else {
                        postStatus("Capture processed")
                    }
                }
                
                resetToReady(after: 3)
            }
        } catch {
            print("Error parsing response: \(error)")
            postStatus("Capture processed")
            resetToReady(after: 2)
        }
    }
}

// Notifications
extension Notification.Name {
    static let screenshotUploaded = Notification.Name("screenshotUploaded")
    static let screenshotStatusUpdate = Notification.Name("screenshotStatusUpdate")
    static let screenshotStarted = Notification.Name("screenshotStarted")
    static let screenshotCompleted = Notification.Name("screenshotCompleted")
}
