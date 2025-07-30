import json
import os

class Config:
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), "config.json")
        self.default = {
            "always_on_top": True,
            "playback_speed": 1.0,
            "jitter_amount": 1,  # Reduced from 2 for less extreme jitter
            "hover_delay": 0.3,
            "human_like_mouse": True,
            "mouse_acceleration": 0.5,  # Reduced from 0.7 for less extreme acceleration
            "micro_jitter": 0.5,        # Reduced from 1.0 for less wiggle
            "path_smoothing": 0.5,      # Adjusted for better balance
            "start_key": "[",
            "stop_key": "]",
            "repeat_enabled": False,
            "repeat_infinite": True,
            "repeat_count": 5
        }
        self.load()
    
    def load(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    self.settings = json.load(f)
                # Merge with defaults (add new keys)
                for k, v in self.default.items():
                    if k not in self.settings:
                        self.settings[k] = v
            else:
                self.settings = self.default.copy()
                self.save()
        except:
            self.settings = self.default.copy()
    
    def save(self):
        with open(self.config_path, 'w') as f:
            json.dump(self.settings, f, indent=2)
    
    def get(self, key):
        return self.settings.get(key, self.default[key])
    
    def set(self, key, value):
        self.settings[key] = value
        self.save()