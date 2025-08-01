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
        self.active_keys = set()  # Track currently pressed keys for gaming
        
        # Get virtual screen dimensions for multi-monitor support
        self.virtual_screen_width = win32api.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        self.virtual_screen_height = win32api.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
        self.virtual_screen_left = win32api.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        self.virtual_screen_top = win32api.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
        
        # Track last valid position to prevent wild jumps
        self.last_valid_x = None
        self.last_valid_y = None
        self.key_durations = {}  # Track expected key durations
        
        # Load config values with error handling
        self._load_config()
    
    def _load_config(self):
        """Safely load config values with default fallbacks"""
        config_defaults = {
            "playback_speed": 1.0,
            "jitter_amount": 0.5,  # Reduced from 2.0 for less wiggling
            "hover_delay": 0.15,   # Reduced from 0.3 for more responsive clicks
            "human_like_mouse": True,
            "mouse_acceleration": 0.7,
            "micro_jitter": 0.1,   # Reduced from 0.2 for less wiggling
            "path_smoothing": 0.5,
            "gaming_mode": False
        }
        
        for key, default in config_defaults.items():
            try:
                value = self.config.get(key)
                setattr(self, key, value)
            except (KeyError, TypeError):
                setattr(self, key, default)
    
    def play(self, recording_data):
        if self.is_playing: return
        self.is_playing = True
        
        # Extract recording data
        virtual_screen = recording_data.get("virtual_screen", {})
        events = recording_data.get("events", [])
        
        # Handle gaming mode from recording data or config
        if "gaming_mode" in recording_data:
            self.gaming_mode = recording_data["gaming_mode"]
        else:
            try:
                self.gaming_mode = self.config.get("gaming_mode")
            except (KeyError, TypeError):
                self.gaming_mode = False
        
        # Adjust for different gaming mode settings if needed
        if self.gaming_mode:
            # For gaming, use more direct mouse movements and precise timing
            self.path_smoothing = max(0.3, self.path_smoothing)
            self.mouse_acceleration = min(0.6, self.mouse_acceleration)
            self.micro_jitter = min(0.05, self.micro_jitter)  # Even less jitter for gaming
            self.hover_delay = min(0.05, self.hover_delay)
        
        start_time = time.perf_counter()
        last_timestamp = 0
        
        # FIX: Don't set initial position from current cursor
        # Instead, wait for first move event
        self.last_valid_x = None
        self.last_valid_y = None
        
        try:
            for i, event in enumerate(events):
                if not self.is_playing: break
                
                # Calculate delay with microsecond precision
                current_time = time.perf_counter() - start_time
                event_time = event[-1] / self.playback_speed
                delay = event_time - last_timestamp
                
                # Handle key durations separately
                if event[0] == "key_duration":
                    key = event[1].lower()
                    self.key_durations[key] = event[2] / self.playback_speed
                    continue
                
                # Add human-like variation (1-5ms) but less for gaming
                variation = 0.002 if not self.gaming_mode else 0.001  # Reduced variation
                if delay > 0.01:
                    delay += np.random.uniform(-variation, variation)
                    precise_sleep(max(0, delay))
                last_timestamp = event_time
                
                # Process event with precision timing
                if event[0] == "move":
                    rel_x, rel_y = event[1], event[2]
                    # Validate relative coordinates
                    rel_x = max(0.0, min(1.0, rel_x))
                    rel_y = max(0.0, min(1.0, rel_y))
                    
                    # Convert to current screen coordinates
                    x = int(self.virtual_screen_left + rel_x * self.virtual_screen_width)
                    y = int(self.virtual_screen_top + rel_y * self.virtual_screen_height)
                    
                    # CRITICAL FIX: Check for wild jumps and correct them
                    if self.last_valid_x is not None and self.last_valid_y is not None:
                        distance = math.sqrt((rel_x - self.last_valid_x)**2 + (rel_y - self.last_valid_y)**2)
                        # If jump is more than 50% of screen (likely error)
                        if distance > 0.5:  
                            # Move in smaller steps toward target
                            self._gradual_move(self.last_valid_x, self.last_valid_y, rel_x, rel_y)
                        else:
                            if self.human_like_mouse:
                                # Human-like mouse movement with path smoothing
                                self._human_like_move(self.last_valid_x, self.last_valid_y, rel_x, rel_y)
                            else:
                                # Standard movement with subtle jitter
                                if self.jitter > 0:
                                    # Add small, natural jitter (less for gaming)
                                    jitter_amount = 0.002 if self.gaming_mode else 0.005
                                    rel_x += np.random.uniform(-jitter_amount, jitter_amount)
                                    rel_y += np.random.uniform(-jitter_amount, jitter_amount)
                                    rel_x = max(0.0, min(1.0, rel_x))
                                    rel_y = max(0.0, min(1.0, rel_y))
                                
                                # Convert to absolute coordinates for final move
                                x = int(self.virtual_screen_left + rel_x * self.virtual_screen_width)
                                y = int(self.virtual_screen_top + rel_y * self.virtual_screen_height)
                                self._move_mouse(x, y)
                    else:
                        # First move event - just go directly to position
                        self._move_mouse(x, y)
                    
                    # Update last valid position
                    self.last_valid_x, self.last_valid_y = rel_x, rel_y
                
                elif event[0] == "click":
                    rel_x, rel_y = event[1], event[2]
                    button, pressed = event[3], event[4]
                    
                    # Validate relative coordinates
                    rel_x = max(0.0, min(1.0, rel_x))
                    rel_y = max(0.0, min(1.0, rel_y))
                    
                    # Convert to current screen coordinates
                    x = int(self.virtual_screen_left + rel_x * self.virtual_screen_width)
                    y = int(self.virtual_screen_top + rel_y * self.virtual_screen_height)
                    
                    # FIX: Ensure we're at the click position before clicking
                    if self.last_valid_x is None or self.last_valid_y is None:
                        self._move_mouse(x, y)
                        self.last_valid_x, self.last_valid_y = rel_x, rel_y
                    
                    if pressed:
                        # Move to click position first (with validation)
                        if self.last_valid_x is None or self.last_valid_y is None:
                            self._move_mouse(x, y)
                            self.last_valid_x, self.last_valid_y = rel_x, rel_y
                        elif self.human_like_mouse:
                            self._human_like_move(self.last_valid_x, self.last_valid_y, rel_x, rel_y)
                        else:
                            self._move_mouse(x, y)
                        
                        # Update position after move
                        self.last_valid_x, self.last_valid_y = rel_x, rel_y
                        
                        # FIX: Add consistent delay after moving to ensure mouse is settled
                        precise_sleep(0.05)
                        
                        # FIX: Reduce random variation in hover delay for consistency
                        hover_delay = self.hover_delay * 0.9  # Using 90% consistently
                        precise_sleep(hover_delay)
                        
                        self._mouse_down(x, y, button)
                    else:
                        # FIX: Add small consistent delay before releasing
                        precise_sleep(0.02)
                        self._mouse_up(x, y, button)
                
                elif event[0] == "scroll":
                    rel_x, rel_y = event[1], event[2]
                    dx, dy = event[3], event[4]
                    
                    # Validate relative coordinates
                    rel_x = max(0.0, min(1.0, rel_x))
                    rel_y = max(0.0, min(1.0, rel_y))
                    
                    # Convert to current screen coordinates
                    x = int(self.virtual_screen_left + rel_x * self.virtual_screen_width)
                    y = int(self.virtual_screen_top + rel_y * self.virtual_screen_height)
                    
                    self._scroll(x, y, dx, dy)
                
                elif "key_press" in event[0]:
                    key = event[1].lower()
                    self._key_press(key)
                    self.active_keys.add(key)
                    
                    # Hold key for exact duration if available
                    if key in self.key_durations:
                        precise_sleep(self.key_durations[key])
                        if key in self.active_keys:
                            self._key_release(key)
                            self.active_keys.remove(key)
                        del self.key_durations[key]
                
                elif "key_release" in event[0] and event[1].lower() not in self.key_durations:
                    key = event[1].lower()
                    if key in self.active_keys:
                        self._key_release(key)
                        self.active_keys.remove(key)
        finally:
            self.is_playing = False
    
    def _gradual_move(self, start_rel_x, start_rel_y, end_rel_x, end_rel_y):
        """Move mouse in smaller steps to prevent wild jumps"""
        # Calculate the direction vector
        dx = end_rel_x - start_rel_x
        dy = end_rel_y - start_rel_y
        distance = math.sqrt(dx*dx + dy*dy)
        if distance == 0:
            return
        
        # Normalize the direction vector
        dx /= distance
        dy /= distance
        
        # Move in smaller steps (max 10% of screen at a time)
        step_size = min(0.1, distance)
        steps = int(distance / step_size)
        
        for i in range(1, steps + 1):
            rel_x = start_rel_x + dx * step_size * i
            rel_y = start_rel_y + dy * step_size * i
            
            # Validate coordinates
            rel_x = max(0.0, min(1.0, rel_x))
            rel_y = max(0.0, min(1.0, rel_y))
            
            # Convert to absolute coordinates
            x = int(self.virtual_screen_left + rel_x * self.virtual_screen_width)
            y = int(self.virtual_screen_top + rel_y * self.virtual_screen_height)
            
            # Move to this intermediate point
            if self.human_like_mouse:
                self._human_like_move(start_rel_x + dx * step_size * (i-1), 
                                     start_rel_y + dy * step_size * (i-1),
                                     rel_x, rel_y)
            else:
                self._move_mouse(x, y)
            
            # Small delay between steps (faster for gaming)
            delay = 0.02 if self.gaming_mode else 0.03
            precise_sleep(delay)
        
        # Final adjustment to exact position
        if self.human_like_mouse:
            self._human_like_move(start_rel_x + dx * step_size * steps, 
                                 start_rel_y + dy * step_size * steps,
                                 end_rel_x, end_rel_y)
        else:
            # Convert to absolute coordinates
            x = int(self.virtual_screen_left + end_rel_x * self.virtual_screen_width)
            y = int(self.virtual_screen_top + end_rel_y * self.virtual_screen_height)
            self._move_mouse(x, y)
    
    def _human_like_move(self, start_rel_x, start_rel_y, end_rel_x, end_rel_y):
        """Move mouse from start to end with human-like characteristics"""
        # Calculate relative distance
        distance = math.sqrt((end_rel_x - start_rel_x)**2 + (end_rel_y - start_rel_y)**2)
        
        # Skip human-like movement for very short distances
        if distance < 0.01:
            # Convert to absolute coordinates
            x = int(self.virtual_screen_left + end_rel_x * self.virtual_screen_width)
            y = int(self.virtual_screen_top + end_rel_y * self.virtual_screen_height)
            self._move_mouse(x, y)
            return
        
        # Determine number of intermediate points based on distance
        num_points = max(3, min(25, int(distance * 30)))
        
        # Generate a proper Bezier curve with natural variation
        points = self._generate_bezier_path(start_rel_x, start_rel_y, end_rel_x, end_rel_y, num_points)
        
        # Add micro jitter to path (scaled by distance)
        points = self._add_micro_jitter(points, distance)
        
        # Calculate timing with acceleration/deceleration
        timings = self._calculate_human_timing(num_points, distance)
        
        # Move through each point with proper timing
        for i, (rel_x, rel_y) in enumerate(points):
            # Skip the first point (we're already there)
            if i == 0:
                continue
            
            # Convert to absolute coordinates
            x = int(self.virtual_screen_left + rel_x * self.virtual_screen_width)
            y = int(self.virtual_screen_top + rel_y * self.virtual_screen_height)
            
            self._move_mouse(x, y)
            
            # Sleep according to timing profile
            if i < len(timings):
                precise_sleep(timings[i-1] * self.playback_speed)
    
    def _generate_bezier_path(self, x0, y0, x1, y1, num_points):
        """Generate a smooth Bezier curve path between two points"""
        # Create a control point with slight deviation for more natural movement
        mid_x = (x0 + x1) / 2
        mid_y = (y0 + y1) / 2
        
        # Add controlled deviation based on distance for natural movement
        distance = math.sqrt((x1 - x0)**2 + (y1 - y0)**2)
        # Calculate max deviation (5-15% of distance, less for gaming)
        max_deviation = distance * (0.05 if self.gaming_mode else 0.15)
        max_deviation = min(max_deviation, 0.2)  # Cap at 20% of screen
        
        # Calculate perpendicular direction for deviation
        angle = math.atan2(y1 - y0, x1 - x0) - math.pi/2
        # Random deviation within limits
        deviation = max_deviation * np.random.uniform(-1, 1)
        
        # Calculate control point with deviation
        cx = mid_x + deviation * math.cos(angle)
        cy = mid_y + deviation * math.sin(angle)
        
        # Ensure control point is within reasonable bounds
        cx = max(0.0, min(1.0, cx))
        cy = max(0.0, min(1.0, cy))
        
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
            # Micro jitter gets smaller toward the end
            progress = i / len(points)
            
            # Scale jitter based on distance and gaming mode - REDUCED INTENSITY
            base_intensity = self.micro_jitter * (0.05 if self.gaming_mode else 0.1)
            intensity = base_intensity * (1 - progress * 0.7)
            
            # Only add jitter if it won't cause wild movement
            if i > 0:
                prev_x, prev_y = jittered_points[-1]
                max_jitter = math.sqrt((x - prev_x)**2 + (y - prev_y)**2) * 0.3
                intensity = min(intensity, max_jitter)
            
            # Add subtle variation
            jitter_x = np.random.uniform(-intensity, intensity)
            jitter_y = np.random.uniform(-intensity, intensity)
            
            # Validate coordinates
            new_x = max(0.0, min(1.0, x + jitter_x))
            new_y = max(0.0, min(1.0, y + jitter_y))
            
            jittered_points.append((new_x, new_y))
        return jittered_points
    
    def _calculate_human_timing(self, num_points, distance):
        """Calculate timing profile that mimics human mouse movement"""
        timings = []
        # Base time per percentage of screen (in seconds)
        time_per_percent = 0.08  # Time to move 1% of screen
        
        # Total time for the movement
        total_time = max(0.03, distance * time_per_percent)
        
        # For gaming, movements are faster and more direct
        if self.gaming_mode:
            total_time *= 0.6  # 40% faster for gaming
        
        for i in range(num_points - 1):  # -1 because we skip first point
            # Position along the path (0 to 1)
            t = i / (num_points - 2)
            
            # Create acceleration/deceleration profile
            # For gaming, use more linear profile; otherwise use ease-in-out
            if self.gaming_mode:
                # More linear for gaming (direct movements)
                timing_factor = t
            else:
                # Ease-in-out for regular use
                if t < 0.5:
                    timing_factor = 4 * t * t * t  # Ease in
                else:
                    t_adj = t - 1
                    timing_factor = 4 * t_adj * t_adj * t_adj + 1  # Ease out
            
            # Calculate time for this segment
            if i == 0:
                segment_time = total_time * timing_factor
            else:
                prev_t = (i-1) / (num_points - 2)
                if self.gaming_mode:
                    prev_timing = prev_t
                else:
                    if prev_t < 0.5:
                        prev_timing = 4 * prev_t * prev_t * prev_t
                    else:
                        prev_t_adj = prev_t - 1
                        prev_timing = 4 * prev_t_adj * prev_t_adj * prev_t_adj + 1
                segment_time = total_time * (timing_factor - prev_timing)
            
            # Add natural variation (less for gaming)
            variation = np.random.uniform(-0.02, 0.02) * (0.3 if self.gaming_mode else 1.0)
            segment_time *= (1 + variation)
            
            # Minimum time per segment (faster for gaming)
            min_time = 0.003 if self.gaming_mode else 0.005
            timings.append(max(min_time, segment_time))
        
        return timings
    
    def stop(self):
        self.is_playing = False
        # Release any held keys
        for key in list(self.active_keys):
            self._key_release(key)
        self.active_keys.clear()
        self.key_durations.clear()
    
    # Low-level Windows API calls (mimics real user input)
    def _move_mouse(self, x, y):
        """Move mouse with boundary checking"""
        # Ensure coordinates are within virtual screen bounds
        x = max(self.virtual_screen_left, min(self.virtual_screen_left + self.virtual_screen_width - 1, x))
        y = max(self.virtual_screen_top, min(self.virtual_screen_top + self.virtual_screen_height - 1, y))
        win32api.SetCursorPos((int(x), int(y)))
    
    def _mouse_down(self, x, y, button):
        if button == "left":
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        elif button == "right":
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTDOWN, x, y, 0, 0)
        elif button == "middle":
            win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEDOWN, x, y, 0, 0)
    
    def _mouse_up(self, x, y, button):
        if button == "left":
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
        elif button == "right":
            win32api.mouse_event(win32con.MOUSEEVENTF_RIGHTUP, x, y, 0, 0)
        elif button == "middle":
            win32api.mouse_event(win32con.MOUSEEVENTF_MIDDLEUP, x, y, 0, 0)
    
    def _scroll(self, x, y, dx, dy):
        win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, x, y, int(dy * 120), 0)
    
    def _key_press(self, key):
        # Normalize WASD keys for consistent handling
        normalized_key = key.lower()
        if normalized_key in ['w', 'a', 's', 'd']:
            key = normalized_key
            
        if len(key) == 1:  # Character key
            # FIX: Direct virtual key codes for WASD to ensure game compatibility
            if key == 'w':
                vk = 0x57  # Direct virtual key code for W
            elif key == 'a':
                vk = 0x41  # Direct virtual key code for A
            elif key == 's':
                vk = 0x53  # Direct virtual key code for S
            elif key == 'd':
                vk = 0x44  # Direct virtual key code for D
            else:
                vk = win32api.VkKeyScan(key)
            win32api.keybd_event(vk, 0, 0, 0)
        else:  # Special key
            # Handle pynput key names
            key_name = key.replace('Key.', '').replace("'", "").lower()
            vk = self._get_virtual_key_code(key_name)
            if vk:
                win32api.keybd_event(vk, 0, 0, 0)
    
    def _key_release(self, key):
        # Normalize WASD keys for consistent handling
        normalized_key = key.lower()
        if normalized_key in ['w', 'a', 's', 'd']:
            key = normalized_key
            
        if len(key) == 1:
            # FIX: Direct virtual key codes for WASD to ensure game compatibility
            if key == 'w':
                vk = 0x57  # Direct virtual key code for W
            elif key == 'a':
                vk = 0x41  # Direct virtual key code for A
            elif key == 's':
                vk = 0x53  # Direct virtual key code for S
            elif key == 'd':
                vk = 0x44  # Direct virtual key code for D
            else:
                vk = win32api.VkKeyScan(key)
            win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
        else:
            key_name = key.replace('Key.', '').replace("'", "").lower()
            vk = self._get_virtual_key_code(key_name)
            if vk:
                win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
    
    def _get_virtual_key_code(self, key_name):
        """Map key names to Windows virtual key codes"""
        key_map = {
            'enter': win32con.VK_RETURN,
            'esc': win32con.VK_ESCAPE,
            'escape': win32con.VK_ESCAPE,
            'space': win32con.VK_SPACE,
            'tab': win32con.VK_TAB,
            'backspace': win32con.VK_BACK,
            'delete': win32con.VK_DELETE,
            'del': win32con.VK_DELETE,
            'insert': win32con.VK_INSERT,
            'home': win32con.VK_HOME,
            'end': win32con.VK_END,
            'pageup': win32con.VK_PRIOR,
            'pagedown': win32con.VK_NEXT,
            'up': win32con.VK_UP,
            'down': win32con.VK_DOWN,
            'left': win32con.VK_LEFT,
            'right': win32con.VK_RIGHT,
            'f1': win32con.VK_F1,
            'f2': win32con.VK_F2,
            'f3': win32con.VK_F3,
            'f4': win32con.VK_F4,
            'f5': win32con.VK_F5,
            'f6': win32con.VK_F6,
            'f7': win32con.VK_F7,
            'f8': win32con.VK_F8,
            'f9': win32con.VK_F9,
            'f10': win32con.VK_F10,
            'f11': win32con.VK_F11,
            'f12': win32con.VK_F12,
            'shift': win32con.VK_SHIFT,
            'ctrl': win32con.VK_CONTROL,
            'control': win32con.VK_CONTROL,
            'alt': win32con.VK_MENU,
            'capslock': win32con.VK_CAPITAL,
            'numlock': win32con.VK_NUMLOCK,
            'scrolllock': win32con.VK_SCROLL,
            'pause': win32con.VK_PAUSE,
            'print_screen': win32con.VK_SNAPSHOT,
            'win': win32con.VK_LWIN,
            'command': win32con.VK_LWIN,
            'cmd': win32con.VK_LWIN,
            'w': 0x57,  # 'W' key
            'a': 0x41,  # 'A' key
            's': 0x53,  # 'S' key
            'd': 0x44,  # 'D' key
        }
        return key_map.get(key_name, 0)