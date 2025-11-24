import time
import traceback
import dearpygui.dearpygui as dpg
import threading
import os
import sys
import json

from appHandler import InputHandler
from livepreview import MAX7219_Serial
from exporter import export_to_arduino_header
from ui import GUI

from DPGWidgets.timeline.timeline import Timeline
from DPGWidgets.timeline.widget import TimelineWidget
from DPGWidgets.MatrixLED import MatrixLEDWidget, MLED

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class AppConfig:
    def __init__(self):
        # livepreview
        self.lp_ena = False
        self.lp_port = "COM3"
        self.lp_speed = 115200
        self.lp_mled_invertH = False
        self.lp_mled_invertV = False
        self.lp_mled_rotate = "No Rotate"

    def save(self):
        print("saving config")
        config = {
            "livepreview": {
                "enabled": self.lp_ena,
                "port": self.lp_port,
                "speed": self.lp_speed,
                "device": {
                    "invertH": self.lp_mled_invertH,
                    "invertV": self.lp_mled_invertV,
                    "rotate": self.lp_mled_rotate
                }
            }
        }
        with open("appconfig.json", 'w') as json_file:
            json.dump(config, json_file, indent=4)

    def load(self):
        print("loading config")
        if not os.path.exists("appconfig.json"):
            print(f"Config file appconfig.json not found.")
            return

        with open("appconfig.json", 'r') as json_file:
            config = json.load(json_file)

        # livepreview settings
        self.lp_ena = config["livepreview"]["enabled"]
        self.lp_port = config["livepreview"]["port"]
        self.lp_speed = config["livepreview"]["speed"]
        self.lp_mled_invertH = config["livepreview"]["device"]["invertH"]
        self.lp_mled_invertV = config["livepreview"]["device"]["invertV"]
        self.lp_mled_rotate = config["livepreview"]["device"]["rotate"]

class App:
    def __init__(self):
        self.apptitle = "Maxleda Studio 1"
        self.appversion = "1.0.0"
        self.gui = GUI(self)
        self.appconfig = AppConfig()

        self.project_name = "Untitled"
        self.project_length = 300  # default project length in frames
        self.project_fps = 6  # default project frame rate
        self.project_path = None
        self.project_is_open = False

        self.last_timeline_window_size = None
        self.timeline = Timeline(total_frames=self.project_length, fps=self.project_fps)

        self.wtimeline = TimelineWidget("timeline", self.timeline)
        self.wtimeline.on_drag_playhead = self.timeline_on_drag_playhead
        self.wtimeline.editor_callback = self.timeline_editor_callback

        self.is_play = False
        self.last_window_size = (0, 0)

        # for demo
        devices_matrix = [
            [MLED(0), MLED(1, 8, 8), MLED(2, 16, 9), MLED(3, 7, 7)],
            [MLED(4, backgroundColor=(0, 0, 0)), MLED(5, LEDColor=(255, 255, 255)), MLED(6, label="hello")]
        ]

        self.MLED = MatrixLEDWidget("matrix_canvas", devices_matrix)
        self.last_matixled_window_size = (0, 0)

        self.MLED.set_editor_mode(True)
        self.MLED.editor_callback = self.editor_callback

        # Frame rate tracking
        self.gui.frame_start_time = time.time()

        self.last_frame = 0

        self.last_mled_change = {}
        self.selected_object_tl = None
        self.is_loop_enable = False
        self.is_saved = True

        self.LPDev = None

    def editor_callback(self, device_id, led_x, led_y, new_state):
        try:

            if device_id not in self.last_mled_change:
                self.last_mled_change[device_id] = {}

            if led_x not in self.last_mled_change[device_id]:
                self.last_mled_change[device_id][led_x] = {}

            # Store LED final state
            self.last_mled_change[device_id][led_x][led_y] = new_state

            #self.ne.node_editor.process(data | {"mode": "editor"})
        except Exception as e:
            print(traceback.format_exc())

    def timeline_editor_callback(self, action_type, is_curve, object_id, track_name, clip_id, dragged_frame, dragged_front):
        if self.is_saved:
            self.is_saved = False
            dpg.set_viewport_title(f"{self.apptitle} - {self.project_name}*")

        #print(action_type, is_curve, object_id, track_name, clip_id, dragged_frame, dragged_front)
        self.wtimeline.disable_dragging_playhead = True
        if is_curve:
            data = self.timeline.objects[object_id].tracks[track_name].keyframes
        else:
            data = self.timeline.objects[object_id].tracks[track_name].statements

        if action_type == 0: # move
            for stmt in data:
                if stmt.id == clip_id:
                    stmt.start_pos += dragged_frame
                    stmt.end_pos += dragged_frame
                    self.wtimeline.render()
                    break
        elif action_type == 1: # resize
            for stmt in data:
                if stmt.id == clip_id:
                    if dragged_front:
                        stmt.start_pos += dragged_frame
                    else:
                        stmt.end_pos += dragged_frame

                    self.wtimeline.render()
                    break
        elif action_type == 2: # property change popup
            self.wtimeline.set_color_for_item(object_id, track_name, clip_id, color=[255, 215, 0, 255])
            self.wtimeline.render()
            self.selected_object_tl = (object_id, track_name, clip_id)
            self.gui.open_property_modal()

        self.wtimeline.disable_dragging_playhead = False

    def property_modal_callback(self, action):
        # action
        # 0 = delete
        # 1 = duplicate

        dpg.configure_item("modal_id", show=False)

        if not self.selected_object_tl:
            return

        object_id, track_name, clip_id = self.selected_object_tl

        self.wtimeline.set_color_for_item(object_id, track_name, clip_id, reset=True)
        self.wtimeline.render()

        if action == -2: # just close:
            return

        if self.is_saved:
            self.is_saved = False
            dpg.set_viewport_title(f"{self.apptitle} - {self.project_name}*")

        data = self.timeline.objects[object_id].tracks[track_name].statements
        for stmt in data:
            if stmt.id == clip_id:
                if action == 0:
                    self.timeline.remove_statement(object_id, track_name, clip_id)

                elif action == 1:
                    self.timeline.new_statement(
                        object_id,
                        track_name,
                        stmt.start_pos + 1,
                        stmt.end_pos + 1,
                        stmt.data
                    )

                    self.wtimeline.set_playhead_frame(stmt.start_pos + 1)

                if action == -1:  # update
                    is_auto_clear = dpg.get_value("auto_clear_checkbox")

                    if isinstance(stmt.data, dict) and "clear_first" in stmt.data:
                        stmt.data["clear_first"] = is_auto_clear

                break

        self.selected_object_tl = None
        self.wtimeline.render()

    def add_action_callback(self, action_type):
        device_combo_value = dpg.get_value("devicelistcombo")
        if not device_combo_value:
            return
        device_id = int(device_combo_value.split(" ")[1])

        intensity = dpg.get_value("intensity_slider")

        if action_type == 0:  # Clear all pixel
            self.timeline.new_statement(
                "mled",
                str(device_id),
                self.timeline.current_position,
                self.timeline.current_position + 1,
                {
                    "clear_first": True,
                    "pixels": [],
                    "intensity": intensity
                }
            )
        elif action_type == 1:  # Fill all pixel
            device = None
            for dev, devdata in self.MLED.devices.items():
                if dev == device_id:
                    device = dev
                    break
            if device:
                pixels = []
                for x in range(device.width):
                    for y in range(device.height):
                        pixels.append({
                            "x": x,
                            "y": y,
                            "state": 1
                        })

                self.timeline.new_statement(
                    "mled",
                    str(device_id),
                    self.timeline.current_position,
                    self.timeline.current_position + 1,
                    {
                        "clear_first": True,
                        "pixels": pixels,
                        "intensity": intensity
                    }
                )
        elif action_type == -1:  # Update with intensity
            device = None
            for dev, devdata in self.MLED.devices.items():
                if dev == device_id:
                    device = dev
                    break
            if device:
                pixels = []
                for x in range(device.width):
                    for y in range(device.height):
                        state = device.getLed(y, x)
                        if state:
                            pixels.append({
                                "x": x,
                                "y": y,
                                "state": state
                            })

                self.timeline.new_statement(
                    "mled",
                    str(device_id),
                    self.timeline.current_position,
                    self.timeline.current_position + 1,
                    {
                        "clear_first": False,
                        "pixels": pixels,
                        "intensity": intensity
                    }
                )

        self.wtimeline.set_playhead_frame(self.timeline.current_position + 1)
        self.wtimeline.render()
        if self.is_saved:
            self.is_saved = False
            dpg.set_viewport_title(f"{self.apptitle} - {self.project_name}*")
        dpg.configure_item("addactionwindow", show=False)


    def update_mled_keyframe(self):
        if not self.last_mled_change:
            return

        cpos = self.timeline.current_position
        intensity = dpg.get_value("intensity_slider")

        for device_id, changed_pixels in self.last_mled_change.items():
            device_id_str = str(device_id)

            # Ensure timeline object exists
            if "mled" not in self.timeline.objects:
                self.timeline.create_object("mled")

            tracks = self.timeline.objects["mled"].tracks

            # Track missing -> create first statement
            if device_id_str not in tracks:
                self.timeline.new_statement(
                    "mled",
                    device_id_str,
                    cpos,
                    cpos + 1,
                    {}
                )
                track = tracks[device_id_str]
                stmt = track.statements[-1]
                clear_first = False  # Changed: Don't auto-clear unless explicitly needed

            else:
                track = tracks[device_id_str]

                # Find active statement at current time
                stmt = None
                for s in track.statements:
                    if s.start_pos <= cpos < s.end_pos:
                        stmt = s
                        break

                # If no active statement, look for PREVIOUS state to inherit
                if stmt is None:
                    # Find the most recent statement before current position
                    prev_stmt = None
                    for s in sorted(track.statements, key=lambda x: x.end_pos, reverse=True):
                        if s.end_pos <= cpos:
                            prev_stmt = s
                            break

                    # Create new statement
                    self.timeline.new_statement(
                        "mled",
                        device_id_str,
                        cpos,
                        cpos + 1,
                        {}
                    )
                    stmt = track.statements[-1]

                    # Inherit previous state if exists
                    if prev_stmt and isinstance(prev_stmt.data, dict) and "pixels" in prev_stmt.data:
                        stmt.data = {
                            "clear_first": False,
                            "pixels": prev_stmt.data["pixels"].copy(),
                            "intensity": prev_stmt.data.get("intensity", intensity)
                        }
                        clear_first = False
                    else:
                        clear_first = False
                else:
                    clear_first = False

            # Build pixel map from existing data
            existing = {}
            if isinstance(stmt.data, dict) and "pixels" in stmt.data:
                existing = {(d["x"], d["y"]): d.copy() for d in stmt.data["pixels"]}
            elif isinstance(stmt.data, list):
                existing = {(d["x"], d["y"]): d.copy() for d in stmt.data}

            # Update with new changed pixels
            for x, col in changed_pixels.items():
                for y, st in col.items():
                    if st == 0:  # If turning off, remove from existing
                        existing.pop((x, y), None)
                    else:
                        existing[(x, y)] = {"x": x, "y": y, "state": st}

            # Store FINAL JSON PACKET directly in the timeline
            stmt.data = {
                "clear_first": clear_first,
                "pixels": list(existing.values()),
                "intensity": intensity
            }

        # Clear the change buffer
        self.last_mled_change.clear()

        # Go to next frame
        self.timeline.set_position(cpos + 1)
        self.wtimeline.render()

        if self.is_saved:
            self.is_saved = False
            dpg.set_viewport_title(f"{self.apptitle} - {self.project_name}*")

    def playback_thread(self):
        while self.is_play:
            total_frames = self.timeline.total_frames
            frame_rate = self.timeline.frame_rate

            sleep_time = 1.0 / frame_rate

            # true frame rate
            start = time.perf_counter()
            while time.perf_counter() - start < sleep_time:
                pass

            if self.wtimeline.current_frame >= total_frames:
                if self.is_loop_enable:
                    self.wtimeline.current_frame = 0
                    self.timeline.set_position(0)
                else:
                    self.stop_playback(None, None)
                    break

            self.wtimeline.current_frame += 1
            self.gui.frame_count += 1

            self.timeline_object_callback(self.timeline.get_scene_state(self.wtimeline.current_frame))

    def timeline_on_drag_playhead(self, frame):
        self.timeline_object_callback(self.timeline.get_scene_state(frame))
        self.gui.set_status(self.timeline.current_position, self.timeline.total_frames, self.timeline.frame_rate, 0, "SEEK", (-255, 0, 0, 255))

    def transform_bitmap(self, bitmap, width, height, inv, inh, rt):
        if inv:
            bitmap = bitmap[::-1]

        if inh:
            # Invert horizontal (mirror left-right)
            flipped = []
            for row in bitmap:
                # Reverse bits in the row
                new_row = 0
                for x in range(width):
                    if row & (1 << x):
                        new_row |= (1 << (width - 1 - x))
                flipped.append(new_row)

            bitmap = flipped

        if rt == "90 clockwise":
            # Rotate 90 degrees clockwise
            # New dimensions: width becomes height, height becomes width
            rotated = [0] * width
            for y in range(height):
                for x in range(width):
                    if bitmap[y] & (1 << x):
                        # (x, y) -> (y, width-1-x) in rotated space
                        new_x = y
                        new_y = width - 1 - x
                        rotated[new_y] |= (1 << new_x)

            bitmap = rotated

        elif rt == '90 counter-clockwise':
            # Rotate 90 degrees counter-clockwise
            rotated = [0] * width
            for y in range(height):
                for x in range(width):
                    if bitmap[y] & (1 << x):
                        # (x, y) -> (height-1-y, x) in rotated space
                        new_x = height - 1 - y
                        new_y = x
                        rotated[new_y] |= (1 << new_x)

            bitmap = rotated

        return bitmap

    def import_iv(self, sender, app_data):
        print(app_data)


    def timeline_object_callback(self, data):
        try:
            # Reset current LED changes
            self.last_mled_change = {}  # Clear old changes

            if "mled" in data:
                for device in data["mled"].keys():
                    stmt = self.timeline.get_object("mled").tracks[device].statements

                    for s in stmt:
                        if s.contains_position(self.timeline.current_position):
                            self.wtimeline.set_color_for_item("mled", device, s.id, color=[0, 255, 0, 255])
                        else:
                            self.wtimeline.set_color_for_item("mled", device, s.id, reset=True)

                    entry = data["mled"][device]
                    device_id = int(device)
                    pixels = entry.get("pixels", [])
                    is_clear_first = entry.get("clear_first", False)
                    intensity = entry.get("intensity", 15)

                    if is_clear_first:
                        self.MLED.clearDevice(device_id)

                    if self.LPDev and self.appconfig.lp_ena and is_clear_first:
                        self.LPDev.clear_device(device_id)

                    self.MLED.setIntensityDevice(device_id, intensity)

                    if self.LPDev and self.appconfig.lp_ena:
                        self.LPDev.set_intensity_device(device_id, intensity)

                    # Initialize this device in last_mled_change
                    if device_id not in self.last_mled_change:
                        self.last_mled_change[device_id] = {}

                    # Build bitmap for this device
                    if device_id in self.MLED.devices:
                        mled = self.MLED.devices[device_id]
                        height = mled.height
                        width = mled.width

                        # Initialize bitmap with current state or zeros
                        if not is_clear_first and device_id in self.MLED.state:
                            current_state = self.MLED.state[device_id]
                            if isinstance(current_state, list):
                                bitmap = [int(row) if isinstance(row, int) else 0 for row in current_state]
                            else:
                                bitmap = [0] * height
                        else:
                            bitmap = [0] * height

                        # Update bitmap with new pixel data
                        for px in pixels:
                            x = px["x"]
                            y = px["y"]
                            st = px["state"]

                            # Set or clear the bit at position x in row y
                            if st:
                                bitmap[y] |= (1 << x)  # Set bit
                            else:
                                bitmap[y] &= ~(1 << x)  # Clear bit

                            # Update last_mled_change to reflect current frame state
                            if x not in self.last_mled_change[device_id]:
                                self.last_mled_change[device_id][x] = {}
                            self.last_mled_change[device_id][x][y] = st

                        # Draw the entire bitmap at once for MLED
                        transformed_bitmap = self.transform_bitmap(bitmap.copy(), width, height, False, True, "")
                        self.MLED.drawBitmap(device_id, transformed_bitmap)

                        # Apply transformation ONLY for LPDev
                        if self.LPDev and self.appconfig.lp_ena:
                            transformed_bitmap = self.transform_bitmap(bitmap.copy(), width, height, self.appconfig.lp_mled_invertV, self.appconfig.lp_mled_invertH, self.appconfig.lp_mled_rotate.lower())

                            if hasattr(self.LPDev, 'draw_bitmap'):
                                self.LPDev.draw_bitmap(device_id, transformed_bitmap)
                            else:
                                # Fallback: reconstruct pixels from transformed bitmap
                                for y_idx, row in enumerate(transformed_bitmap):
                                    for x_idx in range(width):
                                        state = bool(row & (1 << x_idx))
                                        self.LPDev.set_led(device_id, y_idx, x_idx, state)
                    else:
                        print("something wrong")

            self.MLED._safe_render()
        except Exception as e:
            self.stop_playback(None, None)
            print(traceback.format_exc())

    def start_playback(self, _, __):
        if self.is_play:
            return

        dpg.hide_item("startbtn")
        dpg.show_item("stopbtn")
        self.wtimeline.set_editor_mode(False)
        self.MLED.set_editor_mode(False)

        if self.wtimeline.current_frame >= self.timeline.total_frames:
            self.wtimeline.set_playhead_frame(0)

        # Reset frame rate tracking
        self.gui.frame_count = 0
        self.gui.frame_start_time = time.time()

        self.is_play = True
        self.wtimeline.is_play = True
        t = threading.Thread(target=self.playback_thread)
        t.start()

    def stop_playback(self, _, __):
        dpg.show_item("startbtn")
        dpg.hide_item("stopbtn")
        self.is_play = False

        # Update status when stopped
        self.wtimeline.is_play = False
        self.wtimeline.set_editor_mode(True)
        self.MLED.set_editor_mode(True)
        self.gui.set_status(self.timeline.current_position, self.timeline.total_frames, self.timeline.frame_rate, 0, "STOPPED", (-255, 0, 0, 255))

    def change_project_settings(self, _, __):
        new_length = dpg.get_value("plengthin")
        new_fps = dpg.get_value("pfpsin")

        if new_length != self.project_length:
            self.project_length = new_length
            self.timeline.total_frames = new_length

        if new_fps != self.project_fps:
            self.project_fps = new_fps
            self.timeline.frame_rate = new_fps

        self.wtimeline.set_timeline_length(new_length, new_fps)
        if not self.is_play:
            self.wtimeline.render()

        if self.is_saved:
            self.is_saved = False
            dpg.set_viewport_title(f"{self.apptitle} - {self.project_name}*")

    def new_project(self, project_name, project_length, project_fps, devices_count=1):
        self.project_length = project_length  # default project length in frames
        self.project_fps = project_fps  # default project frame rate
        self.project_name = project_name

        self.timeline = Timeline(total_frames=self.project_length, fps=self.project_fps)

        self.wtimeline = TimelineWidget("timeline", self.timeline)
        self.wtimeline.on_drag_playhead = self.timeline_on_drag_playhead
        self.wtimeline.editor_callback = self.timeline_editor_callback

        devices_matrix = []
        created = []

        for i in range(devices_count):
            created.append(MLED(i))

        devices_matrix.append(created)

        self.MLED = MatrixLEDWidget("matrix_canvas", devices_matrix)
        self.last_matixled_window_size = (0, 0)

        self.MLED.set_editor_mode(True)
        self.MLED.editor_callback = self.editor_callback
        self.last_timeline_window_size = None
        dpg.set_viewport_title(f"{self.apptitle} - {self.project_name}*")
        self.is_saved = False
        self.project_path = None
        self.project_is_open = True
        self.last_mled_change = {}
        self.selected_object_tl = None

        dpg.set_value("plengthin", self.project_length)
        dpg.set_value("pfpsin", self.project_fps)

        self.wtimeline.render()

    def save_project(self, saveas=False):
        if not self.project_is_open:
            return
        if not saveas:
            if self.project_path:
                if not self.is_saved:
                    self.save_project_callback(None, {
                        "file_path_name": self.project_path
                    })

                return

        dpg.show_item("saveprojectdialog")

    def save_project_callback(self, sender, app_data):
        filepath = app_data['file_path_name']

        clayout = self.MLED.devices_matrix

        matrix_layout = []

        for row in clayout:
            new_row = []
            for dev in row:
                new_row.append({
                    "id": dev.id,
                    "width": dev.width,
                    "height": dev.height,
                    "backgroundColor": list(dev.backgroundColor),
                    "LEDColor": list(dev.LEDColor),
                    "label": dev.label
                })
            matrix_layout.append(new_row)

        project_data = {
            "name": self.project_name,
            "length": self.project_length,
            "fps": self.project_fps,
            "LEDLayouts": matrix_layout,
            "timeline": self.timeline.export_timeline()
        }

        json.dump(project_data, open(filepath, "w"), indent=4)
        dpg.set_viewport_title(f"{self.apptitle} - {self.project_name}")
        self.is_saved = True
        self.project_path = filepath
        self.project_is_open = True

    def open_project(self, sender, app_data):
        filepath = app_data['file_path_name']

        data = json.load(open(filepath, "r"))

        matrix_data = data["LEDLayouts"]

        devices_matrix = []
        for row in matrix_data:
            new_row = []
            for dev in row:
                mled = MLED(
                    dev["id"],
                    width=dev.get("width", 8),
                    height=dev.get("height", 8),
                    backgroundColor=tuple(dev.get("backgroundColor", (30, 30, 30))),
                    LEDColor=tuple(dev.get("LEDColor", (255, 0, 0))),
                    label=dev.get("label")
                )
                new_row.append(mled)
            devices_matrix.append(new_row)

        self.project_name = data["name"]
        self.project_length = data["length"]
        self.project_fps = data["fps"]

        self.timeline = Timeline(total_frames=self.project_length, fps=self.project_fps)
        self.timeline.import_timeline(data["timeline"])

        self.wtimeline = TimelineWidget("timeline", self.timeline)
        self.wtimeline.on_drag_playhead = self.timeline_on_drag_playhead
        self.wtimeline.editor_callback = self.timeline_editor_callback

        self.MLED = MatrixLEDWidget("matrix_canvas", devices_matrix)
        self.last_matixled_window_size = (0, 0)

        self.MLED.set_editor_mode(True)
        self.MLED.editor_callback = self.editor_callback
        self.last_timeline_window_size = None
        dpg.set_viewport_title(f"{self.apptitle} - {self.project_name}")
        self.is_saved = True
        self.project_path = filepath
        self.project_is_open = True
        self.last_mled_change = {}
        self.selected_object_tl = None

        dpg.set_value("plengthin", self.project_length)
        dpg.set_value("pfpsin", self.project_fps)

        self.wtimeline.render()

    def export_header(self, sender, app_data):
        if not self.project_is_open:
            return

        invertV = dpg.get_value("export_invert_vertical")
        invertH = dpg.get_value("export_invert_horizontal")
        rotate = dpg.get_value("export_rotate_radiobutton").lower()
        includePlayer = dpg.get_value("export_include_helper_checkbox")

        if rotate == "90 clockwise":
            rotate = 1
        elif rotate == "90 counter-clockwise":
            rotate = 2
        else:
            rotate = 0

        header_content = export_to_arduino_header(
            self.timeline,
            self.MLED.devices,
            self.project_name.replace(" ", "_"),
            self.project_fps,
            invertH,
            invertV,
            rotate,
            includePlayer
        )

        filepath = app_data['file_path_name']
        with open(filepath, "w", encoding="UTF-8") as f:
            f.write(header_content)

    def init(self):
        dpg.create_context()
        icon = resource_path("icon.ico")
        dpg.create_viewport(title=f'{self.apptitle}', width=1280, height=720, small_icon=str(icon), large_icon=str(icon))  # set viewport window
        dpg.setup_dearpygui()

        IH = InputHandler(self)

        IH.register()

        with dpg.theme() as self.btn_red_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (255, 0, 0), category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 0, category=dpg.mvThemeCat_Core)

        icons = [
            ["addicon", resource_path("addicon.png")],
            ["updateicon", resource_path("updateicon.png")],
            ["playicon", resource_path("playicon.png")],
            ["stopicon", resource_path("stopicon.png")],
            ["importicon", resource_path("importicon.png")]
        ]

        with dpg.texture_registry():
            for TEXTURE_TAG, IMAGE_PATH in icons:
                width, height, channels, data = dpg.load_image(IMAGE_PATH)
                dpg.add_dynamic_texture(width=width, height=height, default_value=data, tag=TEXTURE_TAG)

        dpg.configure_app(docking=True, docking_space=True)
        dpg.configure_app(init_file="workspace.ini")

        # -------------- add code here --------------
        self.appconfig.load()

        if self.appconfig.lp_ena:
            try:
                self.LPDev = MAX7219_Serial(self.appconfig.lp_port, self.appconfig.lp_speed)
            except:
                print("Failed to connect to Live Preview device")
                self.appconfig.lp_ena = False

        self.gui.window()
        self.gui.menubar()
        #dpg.show_imgui_demo()

        self.wtimeline.render()

        # -------------------------------------------
        dpg.show_viewport()

        try:
            while dpg.is_dearpygui_running():
                self.render()
                dpg.render_dearpygui_frame()
        except Exception as e:
            print(traceback.format_exc())
        except KeyboardInterrupt:
            pass

        self.appconfig.save()


        if self.LPDev:
            self.LPDev.close()

        self.exit()

    def render(self):
        window_width = dpg.get_viewport_width()
        window_height = dpg.get_viewport_height()
        timeline_window_width = dpg.get_item_height("timelinewindow")
        timeline_window_height = dpg.get_item_width("timelinewindow")

        MLED_window_width = dpg.get_item_height("matrixLEDwindow")
        MLED_window_height = dpg.get_item_width("matrixLEDwindow")

        if self.last_timeline_window_size != (timeline_window_width, timeline_window_height):
            self.wtimeline.height = dpg.get_item_height("timelinewindow") - 90
            self.wtimeline.width = dpg.get_item_width("timelinewindow") - 15
            dpg.set_item_width("timeline", self.wtimeline.width)
            dpg.set_item_height("timeline", self.wtimeline.height)

            self.wtimeline.render()
            self.last_timeline_window_size = (timeline_window_width, timeline_window_height)

        if self.last_matixled_window_size != (MLED_window_width, MLED_window_height):
            self.MLED.window_height = dpg.get_item_height("matrixLEDwindow") - 35
            self.MLED.window_width = dpg.get_item_width("matrixLEDwindow") - 15
            dpg.set_item_width("matrix_canvas", self.MLED.window_width)
            dpg.set_item_height("matrix_canvas", self.MLED.window_height)

            self.last_matixled_window_size = (MLED_window_width, MLED_window_height)
            self.MLED._safe_render()

        self.MLED.update()

        if self.last_window_size != (window_width, window_height):
            dpg.set_item_pos("frame_status", [dpg.get_viewport_width() - 400, 0])

            self.last_window_size = (window_width, window_height)

        if self.is_play and (self.last_frame != self.wtimeline.current_frame):
            self.wtimeline.set_playhead_frame(self.wtimeline.current_frame)

            self.gui.update_frame_rate_status()
            self.last_frame = self.wtimeline.current_frame

    def exit(self):
        dpg.destroy_context()

app = App()
app.init()