//
//  ScreenshotTrigger.swift
//  ScreenSnapAI
//
//  Created by Maximilian Glasmacher on 28.11.25.
//

import SwiftUI
import Combine

// Observable object to trigger screenshots from menu bar
class ScreenshotTrigger: ObservableObject {
    @Published var shouldTakeScreenshot = false
    
    func trigger() {
        shouldTakeScreenshot = true
        // Reset after a brief moment
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            self.shouldTakeScreenshot = false
        }
    }
}

