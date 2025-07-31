import time
import win32api
import win32con
import numpy as np
from config import Config
import ctypes
import math
# High-precision sleep function (better than time.sleep)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.QueryPerformanceCounter.argtypes = [ctypes.POINTER(ctypes.c_int64)]
kernel32.QueryPerformanceFrequency.argtypes = [ctypes.POINTER(ctypes.c_int64)]
def precise_sleep(duration):
    """Sleep with 0.001 second precision"""
    if duration <= 0: return
    start = ctypes.c_int64()
    freq = ctypes.c_int64()
    kernel32.QueryPerformanceCounter(ctypes.byref(start))
    kernel32.QueryPerformanceFrequency(ctypes.byref(freq))
    target = start.value + int(duration * freq.value)
    while True:
        now = ctypes.c_int64()
        kernel32.QueryPerformanceCounter(ctypes.byref(now))
        if now.value >= target:
            break

class Player:
    def __init__(self):
        self.config = Config()
        self.is_playing = False
        self.playback_speed = self.config.get("playback_speed")
        self.jitter = self.config.get("jitter_amount")
        self.hover_delay = self.config.get("hover_delay")
        self.human_like_mouse = self.config.get("human_like_mouse")
        self.mouse_acceleration = self.config.get("mouse_acceleration")
        self.micro_jitter = self.config.get("micro_jitter")
        self.path_smoothing = self.config.get("path_smoothing")
        self.key_durations = {}  # Track expected key durations
        # Default to common desktop resolution as fallback
        self.recorded_width, self.recorded_height = 1920, 1080

    def set_recorded_resolution(self, width, height):
        """Set the screen resolution used during recording"""
        self.recorded_width, self.recorded_height = width, height

    def scale_coordinates(self, x, y):
        """Scale coordinates from recorded resolution to current screen resolution"""
        current_width = win32api.GetSystemMetrics(0)
        current_height = win32api.GetSystemMetrics(1)
        
        # Only scale if resolutions are different
        if (current_width != self.recorded_width or 
            current_height != self.recorded_height):
            x_scaled = int((x / self.recorded_width) * current_width)
            y_scaled = int((y / self.recorded_height) * current_height)
            return x_scaled, y_scaled
        return x, y

    def play(self, events):
        if self.is_playing: return
        self.is_playing = True
        start_time = time.perf_counter()
        last_timestamp = 0
        
        # Get current screen resolution
        current_width = win32api.GetSystemMetrics(0)
        current_height = win32api.GetSystemMetrics(1)
        
        # Try to determine recorded resolution from first move event
        for event in events:
            if event[0] == "move" and len(event) > 3:  # If event contains resolution info
                if isinstance(event[3], tuple) and len(event[3]) == 2:  # resolution is stored as (width, height)
                    self.recorded_width, self.recorded_height = event[3]
                    break
        
        last_x, last_y = win32api.GetCursorPos()  # Start from current position
        try:
            for i, event in enumerate(events):
                if not self.is_playing: break
                # Calculate delay with microsecond precision
                current_time = time.perf_counter() - start_time
                event_time = event[-1] / self.playback_speed
                delay = (event_time - last_timestamp) * self.playback_speed
                # Handle key durations separately
                if event[0] == "key_duration":
                    self.key_durations[event[1]] = event[2] / self.playback_speed
                    continue
                # Add human-like variation (1-5ms)
                if delay > 0.01:
                    delay += np.random.uniform(-0.005, 0.005)  # 5ms variation
                    precise_sleep(max(0, delay))
                last_timestamp = event_time
                # Process event with precision timing
                if event[0] == "move":
                    x, y = event[1], event[2]
                    
                    # Scale coordinates to current screen resolution
                    x, y = self.scale_coordinates(x, y)
                    
                    if self.human_like_mouse:
                        # Human-like mouse movement with path smoothing
                        self._human_like_move(last_x, last_y, x, y)
                    else:
                        # Standard movement with subtle jitter
                        if self.jitter > 0:
                            # Add small, natural jitter
                            x += np.random.uniform(-0.5, 0.5)
                            y += np.random.uniform(-0.5, 0.5)
                        self._move_mouse(int(x), int(y))
                    last_x, last_y = x, y
                elif event[0] == "click":
                    x, y, button, pressed = event[1], event[2], event[3], event[4]
                    # Scale click coordinates
                    x, y = self.scale_coordinates(x, y)
                    if pressed:
                        # Simulate natural hover delay
                        precise_sleep(np.random.uniform(
                            self.hover_delay * 0.8, 
                            self.hover_delay * 1.2
                        ))
                        self._mouse_down(x, y, button)
                    else:
                        self._mouse_up(x, y, button)
                elif event[0] == "scroll":
                    x, y, dx, dy = event[1], event[2], event[3], event[4]
                    # Scale scroll coordinates
                    x, y = self.scale_coordinates(x, y)
                    self._scroll(x, y, dx, dy)
                elif "key_press" in event[0]:
                    key = event[1]
                    self._key_press(key)
                    # Hold key for exact duration if available
                    if key in self.key_durations:
                        precise_sleep(self.key_durations[key])
                        self._key_release(key)
                        del self.key_durations[key]
                elif "key_release" in event[0] and event[1] not in self.key_durations:
                    self._key_release(event[1])
        finally:
            self.is_playing = False
    
    def _human_like_move(self, start_x, start_y, end_x, end_y):
        """Move mouse from start to end with human-like characteristics"""
        # Calculate distance
        distance = math.sqrt((end_x - start_x)**2 + (end_y - start_y)**2)
    
        # Skip human-like movement for very short distances (prevents jitter)
        if distance < 5:
            self._move_mouse(int(end_x), int(end_y))
            return
        
        # Determine number of intermediate points based on distance
        num_points = max(3, min(20, int(distance / 8)))
    
        # Generate smooth path with Bezier curve
        points = self._generate_bezier_path(start_x, start_y, end_x, end_y, num_points, distance)
    
        # Add micro jitter to path (scaled by distance)
        points = self._add_micro_jitter(points, distance)
    
        # Calculate timing with acceleration/deceleration
        timings = self._calculate_human_timing(num_points, distance)
    
        # Move through each point with proper timing
        for i, (x, y) in enumerate(points):
            # Skip the first point (we're already there)
            if i == 0:
                continue
            
            self._move_mouse(int(x), int(y))
            # Sleep according to timing profile
            if i < len(timings):
                precise_sleep(timings[i-1] * self.playback_speed)
    
    def _generate_bezier_path(self, x0, y0, x1, y1, num_points, distance):
        """Generate a smooth Bezier curve path between two points"""
        # Control point for the Bezier curve (creates natural arc)
        mid_x = (x0 + x1) / 2
        mid_y = (y0 + y1) / 2
        # Calculate a subtle arc based on distance (larger movements have slightly more arc)
        # Max 10 pixels arc height for natural movement
        arc_height = min(10, max(2, distance * 0.05))
        # Create a natural upward arc (but much more subtle than before)
        cx = mid_x
        cy = mid_y - arc_height
        points = []
        for i in range(num_points + 1):
            t = i / num_points
            # Quadratic Bezier formula
            x = (1-t)**2 * x0 + 2*(1-t)*t * cx + t**2 * x1
            y = (1-t)**2 * y0 + 2*(1-t)*t * cy + t**2 * y1
            points.append((x, y))
        return points
    
    def _add_micro_jitter(self, points, distance):
        """Add subtle, natural variations to the path"""
        if self.micro_jitter <= 0:
            return points
        jittered_points = []
        for i, (x, y) in enumerate(points):
            # Micro jitter gets smaller toward the end (like human precision)
            progress = i / len(points)
            # Scale jitter based on distance (smaller movements have less jitter)
            base_intensity = self.micro_jitter * 0.5
            distance_factor = min(1.0, distance / 50)
            intensity = base_intensity * (1 - progress) * distance_factor
            # Add subtle variation
            jitter_x = np.random.uniform(-intensity, intensity)
            jitter_y = np.random.uniform(-intensity, intensity)
            jittered_points.append((x + jitter_x, y + jitter_y))
        return jittered_points
    
    def _calculate_human_timing(self, num_points, distance):
        """Calculate timing profile that mimics human mouse movement"""
        timings = []
        # Base time per pixel (in seconds)
        time_per_pixel = 0.004
        # Total time for the movement (based on distance)
        total_time = max(0.05, distance * time_per_pixel)
        for i in range(num_points):
            # Create acceleration/deceleration profile
            t = i / num_points
            # S-curve timing (slow at start, fast in middle, slow at end)
            # But much more subtle than before
            timing_factor = 0.5 - 0.3 * math.cos(t * math.pi)
            # Add natural variation to timing (proportional to distance)
            variation = np.random.uniform(-0.03, 0.03) * min(1.0, distance / 100)
            # Calculate time for this segment
            if i == 0:
                segment_time = total_time * (timing_factor + variation) / num_points
            else:
                prev_t = (i-1) / num_points
                prev_timing = 0.5 - 0.3 * math.cos(prev_t * math.pi)
                segment_time = total_time * ((timing_factor + variation) - (prev_timing + variation)) / num_points
            timings.append(max(0.005, segment_time))  # Minimum 5ms per segment
        return timings
    
    def stop(self):
        self.is_playing = False
        # Release any held keys
        for key in list(self.key_durations.keys()):
            self._key_release(key)
        self.key_durations.clear()
    
    # Low-level Windows API calls (mimics real user input)
    def _move_mouse(self, x, y):
        win32api.SetCursorPos((x, y))
    
    def _mouse_down(self, x, y, button):
        if button == "left":
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        elif button == "right":
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, x, y, 0, 0)
    
    def _mouse_up(self, x, y, button):
        if button == "left":
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
        elif button == "right":
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, x, y, 0, 0)
    
    def _scroll(self, x, y, dx, dy):
        win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, x, y, dy * 120, 0)
    
    def _key_press(self, key):
        if len(key) == 1:  # Character key
            vk = win32api.VkKeyScan(key)
            win32api.keybd_event(vk, 0, 0, 0)
        else:  # Special key
            vk = getattr(win32con, f"VK_{key.replace('Key.', '').upper()}", None)
            if vk: win32api.keybd_event(vk, 0, 0, 0)
    
    def _key_release(self, key):
        if len(key) == 1:
            vk = win32api.VkKeyScan(key)
            win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
        else:
            vk = getattr(win32con, f"VK_{key.replace('Key.', '').upper()}", None)
            if vk: win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)