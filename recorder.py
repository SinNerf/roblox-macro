import math
import time
import numpy as np
from pynput import mouse, keyboard
from config import Config
import win32api
import win32con

class Recorder:
    def __init__(self):
        self.config = Config()
        self.events = []
        self.is_recording = False
        self.start_time = 0
        self.mouse_listener = None
        self.keyboard_listener = None
        self.key_press_times = {}  # Track exact press times
        self.active_keys = set()  # Track currently pressed keys
        
        # Get virtual screen dimensions for multi-monitor support
        self.virtual_screen_width = win32api.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        self.virtual_screen_height = win32api.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
        self.virtual_screen_left = win32api.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        self.virtual_screen_top = win32api.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
        
        # FIX: Handle default values properly for Config.get()
        try:
            self.gaming_mode = self.config.get("gaming_mode")
        except (KeyError, TypeError):
            self.gaming_mode = False
    
    def start(self):
        if self.is_recording: return
        self.is_recording = True
        self.events = []
        self.key_press_times = {}
        self.active_keys = set()
        self.start_time = time.perf_counter()  # MICROSECOND PRECISION
        
        # Capture virtual screen dimensions for multi-monitor support
        self.virtual_screen_width = win32api.GetSystemMetrics(78)
        self.virtual_screen_height = win32api.GetSystemMetrics(79)
        self.virtual_screen_left = win32api.GetSystemMetrics(76)
        self.virtual_screen_top = win32api.GetSystemMetrics(77)
        
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
        
        # Release any keys still pressed
        for key in list(self.active_keys):
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
            self.active_keys.discard(key)
    
    def on_move(self, x, y):
        if not self.is_recording: return
    
        # Convert to relative coordinates (0-1 range) within virtual screen
        rel_x = (x - self.virtual_screen_left) / self.virtual_screen_width
        rel_y = (y - self.virtual_screen_top) / self.virtual_screen_height
        
        # Validate coordinates are within virtual screen bounds
        rel_x = max(0.0, min(1.0, rel_x))
        rel_y = max(0.0, min(1.0, rel_y))
        
        # Skip if this is too close to the last position (reduces noise)
        if self.events and self.events[-1][0] == "move":
            last_rel_x, last_rel_y = self.events[-1][1], self.events[-1][2]
            distance = math.sqrt((rel_x - last_rel_x)**2 + (rel_y - last_rel_y)**2)
            # Only record if moved at least 1% of screen distance
            if distance < 0.01:  
                return
            
        timestamp = time.perf_counter() - self.start_time
        self.events.append(("move", rel_x, rel_y, timestamp))
    
    def on_click(self, x, y, button, pressed):
        if not self.is_recording: return
        
        # Convert to relative coordinates
        rel_x = (x - self.virtual_screen_left) / self.virtual_screen_width
        rel_y = (y - self.virtual_screen_top) / self.virtual_screen_height
        
        # Validate coordinates
        rel_x = max(0.0, min(1.0, rel_x))
        rel_y = max(0.0, min(1.0, rel_y))
        
        timestamp = time.perf_counter() - self.start_time
        self.events.append(("click", rel_x, rel_y, button.name, pressed, timestamp))
    
    def on_scroll(self, x, y, dx, dy):
        if not self.is_recording: return
        
        # Convert to relative coordinates
        rel_x = (x - self.virtual_screen_left) / self.virtual_screen_width
        rel_y = (y - self.virtual_screen_top) / self.virtual_screen_height
        
        # Validate coordinates
        rel_x = max(0.0, min(1.0, rel_x))
        rel_y = max(0.0, min(1.0, rel_y))
        
        timestamp = time.perf_counter() - self.start_time
        self.events.append(("scroll", rel_x, rel_y, dx, dy, timestamp))
    
    def on_press(self, key):
        if not self.is_recording: return
        
        # Track active keys for gaming
        self.active_keys.add(key)
        
        timestamp = time.perf_counter() - self.start_time
        self.key_press_times[key] = timestamp  # Track exact press time
        
        # Normalize WASD keys for consistent handling
        key_str = str(key).lower()
        if key_str in ["'w'", "'a'", "'s'", "'d'"]:
            key_str = key_str[1]  # Extract the actual letter
            
        try:
            self.events.append(("key_press", key.char.lower(), timestamp))
        except AttributeError:
            self.events.append(("key_press", key_str, timestamp))
    
    def on_release(self, key):
        if not self.is_recording: return
        
        timestamp = time.perf_counter() - self.start_time
        # Calculate exact press duration
        if key in self.key_press_times:
            duration = timestamp - self.key_press_times[key]
            key_str = str(key).lower()
            if key_str in ["'w'", "'a'", "'s'", "'d'"]:
                key_str = key_str[1]
            self.events.append(("key_duration", key_str, duration))
            del self.key_press_times[key]
        
        self.active_keys.discard(key)
        
        try:
            self.events.append(("key_release", key.char.lower(), timestamp))
        except AttributeError:
            key_str = str(key).lower()
            if key_str in ["'w'", "'a'", "'s'", "'d'"]:
                key_str = key_str[1]
            self.events.append(("key_release", key_str, timestamp))
    
    def save_recording(self, filename):
        """Save the recorded events to a file with virtual screen info"""
        import json
        recording_data = {
            "virtual_screen": {
                "width": self.virtual_screen_width,
                "height": self.virtual_screen_height,
                "left": self.virtual_screen_left,
                "top": self.virtual_screen_top
            },
            "events": self.events,
            "gaming_mode": self.gaming_mode
        }
        with open(filename, 'w') as f:
            json.dump(recording_data, f)
        return len(self.events)