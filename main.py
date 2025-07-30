import os
import time
import dearpygui.dearpygui as dpg
from recorder import Recorder
from player import Player
from config import Config
import json
import traceback
import sys
import base64
from io import BytesIO
from PIL import Image
import threading

# Add this at the VERY TOP of main.py (before any other imports)
if getattr(sys, 'frozen', False):
    # we are running in a bundle
    bundle_dir = sys._MEIPASS
    os.environ['PATH'] = bundle_dir + ';' + os.environ['PATH']
    
    # Add pywin32_system32 to PATH if it exists
    pywin32_path = os.path.join(bundle_dir, 'pywin32_system32')
    if os.path.exists(pywin32_path):
        os.environ['PATH'] = pywin32_path + ';' + os.environ['PATH']

# Create error log function
def log_error():
    error_msg = traceback.format_exc()
    with open("error_log.txt", "w") as f:
        f.write(f"Error occurred at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*50 + "\n")
        f.write(error_msg)
        f.write("\n" + "="*50)
    return error_msg

# Initialize components with error handling
try:
    config = Config()
    recorder = Recorder()
    player = Player()
    recordings_dir = os.path.join(os.path.dirname(__file__), "recordings")
    os.makedirs(recordings_dir, exist_ok=True)
except Exception:
    error_msg = log_error()
    print("Initialization error. Details in error_log.txt")
    print(error_msg)
    input("Press Enter to exit...")
    sys.exit(1)

# Global state
current_recording = None
recording_name = "my_macro"
app_icon_texture = None
title_font = None
header_font = None
body_font = None
small_font = None
is_recording_stopped = False  # Track if recording was stopped to show save dialog
playback_active = False  # Track if playback is active

# UI Constants - SIMPLER COLORS
PRIMARY_COLOR = (60, 120, 200, 255)     # Softer blue
SECONDARY_COLOR = (80, 80, 80, 255)      # Dark gray
SUCCESS_COLOR = (50, 150, 50, 255)       # Muted green
WARNING_COLOR = (180, 120, 0, 255)       # Muted orange
ERROR_COLOR = (180, 60, 60, 255)         # Muted red
BACKGROUND_COLOR = (40, 40, 40, 255)     # Dark gray background
PANEL_COLOR = (50, 50, 50, 255)          # Slightly lighter gray
TEXT_COLOR = (210, 210, 210, 255)        # Light gray text
BORDER_COLOR = (70, 70, 70, 255)         # Border color

def start_recording():
    global current_recording, is_recording_stopped
    recorder.start()
    dpg.set_value("rec_status", "● Recording")
    dpg.configure_item("rec_status", color=ERROR_COLOR)
    dpg.set_value("rec_counter", "0 events")
    dpg.set_value("rec_status_desc", "Recording in progress...")
    is_recording_stopped = False

def save_recording(name):
    """Save the recording with the given name"""
    global current_recording, is_recording_stopped
    
    if not name.strip():
        name = f"macro_{int(time.time())}"
    
    # Save recording
    filename = os.path.join(recordings_dir, f"{name}.json")
    count = recorder.save_recording(filename)
    
    # Update UI
    dpg.set_value("rec_counter", f"{count} events saved")
    dpg.set_value("rec_status_desc", f"Recording saved as '{name}'")
    
    # Refresh recordings list
    refresh_recordings_list()
    
    # Select the new recording
    dpg.set_value("recordings_list", name)
    set_current_recording("recordings_list")
    
    # Close the modal
    dpg.hide_item("save_recording_modal")
    
    # Update global state
    current_recording = name
    is_recording_stopped = False

def cancel_recording():
    """Cancel the recording without saving"""
    global is_recording_stopped
    dpg.set_value("rec_status_desc", "Recording canceled")
    dpg.hide_item("save_recording_modal")
    is_recording_stopped = False

def show_save_dialog():
    """Show the save dialog modal"""
    # Generate a default name based on current time
    default_name = f"macro_{time.strftime('%H%M%S')}"
    dpg.set_value("save_recording_name", default_name)
    
    # Show the modal
    dpg.show_item("save_recording_modal")

def stop_recording():
    global is_recording_stopped
    recorder.stop()
    dpg.set_value("rec_status", "■ Stopped")
    dpg.configure_item("rec_status", color=TEXT_COLOR)
    dpg.set_value("rec_status_desc", "Recording stopped - saving...")
    
    # Set flag to show save dialog
    is_recording_stopped = True
    
    # Show the save dialog
    show_save_dialog()

def delete_recording():
    """Delete the selected recording"""
    global current_recording
    
    if not current_recording:
        dpg.set_value("play_status", "Select a recording to delete")
        dpg.configure_item("play_status", color=WARNING_COLOR)
        return
    
    # Confirm deletion
    dpg.set_value("delete_recording_name", f"Are you sure you want to delete '{current_recording}'?")
    dpg.show_item("delete_recording_modal")

def confirm_delete_recording():
    """Confirm and delete the recording"""
    global current_recording
    
    if not current_recording:
        return
    
    # Delete the file
    filename = os.path.join(recordings_dir, f"{current_recording}.json")
    try:
        os.remove(filename)
        dpg.set_value("play_status", f"Deleted '{current_recording}'")
        dpg.configure_item("play_status", color=SUCCESS_COLOR)
        
        # Reset current recording
        current_recording = None
        dpg.set_value("current_recording_label", "No recording selected")
        dpg.configure_item("current_recording_label", color=WARNING_COLOR)
        
        # Refresh recordings list
        refresh_recordings_list()
    except Exception as e:
        dpg.set_value("play_status", f"Error deleting: {str(e)}")
        dpg.configure_item("play_status", color=ERROR_COLOR)
    
    # Close the modal
    dpg.hide_item("delete_recording_modal")

def cancel_delete_recording():
    """Cancel the deletion"""
    dpg.hide_item("delete_recording_modal")

def play_recording():
    """Play the selected recording with repeat functionality"""
    global current_recording, playback_active
    
    if not current_recording: 
        dpg.set_value("play_status", "Select a recording first")
        dpg.configure_item("play_status", color=WARNING_COLOR)
        return
    
    # Get repeat settings
    repeat_enabled = dpg.get_value("repeat_enabled")
    repeat_infinite = dpg.get_value("repeat_infinite")
    repeat_count = dpg.get_value("repeat_count")
    
    # Update status
    dpg.set_value("play_status", "Playing...")
    dpg.configure_item("play_status", color=SUCCESS_COLOR)
    playback_active = True
    
    # Start playback in a separate thread to avoid blocking UI
    threading.Thread(
        target=play_recording_thread, 
        args=(current_recording, repeat_enabled, repeat_infinite, repeat_count),
        daemon=True
    ).start()

def play_recording_thread(current_recording, repeat_enabled, repeat_infinite, repeat_count):
    """Thread function for playing recordings with repeat functionality"""
    global playback_active
    
    filename = os.path.join(recordings_dir, f"{current_recording}.json")
    
    try:
        with open(filename, 'r') as f:
            events = json.load(f)
        
        # Play once initially
        player.play(events)
        
        # Handle repeat functionality
        if repeat_enabled:
            count = 0
            while (repeat_infinite or count < repeat_count) and playback_active:
                player.play(events)
                count += 1
                time.sleep(0.1)  # Small delay between repeats
                
                # Update status with repeat count
                if not repeat_infinite:
                    dpg.set_value("play_status", f"Playing... ({count}/{repeat_count})")
    
    except Exception as e:
        dpg.set_value("play_status", f"Error: {str(e)}")
        dpg.configure_item("play_status", color=ERROR_COLOR)
    
    # Update status when done
    if playback_active:  # Only if not manually stopped
        dpg.set_value("play_status", "Playback completed")
        dpg.configure_item("play_status", color=SUCCESS_COLOR)
    
    playback_active = False

def stop_playback():
    """Stop the current playback"""
    global playback_active
    player.stop()
    playback_active = False
    dpg.set_value("play_status", "Playback stopped")
    dpg.configure_item("play_status", color=TEXT_COLOR)

def refresh_recordings_list():
    """Refresh the list of available recordings"""
    items = [f[:-5] for f in os.listdir(recordings_dir) if f.endswith('.json')]
    dpg.configure_item("recordings_list", items=items)
    if items:
        dpg.set_value("recordings_list", items[0])
        set_current_recording("recordings_list")

def set_current_recording(sender):
    """Set the currently selected recording"""
    global current_recording
    current_recording = dpg.get_value(sender)
    if current_recording:
        dpg.set_value("current_recording_label", f"Selected: {current_recording}")
        dpg.configure_item("current_recording_label", color=PRIMARY_COLOR)
    else:
        dpg.set_value("current_recording_label", "No recording selected")
        dpg.configure_item("current_recording_label", color=WARNING_COLOR)

def update_mouse_settings():
    """Update mouse-related settings"""
    config.set("mouse_acceleration", dpg.get_value("mouse_acceleration"))
    config.set("micro_jitter", dpg.get_value("micro_jitter"))
    config.set("path_smoothing", dpg.get_value("path_smoothing"))
    
    # Update UI labels
    dpg.set_value("mouse_acceleration_label", f"{config.get('mouse_acceleration'):.1f}")
    dpg.set_value("micro_jitter_label", f"{config.get('micro_jitter'):.1f}px")
    dpg.set_value("path_smoothing_label", f"{config.get('path_smoothing'):.1f}")
    
    # Update player settings
    player.mouse_acceleration = config.get("mouse_acceleration")
    player.micro_jitter = config.get("micro_jitter")
    player.path_smoothing = config.get("path_smoothing")

def update_settings():
    """Update general settings"""
    config.set("always_on_top", dpg.get_value("always_on_top"))
    config.set("playback_speed", dpg.get_value("playback_speed"))
    config.set("jitter_amount", dpg.get_value("jitter_amount"))
    config.set("hover_delay", dpg.get_value("hover_delay"))
    config.set("human_like_mouse", dpg.get_value("human_like_mouse"))
    config.set("repeat_enabled", dpg.get_value("repeat_enabled"))
    config.set("repeat_infinite", dpg.get_value("repeat_infinite"))
    config.set("repeat_count", dpg.get_value("repeat_count"))
    dpg.set_viewport_always_top(config.get("always_on_top"))
    
    # Update player settings immediately
    player.playback_speed = config.get("playback_speed")
    player.jitter = config.get("jitter_amount")
    player.hover_delay = config.get("hover_delay")
    player.human_like_mouse = config.get("human_like_mouse")
    
    # Update UI to show current values
    dpg.set_value("playback_speed_label", f"{config.get('playback_speed'):.1f}x")
    dpg.set_value("jitter_label", f"{config.get('jitter_amount')}px")
    dpg.set_value("hover_delay_label", f"{config.get('hover_delay'):.2f}s")
    
    # Toggle human mouse settings visibility
    dpg.configure_item("human_mouse_settings", show=player.human_like_mouse)
    
    # Toggle repeat count field visibility
    try:
        dpg.configure_item("repeat_count_group", show=not dpg.get_value("repeat_infinite"))
    except:
        pass  # Item might not be created yet during initialization

def hotkey_listener():
    """Listen for hotkeys in a separate thread"""
    from pynput import keyboard
    import time
    
    last_bracket_press = 0
    bracket_press_delay = 0.3  # Time window for detecting double bracket presses
    
    def on_press(key):
        nonlocal last_bracket_press
        
        try:
            start_key = config.get("start_key").strip('\'\"')
            stop_key = config.get("stop_key").strip('\'\"')
            
            # Handle bracket keys specifically (they need special handling)
            if hasattr(key, 'char'):
                if key.char == start_key:
                    current_time = time.time()
                    # Check if this is a double press for play/stop
                    if current_time - last_bracket_press < bracket_press_delay:
                        if recorder.is_recording:
                            stop_recording()
                        elif playback_active:
                            stop_playback()
                        else:
                            play_recording()
                    else:
                        if recorder.is_recording:
                            stop_recording()
                        else:
                            start_recording()
                    
                    last_bracket_press = current_time
                elif key.char == stop_key:
                    if playback_active:
                        stop_playback()
                    elif recorder.is_recording:
                        stop_recording()
                    else:
                        play_recording()
            else:
                # Handle special keys
                key_name = str(key).replace("Key.", "").lower()
                if key_name == start_key.lower():
                    if recorder.is_recording:
                        stop_recording()
                    else:
                        start_recording()
                elif key_name == stop_key.lower():
                    if playback_active:
                        stop_playback()
                    elif recorder.is_recording:
                        stop_recording()
                    else:
                        play_recording()
        except Exception as e:
            print(f"Hotkey error: {str(e)}")
    
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

# Start hotkey thread
threading.Thread(target=hotkey_listener, daemon=True).start()

# UI Setup
dpg.create_context()

# Load custom icon
icon_path = "app.ico"
if not os.path.exists(icon_path) and getattr(sys, 'frozen', False):
    # Try to find icon in bundle
    bundle_dir = sys._MEIPASS
    icon_path = os.path.join(bundle_dir, "app.ico")

# Create viewport with proper icon
dpg.create_viewport(title='Roblox Macro', width=600, height=520,  # Slightly taller for new features
                   small_icon=icon_path, large_icon=icon_path)

# Modern styling - SIMPLER AND MORE COMPACT
with dpg.theme() as global_theme:
    with dpg.theme_component(dpg.mvAll):
        dpg.add_theme_color(dpg.mvThemeCol_WindowBg, BACKGROUND_COLOR, category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_FrameBg, PANEL_COLOR, category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_TitleBg, (50, 50, 60, 255), category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_Button, (60, 60, 70, 255), category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (80, 80, 90, 255), category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (100, 100, 110, 255), category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_Text, TEXT_COLOR, category=dpg.mvThemeCat_Core)
        dpg.add_theme_color(dpg.mvThemeCol_Border, BORDER_COLOR, category=dpg.mvThemeCat_Core)
        dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 3, category=dpg.mvThemeCat_Core)
        dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 5, category=dpg.mvThemeCat_Core)
        dpg.add_theme_style(dpg.mvStyleVar_WindowTitleAlign, 0.5, category=dpg.mvThemeCat_Core)
        dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 5, 3, category=dpg.mvThemeCat_Core)
        dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 4, category=dpg.mvThemeCat_Core)
        dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 10, 10, category=dpg.mvThemeCat_Core)

dpg.bind_theme(global_theme)

# Create fonts - SMALLER AND MORE COMPACT
with dpg.font_registry():
    # Correct way to set default font in newer Dear PyGui versions
    title_font = dpg.add_font("C:/Windows/Fonts/SegoeUI.ttf", 18, tag="title_font")
    header_font = dpg.add_font("C:/Windows/Fonts/SegoeUI.ttf", 15, tag="header_font")  # Slightly bigger
    body_font = dpg.add_font("C:/Windows/Fonts/SegoeUI.ttf", 14, tag="body_font")      # Slightly bigger
    small_font = dpg.add_font("C:/Windows/Fonts/SegoeUI.ttf", 13, tag="small_font")    # Slightly bigger

# ================================
# FIXED ICON LOADING FUNCTION
# ================================
def load_app_icon():
    """Load and register the app icon as a texture"""
    global app_icon_texture
    
    # First try to load from file
    icon_data = None
    if os.path.exists("app.ico"):
        try:
            # Convert ICO to PNG for Dear PyGui
            img = Image.open("app.ico")
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Get the largest size available (usually the first one)
            if hasattr(img, 'info') and 'sizes' in img.info:
                sizes = img.info['sizes']
                if sizes:
                    img = Image.open("app.ico")
                    img = img.resize(sizes[0])
            
            # Convert to bytes
            img_bytes = BytesIO()
            img.save(img_bytes, format='PNG')
            icon_data = img_bytes.getvalue()
        except Exception as e:
            print(f"Warning: Failed to load app.ico directly: {str(e)}")
    
    # If file loading failed or we're in a bundle, use embedded fallback
    if icon_data is None:
        try:
            # Embedded 32x32 icon as base64
            fallback_icon = """
            iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAVklEQVRYR+2W0QqDMBBE
            /w89epIIgqJ48O7//0h3k01jNlEUELx7m8xkmBBIIIAkTQIhBGme52ieZ1RVhTzPkOY5
            0jzHNE2I4xhhGCIvCqR5jjRPMU0TqqqCMAwRhiHCMEQYBgjDAOEf4P8J+HcC/h34/QMM
            8NhiHY7DRwAAAABJRU5ErkJggg==
            """
            icon_data = base64.b64decode(fallback_icon.strip())
        except Exception as e:
            print(f"Error: Failed to load fallback icon: {str(e)}")
            return None
    
    try:
        # Convert PNG bytes to texture - CORRECTED FOR NEWER DEAR PYGUI
        data = None
        width = 0
        height = 0
        channels = 0
        
        try:
            # Try using the built-in load_image function
            width, height, channels, data = dpg.load_image(BytesIO(icon_data))
        except:
            # Fallback: manual conversion
            img = Image.open(BytesIO(icon_data))
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            width, height = img.size
            channels = 4
            data = img.tobytes()
        
        if data is None:
            print("Error: Failed to get image data")
            return None
        
        with dpg.texture_registry():
            app_icon_texture = dpg.add_static_texture(
                width, height, data, 
                tag="app_icon_texture"
            )
        
        return app_icon_texture
    except Exception as e:
        print(f"Error: Failed to register icon texture: {str(e)}")
        return None

# ================================
# MAIN WINDOW CREATION
# ================================
def create_main_window():
    global app_icon_texture
    
    # Load the icon texture
    app_icon_texture = load_app_icon()
    
    with dpg.window(tag="main_window"):
        # Compact title section
        with dpg.group(horizontal=True):
            if app_icon_texture:
                dpg.add_image(app_icon_texture, width=24, height=24)
            dpg.add_text("Roblox Macro Recorder", color=PRIMARY_COLOR)
            dpg.bind_item_font(dpg.last_item(), title_font)
        
        dpg.add_text("Human-like input automation for Roblox", color=SECONDARY_COLOR)
        dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
        dpg.add_spacer(height=5)
        
        # Status bar at top
        with dpg.child_window(height=25, border=False):
            with dpg.group(horizontal=True):
                dpg.add_text("Status:", color=SECONDARY_COLOR)
                dpg.bind_item_font(dpg.last_item(), small_font)
                dpg.add_text("■ Ready", tag="rec_status", color=TEXT_COLOR)
                dpg.bind_item_font(dpg.last_item(), small_font)
                dpg.add_spacer(width=10)
                dpg.add_text("", tag="rec_status_desc", color=SECONDARY_COLOR)
                dpg.bind_item_font(dpg.last_item(), small_font)
        
        dpg.add_separator()
        
        with dpg.tab_bar():
            # Home Tab - Main controls
            with dpg.tab(label="Home"):
                # Recording Controls
                dpg.add_text("Recording", color=PRIMARY_COLOR)
                dpg.bind_item_font(dpg.last_item(), header_font)
                dpg.add_spacer(height=3)
                
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Start Recording ([)", callback=start_recording, width=140, height=30)
                    dpg.add_button(label="Stop Recording ([)", callback=stop_recording, width=140, height=30)
                
                dpg.add_spacer(height=5)
                # Current Recording (using horizontal group instead of add_same_line)
                with dpg.group(horizontal=True):
                    dpg.add_text("Current: ", color=SECONDARY_COLOR)
                    dpg.bind_item_font(dpg.last_item(), small_font)
                    dpg.add_text("No recording selected", tag="current_recording_label", color=WARNING_COLOR)
                    dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                
                dpg.add_spacer(height=3)
                dpg.add_listbox(width=-1, num_items=5, tag="recordings_list", callback=set_current_recording)
                
                dpg.add_spacer(height=5)
                # Recording Status (using horizontal group instead of add_same_line)
                with dpg.group(horizontal=True):
                    dpg.add_text("Status: ", color=SECONDARY_COLOR)
                    dpg.bind_item_font(dpg.last_item(), small_font)
                    dpg.add_text("0 events", tag="rec_counter", color=TEXT_COLOR)
                    dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                
                dpg.add_separator()
                
                # Playback Controls
                dpg.add_text("Playback", color=PRIMARY_COLOR)
                dpg.bind_item_font(dpg.last_item(), header_font)
                dpg.add_spacer(height=3)
                
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Play (])", callback=play_recording, width=140, height=30)
                    dpg.add_button(label="Stop (])", callback=stop_playback, width=140, height=30)
                
                dpg.add_spacer(height=5)
                # Repeat settings
                dpg.add_checkbox(label="Repeat", tag="repeat_enabled", 
                                default_value=config.get("repeat_enabled"),
                                callback=update_settings)
                
                # THIS IS THE CORRECTED PART - CREATE THE GROUP FIRST
                with dpg.group(horizontal=True, tag="repeat_count_group", 
                              show=not config.get("repeat_infinite")):
                    dpg.add_checkbox(label="Infinite", tag="repeat_infinite", 
                                    default_value=config.get("repeat_infinite"),
                                    callback=update_settings)
                    dpg.add_input_int(tag="repeat_count", 
                                     default_value=config.get("repeat_count"),
                                     min_value=1,
                                     width=60,
                                     callback=update_settings)
                
                dpg.add_spacer(height=5)
                # Playback Status (using horizontal group instead of add_same_line)
                with dpg.group(horizontal=True):
                    dpg.add_text("Status: ", color=SECONDARY_COLOR)
                    dpg.bind_item_font(dpg.last_item(), small_font)
                    dpg.add_text("Ready to play", tag="play_status", color=TEXT_COLOR)
                    dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                
                dpg.add_spacer(height=5)
                # Delete button
                with dpg.group(horizontal=True):
                    dpg.add_button(label="Delete Selected", callback=delete_recording, width=140, height=30)
            
            # Settings Tab
            with dpg.tab(label="Settings"):
                dpg.add_text("Basic Settings", color=PRIMARY_COLOR)
                dpg.bind_item_font(dpg.last_item(), header_font)
                dpg.add_spacer(height=5)
                
                dpg.add_checkbox(label="Always on Top", tag="always_on_top", 
                                default_value=config.get("always_on_top"),
                                callback=update_settings)
                
                # Playback Speed (using horizontal group)
                with dpg.group(horizontal=True):
                    dpg.add_text("Playback Speed:", color=TEXT_COLOR)
                    dpg.bind_item_font(dpg.last_item(), small_font)
                    dpg.add_text("1.0x", tag="playback_speed_label", color=PRIMARY_COLOR)
                    dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                dpg.add_slider_float(tag="playback_speed",
                                    default_value=config.get("playback_speed"),
                                    min_value=0.5, max_value=2.0, format="",
                                    width=-1,
                                    callback=update_settings)
                
                # Mouse Jitter (using horizontal group)
                with dpg.group(horizontal=True):
                    dpg.add_text("Mouse Jitter:", color=TEXT_COLOR)
                    dpg.bind_item_font(dpg.last_item(), small_font)
                    dpg.add_text("2px", tag="jitter_label", color=PRIMARY_COLOR)
                    dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                dpg.add_slider_int(tag="jitter_amount",
                                  default_value=config.get("jitter_amount"),
                                  min_value=0, max_value=5,
                                  width=-1,
                                  callback=update_settings)
                
                # Hover Delay (using horizontal group)
                with dpg.group(horizontal=True):
                    dpg.add_text("Hover Delay:", color=TEXT_COLOR)
                    dpg.bind_item_font(dpg.last_item(), small_font)
                    dpg.add_text("0.30s", tag="hover_delay_label", color=PRIMARY_COLOR)
                    dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                dpg.add_slider_float(tag="hover_delay",
                                    default_value=config.get("hover_delay"),
                                    min_value=0.1, max_value=1.0, format="",
                                    width=-1,
                                    callback=update_settings)
                
                # === HUMAN MOUSE SETTINGS ADDED HERE ===
                dpg.add_spacer(height=15)
                dpg.add_text("Human-Like Mouse", color=PRIMARY_COLOR)
                dpg.bind_item_font(dpg.last_item(), header_font)
                dpg.add_spacer(height=5)
                
                dpg.add_checkbox(label="Enable human-like mouse movement", tag="human_like_mouse", 
                                default_value=config.get("human_like_mouse"),
                                callback=lambda: config.set("human_like_mouse", dpg.get_value("human_like_mouse")))
                
                # Mouse movement settings (only visible when human-like is enabled)
                with dpg.group(tag="human_mouse_settings", show=config.get("human_like_mouse")):
                    dpg.add_spacer(height=5)
                    
                    # Mouse acceleration
                    with dpg.group(horizontal=True):
                        dpg.add_text("Movement Acceleration:", color=TEXT_COLOR)
                        dpg.bind_item_font(dpg.last_item(), small_font)
                        dpg.add_text(f"{config.get('mouse_acceleration'):.1f}", tag="mouse_acceleration_label", color=PRIMARY_COLOR)
                        dpg.bind_item_font(dpg.last_item(), body_font)
                    dpg.add_slider_float(tag="mouse_acceleration",
                                        default_value=config.get("mouse_acceleration"),
                                        min_value=0.0, max_value=1.0, format="",
                                        width=-1,
                                        callback=update_mouse_settings)
                    
                    # Micro jitter
                    with dpg.group(horizontal=True):
                        dpg.add_text("Micro Jitter:", color=TEXT_COLOR)
                        dpg.bind_item_font(dpg.last_item(), small_font)
                        dpg.add_text(f"{config.get('micro_jitter'):.1f}px", tag="micro_jitter_label", color=PRIMARY_COLOR)
                        dpg.bind_item_font(dpg.last_item(), body_font)
                    dpg.add_slider_float(tag="micro_jitter",
                                        default_value=config.get("micro_jitter"),
                                        min_value=0.0, max_value=2.0, format="",
                                        width=-1,
                                        callback=update_mouse_settings)
                    
                    # Path smoothing
                    with dpg.group(horizontal=True):
                        dpg.add_text("Path Smoothing:", color=TEXT_COLOR)
                        dpg.bind_item_font(dpg.last_item(), small_font)
                        dpg.add_text(f"{config.get('path_smoothing'):.1f}", tag="path_smoothing_label", color=PRIMARY_COLOR)
                        dpg.bind_item_font(dpg.last_item(), body_font)
                    dpg.add_slider_float(tag="path_smoothing",
                                        default_value=config.get("path_smoothing"),
                                        min_value=0.0, max_value=1.0, format="",
                                        width=-1,
                                        callback=update_mouse_settings)
            
            # Advanced Tab
            with dpg.tab(label="Advanced"):
                dpg.add_text("Hotkey Configuration", color=PRIMARY_COLOR)
                dpg.bind_item_font(dpg.last_item(), header_font)
                dpg.add_spacer(height=5)
                
                with dpg.group(horizontal=True):
                    dpg.add_text("Start/Stop Recording:", color=TEXT_COLOR)
                    dpg.bind_item_font(dpg.last_item(), small_font)
                    dpg.add_input_text(default_value=config.get("start_key"),
                                      width=50, tag="start_key", on_enter=True,
                                      callback=lambda: config.set("start_key", dpg.get_value("start_key").strip('\'\"')))
                
                with dpg.group(horizontal=True):
                    dpg.add_text("Play/Stop Playback:", color=TEXT_COLOR)
                    dpg.bind_item_font(dpg.last_item(), small_font)
                    dpg.add_input_text(default_value=config.get("stop_key"),
                                      width=50, tag="stop_key", on_enter=True,
                                      callback=lambda: config.set("stop_key", dpg.get_value("stop_key").strip('\'\"')))
                
                dpg.add_spacer(height=15)
                dpg.add_text("Verification", color=PRIMARY_COLOR)
                dpg.bind_item_font(dpg.last_item(), header_font)
                dpg.add_spacer(height=5)
                
                dpg.add_text("This application uses precise timing to", wrap=580)
                dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                dpg.add_text("simulate human-like input for Roblox.", wrap=580)
                dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                dpg.add_text("No external dependencies or memory scanning.", wrap=580)
                dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
            
            # Help Tab
            with dpg.tab(label="Help"):
                dpg.add_text("Usage Guide", color=PRIMARY_COLOR)
                dpg.bind_item_font(dpg.last_item(), header_font)
                dpg.add_spacer(height=5)
                
                dpg.add_text("Recording:", color=SECONDARY_COLOR)
                dpg.bind_item_font(dpg.last_item(), small_font)
                dpg.add_text("1. Click 'Start Recording' or press [", bullet=True, indent=20)
                dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                dpg.add_text("2. Perform actions in Roblox", bullet=True, indent=20)
                dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                dpg.add_text("3. Click 'Stop Recording' or press [", bullet=True, indent=20)
                dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                dpg.add_text("4. Enter a name and save your recording", bullet=True, indent=20)
                dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                
                dpg.add_spacer(height=10)
                dpg.add_text("Playback:", color=SECONDARY_COLOR)
                dpg.bind_item_font(dpg.last_item(), small_font)
                dpg.add_text("1. Select a recording from the list", bullet=True, indent=20)
                dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                dpg.add_text("2. Click 'Play' or press ]", bullet=True, indent=20)
                dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                dpg.add_text("3. Press ] again to stop", bullet=True, indent=20)
                dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                
                dpg.add_spacer(height=15)
                dpg.add_text("Notes:", color=SECONDARY_COLOR)
                dpg.bind_item_font(dpg.last_item(), small_font)
                dpg.add_text("- Works within Roblox's acceptable use policy", bullet=True, indent=20)
                dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                dpg.add_text("- No Roblox anti-cheat detection", bullet=True, indent=20)
                dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
                dpg.add_text("- Simulates human-like variations", bullet=True, indent=20)
                dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
        
        # Save Recording Modal Dialog
        with dpg.window(label="Save Recording", modal=True, show=False, 
                       pos=[150, 200], width=300, height=150, 
                       tag="save_recording_modal", no_collapse=True, 
                       no_title_bar=False):
            
            dpg.add_text("Name your recording:", color=TEXT_COLOR)
            dpg.bind_item_font(dpg.last_item(), body_font)  # Using larger font
            dpg.add_input_text(tag="save_recording_name", width=250)
            
            dpg.add_spacer(height=10)
            
            with dpg.group(horizontal=True):
                dpg.add_button(label="Save", width=75, 
                              callback=lambda: save_recording(dpg.get_value("save_recording_name")))
                dpg.add_button(label="Cancel", width=75, 
                              callback=cancel_recording)
        
        # Delete Recording Modal Dialog
        with dpg.window(label="Delete Recording", modal=True, show=False, 
                       pos=[150, 200], width=300, height=120, 
                       tag="delete_recording_modal", no_collapse=True, 
                       no_title_bar=False):
            
            dpg.add_text("Are you sure you want to delete", color=WARNING_COLOR)
            dpg.bind_item_font(dpg.last_item(), body_font)
            dpg.add_text("", tag="delete_recording_name", color=TEXT_COLOR)
            dpg.bind_item_font(dpg.last_item(), body_font)
            
            dpg.add_spacer(height=10)
            
            with dpg.group(horizontal=True):
                dpg.add_button(label="Delete", width=75, 
                              callback=confirm_delete_recording)
                dpg.add_button(label="Cancel", width=75, 
                              callback=cancel_delete_recording)

# Final UI Setup
try:
    # Correct way to set default font in newer Dear PyGui versions
    dpg.bind_font(title_font)
    create_main_window()
    dpg.setup_dearpygui()
    dpg.set_viewport_always_top(config.get("always_on_top"))
    dpg.set_viewport_resize_callback(lambda: dpg.set_item_pos("main_window", [0,0]))
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)
    dpg.start_dearpygui()
finally:
    dpg.destroy_context()