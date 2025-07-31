import time
import numpy as np
from pynput import mouse, keyboard
from config import Config
import win32api  # Added to get screen resolution
import win32con

class Recorder:
    def __init__(self):
        self.config = Config()
        self.events = []
        self.is_recording = False
        self.start_time = 0
        self.mouse_listener = None
        self.keyboard_listener = None
        self.key_press_times = {}  # Track exact press durations
        # Store screen resolution when recording starts
        self.recorded_width = win32api.GetSystemMetrics(0)
        self.recorded_height = win32api.GetSystemMetrics(1)
    
    def start(self):
        if self.is_recording: return
        self.is_recording = True
        self.events = []
        self.key_press_times = {}
        self.start_time = time.perf_counter()  # MICROSECOND PRECISION
        
        # Capture current screen resolution when starting recording
        self.recorded_width = win32api.GetSystemMetrics(0)
        self.recorded_height = win32api.GetSystemMetrics(1)
        
        self.mouse_listener = mouse.Listener(
            on_move=self.on_move,
            on_click=self.on_click,
            on_scroll=self.on_scroll
        )
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        )
        self.mouse_listener.start()
        self.keyboard_listener.start()
    
    def stop(self):
        if not self.is_recording: return
        self.is_recording = False
        if self.mouse_listener:
            self.mouse_listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        
        # Add missing key releases (if stopped mid-press)
        for key, press_time in self.key_press_times.items():
            timestamp = time.perf_counter() - self.start_time
            self.events.append(("key_release", str(key), timestamp))
    
    def on_move(self, x, y):
        if not self.is_recording: return
        timestamp = time.perf_counter() - self.start_time
        # Store resolution info with the first move event
        if not self.events or self.events[-1][0] != "move":
            self.events.append(("move", x, y, (self.recorded_width, self.recorded_height), timestamp))
        else:
            self.events.append(("move", x, y, timestamp))
    
    def on_click(self, x, y, button, pressed):
        if not self.is_recording: return
        timestamp = time.perf_counter() - self.start_time
        self.events.append(("click", x, y, button.name, pressed, timestamp))
    
    def on_scroll(self, x, y, dx, dy):
        if not self.is_recording: return
        timestamp = time.perf_counter() - self.start_time
        self.events.append(("scroll", x, y, dx, dy, timestamp))
    
    def on_press(self, key):
        if not self.is_recording: return
        timestamp = time.perf_counter() - self.start_time
        self.key_press_times[key] = timestamp  # Track exact press time
        try:
            self.events.append(("key_press", key.char, timestamp))
        except AttributeError:
            self.events.append(("key_press", str(key), timestamp))
    
    def on_release(self, key):
        if not self.is_recording: return
        timestamp = time.perf_counter() - self.start_time
        # Calculate exact press duration
        if key in self.key_press_times:
            duration = timestamp - self.key_press_times[key]
            self.events.append(("key_duration", str(key), duration))
            del self.key_press_times[key]
        
        try:
            self.events.append(("key_release", key.char, timestamp))
        except AttributeError:
            self.events.append(("key_release", str(key), timestamp))
    
    def save_recording(self, filename):
        """Save the recorded events to a file"""
        import json
        with open(filename, 'w') as f:
            json.dump(self.events, f)
        return len(self.events)