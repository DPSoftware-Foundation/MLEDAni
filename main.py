import time
import traceback
from datetime import datetime
import dearpygui.dearpygui as dpg
import threading
import os
import sys
import json
from exporter import export_to_arduino_header

from DPGWidgets.timeline.timeline import Timeline
from DPGWidgets.timeline.widget import TimelineWidget
from DPGWidgets.MatrixLED import MatrixLEDWidget, MLED

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class App:
    def __init__(self):
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
        self.frame_start_time = time.time()
        self.actual_frame_rate = 0.0
        self.frame_count = 0
        self.taskbar = None
        self.last_frame = 0

        self.last_mled_change = {}
        self.selected_object_tl = None
        self.is_loop_enable = False
        self.is_saved = True

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
            dpg.set_viewport_title(f"Maxleda Animator - {self.project_name}*")

        print(action_type, is_curve, object_id, track_name, clip_id, dragged_frame, dragged_front)
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
            self.wtimeline.render()

            self.selected_object_tl = (object_id, track_name, clip_id)
            self.open_property_modal()

        self.wtimeline.disable_dragging_playhead = False

    def open_property_modal(self):
        if not self.selected_object_tl:
            return

        object_id, track_name, clip_id = self.selected_object_tl

        data = self.timeline.objects[object_id].tracks[track_name].statements

        for stmt in data:
            if stmt.id == clip_id:
                print("Open property modal for:", stmt)

                if isinstance(stmt.data, dict) and "clear_first" in stmt.data:
                    dpg.set_value("auto_clear_checkbox", stmt.data["clear_first"])
                else:
                    dpg.set_value("auto_clear_checkbox", True)

                dpg.configure_item("modal_id", show=True)

                break

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
            dpg.set_viewport_title(f"Maxleda Animator - {self.project_name}*")

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
            dpg.set_viewport_title(f"Maxleda Animator - {self.project_name}*")
        dpg.configure_item("addactionwindow", show=False)

    def open_add_action_modal(self):
        # Populate device list
        device_list = []
        for device, devdata in self.MLED.devices.items():
            device_list.append(f"Device {device} ({devdata.width}x{devdata.height})")

        dpg.configure_item("devicelistcombo", items=device_list, default_value=device_list[0] if device_list else "")

        dpg.configure_item("addactionwindow", show=True)


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
                clear_first = True  # First statement in track

            else:
                track = tracks[device_id_str]

                # Find active statement at current time
                stmt = None
                for s in track.statements:
                    if s.start_pos <= cpos < s.end_pos:
                        stmt = s
                        break

                # If no active statement, create new
                if stmt is None:
                    self.timeline.new_statement(
                        "mled",
                        device_id_str,
                        cpos,
                        cpos + 1,
                        {}
                    )
                    stmt = track.statements[-1]
                    clear_first = True
                else:
                    clear_first = False

            # Build pixel map from existing data
            existing = {}
            if isinstance(stmt.data, dict) and "pixels" in stmt.data:
                existing = {(d["x"], d["y"]): d for d in stmt.data["pixels"]}
            elif isinstance(stmt.data, list):
                existing = {(d["x"], d["y"]): d for d in stmt.data}

            # Update with new changed pixels
            for x, col in changed_pixels.items():
                for y, st in col.items():
                    existing[(x, y)] = {"x": x, "y": y, "state": st}

            # Store FINAL JSON PACKET directly in the timeline
            stmt.data = {
                "clear_first": clear_first,
                "pixels": list(existing.values()),
                "intensity": intensity  # default intensity
            }

        # Go to next frame
        self.timeline.set_position(cpos + 1)
        self.wtimeline.render()

        if self.is_saved:
            self.is_saved = False
            dpg.set_viewport_title(f"Maxleda Animator - {self.project_name}*")

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
            self.frame_count += 1

            self.timeline_object_callback(self.timeline.get_scene_state(self.wtimeline.current_frame))

    def update_frame_rate_status(self):
        """Update the frame rate status with color coding"""
        current_time = time.time()

        if self.frame_count == 0:
            self.frame_start_time = current_time

        if (current_time - self.frame_start_time) >= 0.5:
            elapsed_time = current_time - self.frame_start_time
            if elapsed_time > 0:
                self.actual_frame_rate = self.frame_count / elapsed_time

            # Reset counters
            self.frame_count = 0
            self.frame_start_time = current_time

        # Determine color based on performance
        fps_ratio = self.actual_frame_rate / self.timeline.frame_rate if self.timeline.frame_rate > 0 else 1.0

        if fps_ratio >= 0.9:  # Normal (realtime) - Green
            color = (0, 255, 0, 255)  # Green
        elif fps_ratio >= 0.5:  # Slower but not more than half - Yellow
            color = (255, 255, 0, 255)  # Yellow
        else:  # Slower than half - Red
            color = (255, 0, 0, 255)  # Red

        self.set_status(self.timeline.current_position, self.timeline.total_frames, self.timeline.frame_rate, self.actual_frame_rate, None, color)

    def timeline_on_drag_playhead(self, frame):
        self.timeline_object_callback(self.timeline.get_scene_state(frame))
        self.set_status(self.timeline.current_position, self.timeline.total_frames, self.timeline.frame_rate, 0, "SEEK", (-255, 0, 0, 255))

    def timeline_object_callback(self, data):
        try:
            #print(data)
            # Reset current LED changes
            self.last_mled_change = {}  # Clear old changes

            if "mled" in data:
                for device in data["mled"].keys():
                    entry = data["mled"][device]
                    device_id = int(device)
                    pixels = entry.get("pixels", [])
                    is_clear_first = entry.get("clear_first", False)
                    intensity = entry.get("intensity", 15)

                    if is_clear_first:
                        self.MLED.clearDevice(device_id)

                    self.MLED.setIntensityDevice(device_id, intensity)

                    # Initialize this device in last_mled_change
                    if device_id not in self.last_mled_change:
                        self.last_mled_change[device_id] = {}

                    for px in pixels:
                        x = px["x"]
                        y = px["y"]
                        st = px["state"]

                        # Update MLED widget
                        self.MLED.setLed(device_id, y, x, st)

                        # Update last_mled_change to reflect current frame state
                        if x not in self.last_mled_change[device_id]:
                            self.last_mled_change[device_id][x] = {}
                        self.last_mled_change[device_id][x][y] = st

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
        self.frame_count = 0
        self.frame_start_time = time.time()

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
        self.set_status(self.timeline.current_position, self.timeline.total_frames, self.timeline.frame_rate, 0, "STOPPED", (-255, 0, 0, 255))

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
            dpg.set_viewport_title(f"Maxleda Animator - {self.project_name}*")

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
        dpg.set_viewport_title(f"Maxleda Animator - {self.project_name}*")
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
        dpg.set_viewport_title(f"Maxleda Animator - {self.project_name}")
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
        dpg.set_viewport_title(f"Maxleda Animator - {self.project_name}")
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

    def window(self):
        with dpg.window(label="Timeline", tag="timelinewindow", width=500, height=320, no_close=True):
            with dpg.group(horizontal=True):
                with dpg.tooltip(dpg.add_image_button("addicon", width=20, height=20, callback=lambda: self.open_add_action_modal())):
                    dpg.add_text("Add new action to the Matrix LED.")

                with dpg.tooltip(dpg.add_image_button("updateicon", width=20, height=20, callback=lambda: self.update_mled_keyframe())):
                    dpg.add_text("Add or override new LED matrix statement to the timeline at the current playhead position.")

                dpg.add_slider_int(label="Intensity", tag="intensity_slider", default_value=15, min_value=0, max_value=15, width=100, height=20)

            dpg.add_drawlist(self.wtimeline.width, self.wtimeline.height, tag="timeline")

            with dpg.group(horizontal=True):
                dpg.add_input_int(label="Length (frames)", tag="plengthin", default_value=self.project_length, width=150, callback=self.change_project_settings)
                dpg.add_input_int(label="Frame Rate (FPS)", tag="pfpsin", default_value=self.project_fps, width=150, callback=self.change_project_settings)
                dpg.add_checkbox(label="Loop", default_value=self.is_loop_enable, callback=lambda s, a: setattr(self, 'is_loop_enable', a))

        with dpg.window(label="Maxtrix LED", tag="matrixLEDwindow", width=500, height=320, no_close=True):
            dpg.add_drawlist(self.MLED.window_width, self.MLED.window_height, tag="matrix_canvas")

        with dpg.window(label="New Project", tag="newprojectwindow", no_close=False, show=False, modal=True):
            dpg.add_input_text(label="Project Name", tag="newprojectnamein", default_value="Untitled", width=200)
            dpg.add_input_int(label="Project Length (frames)", tag="newprojectlengthin", default_value=300, width=200)
            dpg.add_input_int(label="Project Frame Rate (FPS)", tag="newprojectfpsin", default_value=6, width=200)
            dpg.add_input_int(label="Number of Matrix LED Devices", tag="newprojectdevicescountin", default_value=1, width=200, min_value=1, min_clamped=True)
            dpg.add_text("For editing layout of Matrix LED devices, please do it after creating the project and edit at project file.")
            dpg.add_spacer()
            dpg.add_text("Note: This will reset current project. Please save first!")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Create", width=75, callback=lambda: self.new_project(
                    dpg.get_value("newprojectnamein"),
                    dpg.get_value("newprojectlengthin"),
                    dpg.get_value("newprojectfpsin"),
                    dpg.get_value("newprojectdevicescountin")
                ) or dpg.configure_item("newprojectwindow", show=False))
                dpg.add_spacer(width=100)
                dpg.add_button(label="Cancel", width=75, callback=lambda: dpg.configure_item("newprojectwindow", show=False))

        with dpg.window(label="Add Action", tag="addactionwindow", width=300, no_close=False, show=False, modal=True):
            dpg.add_combo(label="Matrix Device", tag="devicelistcombo")
            dpg.add_spacer()
            dpg.add_text("Please select action to add:")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Clear All Pixel", width=120, callback=lambda: self.add_action_callback(0))
                dpg.add_button(label="Fill All Pixel", width=120, callback=lambda: self.add_action_callback(1))

                dpg.add_spacer(width=150)
                dpg.add_button(label="Cancel", width=75, callback=lambda: dpg.configure_item("addactionwindow", show=False))

        with dpg.window(label="Action", modal=True, show=False, tag="modal_id", no_title_bar=True):
            dpg.add_text("Please select action for the selected item:")
            dpg.add_separator()
            with dpg.group():
                dpg.add_checkbox(label="Auto Clear Before Action", tag="auto_clear_checkbox", default_value=True)
                dpg.add_button(label="Update", width=75, callback=lambda: self.property_modal_callback(-1))
                dpg.add_spacer()
                dpg.add_button(label="Duplicate", width=75, callback=lambda: self.property_modal_callback(1))
                delbtn = dpg.add_button(label="Delete", width=75, callback=lambda: self.property_modal_callback(0))
                dpg.add_spacer(width=100)
                dpg.add_button(label="Cancel", width=75, callback=lambda: self.property_modal_callback(-2))

                dpg.bind_item_theme(delbtn, self.btn_red_theme)

        with dpg.file_dialog(directory_selector=False, show=False, modal=True, label="Open Project", callback=self.open_project, tag="openprojectdialog", width=700, height=400):
            dpg.add_file_extension(".mledp", color=(0, 255, 0, 255), custom_text="[MLED Project]")

        with dpg.file_dialog(directory_selector=False, show=False, modal=True, label="Save Project", callback=self.save_project_callback, tag="saveprojectdialog", width=700, height=400):
            dpg.add_file_extension(".mledp", color=(0, 255, 0, 255), custom_text="[MLED Project]")

        with dpg.file_dialog(directory_selector=False, show=False, modal=True, label="Export to DPH_MAX7219", callback=self.export_header, tag="exportheaderdialog", width=700, height=400, default_filename="animation"):
            dpg.add_file_extension(".h", color=(0, 255, 0, 255), custom_text="[Header]")

            dpg.add_checkbox(label="Invert Vertical", tag="export_invert_vertical_checkbox", default_value=False)
            dpg.add_checkbox(label="Invert Horizontal", tag="export_invert_horizontal_checkbox", default_value=False)
            dpg.add_radio_button(["No Rotate", "90 clockwise", "90 counter-clockwise"], label="Rotate", tag="export_rotate_radiobutton", horizontal=False, default_value="No Rotate")
            dpg.add_spacer()
            dpg.add_checkbox(label="Include player helpper", tag="export_include_helper_checkbox", default_value=True)

    def menubar(self):
        with dpg.viewport_menu_bar(tag="menubar"):
            with dpg.menu(label="File"):
                dpg.add_menu_item(label="New Project", callback=lambda: dpg.configure_item("newprojectwindow", show=True))
                dpg.add_menu_item(label="Open Project", callback=lambda: dpg.show_item("openprojectdialog"))
                dpg.add_menu_item(label="Save Project", callback=lambda: self.save_project())
                dpg.add_menu_item(label="Save Project As...", callback=lambda: self.save_project(True))
                dpg.add_spacer()
                dpg.add_menu_item(label="Export to DPH_MAX7219 Header", callback=lambda: dpg.show_item("exportheaderdialog"))
                dpg.add_spacer()
                dpg.add_menu_item(label="Exit", callback=lambda: self.exit())

            dpg.add_spacer()
            dpg.add_button(label="start", callback=self.start_playback, tag="startbtn")
            dpg.add_button(label="stop/pause", callback=self.stop_playback, tag="stopbtn", show=False)

            # Enhanced frame status display
            dpg.add_text(f"Time: -/- | Frame: -/- | FPS: ???", tag="frame_status")

    def on_mouse_click(self, sender, app_data):
        self.wtimeline.handle_mouse_click(app_data)
        self.MLED.on_mouse_click(sender, app_data)

    def on_wheel_mouse(self, sender, app_data):
        self.wtimeline.handle_mouse_wheel(app_data)
        self.MLED.on_mouse_wheel(sender, app_data)

    def on_mouse_release(self, sender, app_data):
        self.wtimeline.handle_mouse_release(app_data)
        self.MLED.on_mouse_release(sender, app_data)

    def on_mouse_drag(self, sender, app_data):
        self.wtimeline.handle_mouse_drag(app_data)
        self.MLED.on_mouse_drag(sender, app_data)

    def on_key_press(self, sender, key):
        if key == 32:
            if not self.is_play:
                self.start_playback(None, None)
            else:
                self.stop_playback(None, None)
        elif key == 0x25:
            if self.is_play:
                self.stop_playback(None, None)

            self.wtimeline.current_frame -= 1
            self.wtimeline.set_playhead_frame(self.wtimeline.current_frame)
            self.timeline_object_callback(self.timeline.get_scene_state(self.wtimeline.current_frame))

            self.set_status(self.timeline.current_position, self.timeline.total_frames, self.timeline.frame_rate, 0, "SEEK", (-255, 0, 0, 255))
        elif key == 0x27:
            if self.is_play:
                self.stop_playback(None, None)

            self.wtimeline.current_frame += 1
            self.wtimeline.set_playhead_frame(self.wtimeline.current_frame)
            self.timeline_object_callback(self.timeline.get_scene_state(self.wtimeline.current_frame))

            self.set_status(self.timeline.current_position, self.timeline.total_frames, self.timeline.frame_rate, 0, "SEEK", (-255, 0, 0, 255))
        elif key == 85: # U for update
            self.update_mled_keyframe()

        #print(key)

    def set_status(self, cpos, tpos, fps, cfps, status=None, color=(-255, 0, 0, 255)):
        if cfps == 0 and status:
            cfps = status
        else:
            cfps = f"{cfps:.2f}/{fps:.2f}"

        current_time = datetime.fromtimestamp(cpos/fps)
        total_time = datetime.fromtimestamp(tpos/fps)

        time_format = "%H:%M:%S" if tpos/fps >= 3600 else "%M:%S"

        dpg.configure_item("frame_status", color=color)
        dpg.set_value("frame_status",
            (
                f"Time: {current_time.strftime(time_format)}/{total_time.strftime(time_format)} "
                f"| Frame: {cpos}/{tpos} "
                f"| FPS: {cfps}"
            ),
        )

    def init(self):
        dpg.create_context()
        icon = resource_path("icon.ico")
        dpg.create_viewport(title='Maxleda Animator', width=1280, height=720, small_icon=str(icon), large_icon=str(icon))  # set viewport window
        dpg.setup_dearpygui()

        with dpg.handler_registry():
            dpg.add_mouse_click_handler(callback=self.on_mouse_click)
            dpg.add_mouse_wheel_handler(callback=self.on_wheel_mouse)
            dpg.add_mouse_drag_handler(callback=self.on_mouse_drag)

            dpg.add_mouse_release_handler(callback=self.on_mouse_release)
            dpg.add_key_press_handler(callback=self.on_key_press)

        with dpg.theme() as self.btn_red_theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (255, 0, 0), category=dpg.mvThemeCat_Core)
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 0, category=dpg.mvThemeCat_Core)

        icons = [
            ["addicon", resource_path("addicon.png")],
            ["updateicon", resource_path("updateicon.png")]
        ]

        with dpg.texture_registry():
            for TEXTURE_TAG, IMAGE_PATH in icons:
                width, height, channels, data = dpg.load_image(IMAGE_PATH)
                dpg.add_dynamic_texture(width=width, height=height, default_value=data, tag=TEXTURE_TAG)

        dpg.configure_app(docking=True, docking_space=True)
        dpg.configure_app(init_file="workspace.ini")

        # -------------- add code here --------------
        self.window()
        self.menubar()
        #dpg.show_imgui_demo()

        self.wtimeline.render()

        # -------------------------------------------
        dpg.show_viewport()

        while dpg.is_dearpygui_running():
            self.render()
            dpg.render_dearpygui_frame()

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

            self.update_frame_rate_status()
            self.last_frame = self.wtimeline.current_frame

    def exit(self):
        dpg.destroy_context()

app = App()
app.init()