import os
import platform
import time
import traceback
from datetime import datetime
import dearpygui.dearpygui as dpg
import threading
import uuid6

from DPGWidgets.timeline.timeline import Timeline, Curves
from DPGWidgets.timeline.widget import TimelineWidget
from DPGWidgets.MatrixLED import MatrixLEDWidget, MLED

if platform.system() == "Windows":
    from damp11113 import WindowsTaskbar, get_hwnd_from_pid

class App:
    def __init__(self):
        self.last_timeline_window_size = None
        self.timeline = Timeline(total_frames=30, fps=1)

        self.wtimeline = TimelineWidget("timeline", self.timeline)
        self.wtimeline.on_drag_playhead = self.timeline_on_drag_playhead
        self.wtimeline.editor_callback = self.timeline_editor_callback

        self.is_play = False
        self.last_window_size = (0, 0)

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
        data = self.timeline.objects[object_id].tracks[track_name].statements
        for stmt in data:
            if stmt.id == clip_id:
                if action == 0:
                    self.timeline.remove_statement(object_id, track_name, clip_id)
                    self.wtimeline.render()

                elif action == 1:
                    self.timeline.new_statement(
                        object_id,
                        track_name,
                        stmt.start_pos + 1,
                        stmt.end_pos + 2,
                        stmt.data
                    )
                    self.wtimeline.render()

                    # move playhead to new duplicated statement
                    self.wtimeline.set_playhead_frame(stmt.start_pos + 1)

                if action == -1:  # update
                    is_auto_clear = dpg.get_value("auto_clear_checkbox")

                    if isinstance(stmt.data, dict) and "clear_first" in stmt.data:
                        stmt.data["clear_first"] = is_auto_clear

                break

        self.wtimeline.render()

    def update_mled_keyframe(self):
        if not self.last_mled_change:
            return

        cpos = self.timeline.current_position

        for device_id, changed_pixels in self.last_mled_change.items():
            device_id_str = str(device_id)

            # Ensure timeline object exists
            if "mled" not in self.timeline.objects:
                self.timeline.create_object("mled")

            tracks = self.timeline.objects["mled"].tracks

            # Track missing → create first statement
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

            # 🧠 Build pixel map from existing data
            existing = {}
            if isinstance(stmt.data, dict) and "pixels" in stmt.data:
                existing = {(d["x"], d["y"]): d for d in stmt.data["pixels"]}
            elif isinstance(stmt.data, list):
                existing = {(d["x"], d["y"]): d for d in stmt.data}

            # 🔥 Update with new changed pixels
            for x, col in changed_pixels.items():
                for y, st in col.items():
                    existing[(x, y)] = {"x": x, "y": y, "state": st}

            # 🎯 Store FINAL JSON PACKET directly in the timeline
            stmt.data = {
                "clear_first": clear_first,
                "pixels": list(existing.values())
            }

        # Go to next frame
        self.timeline.set_position(cpos + 1)
        self.wtimeline.render()

    def update_taskbar(self, status=None, progress=None, reset=False):
        if self.taskbar:
            if reset:
                self.taskbar.reset()
                return

            if status:
                self.taskbar.setState(status)
            if progress:
                self.taskbar.setProgress(progress)

    def playback_thread(self):
        info = self.timeline.get_timeline_info()

        total_frames = info.get('total_frames', 0)
        frame_rate = info.get('frame_rate', 30.0)

        sleep_time = 1.0 / frame_rate

        while self.is_play:
            self.timeline_object_callback(self.timeline.get_scene_state(self.wtimeline.current_frame))

            # true frame rate
            start = time.perf_counter()
            while time.perf_counter() - start < sleep_time:
                pass

            if self.wtimeline.current_frame >= total_frames:
                self.stop_playback(None, None)
                break

            self.wtimeline.current_frame += 1
            self.frame_count += 1

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
        #
        try:
            print(data)
            # Reset current LED changes
            self.last_mled_change = {}

            if "mled" in data:
                for device in data["mled"].keys():
                    entry = data["mled"][device]
                    device_id = int(device)
                    pixels = entry.get("pixels", [])
                    is_clear_first = entry.get("clear_first", False)

                    if device_id not in self.last_mled_change:
                        self.last_mled_change[device_id] = {}

                    if is_clear_first:
                        self.MLED.clearDevice(device_id)

                    for px in pixels:
                        x = px["x"]
                        y = px["y"]
                        st = px["state"]

                        if x not in self.last_mled_change[device_id]:
                            self.last_mled_change[device_id][x] = {}

                        self.last_mled_change[device_id][x][y] = st

                        # update MLED widget immediately
                        self.MLED.setLed(device_id, x, y, st)

                        print(device_id, x, y, st)

            #self.ne.node_editor.process(data | {"mode": "normal"})
        except Exception as e:
            self.stop_playback(None, None)
            self.update_taskbar(status="error")
            print(traceback.format_exc())

    def start_playback(self, _, __):
        if self.is_play:
            return

        dpg.hide_item("startbtn")
        dpg.show_item("stopbtn")

        if self.wtimeline.current_frame >= self.timeline.total_frames:
            self.wtimeline.set_playhead_frame(0)
        else:
            self.update_taskbar(status="normal")

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

        if self.wtimeline.current_frame >= self.timeline.total_frames:
            self.update_taskbar(reset=True)
        else:
            self.update_taskbar(status="paused")

        # Update status when stopped
        self.wtimeline.is_play = False
        self.set_status(self.timeline.current_position, self.timeline.total_frames, self.timeline.frame_rate, 0, "STOPPED", (-255, 0, 0, 255))

    def window(self):
        with dpg.window(label="Timeline", tag="timelinewindow", width=500, height=320, no_close=True):
            with dpg.group(horizontal=True):
                with dpg.tooltip(dpg.add_image_button("addicon", width=20, height=20, callback=lambda: dpg.configure_item("addactionwindow", show=True))):
                    dpg.add_text("Add new action to the Matrix LED.")

                with dpg.tooltip(dpg.add_image_button("updateicon", width=20, height=20, callback=lambda: self.update_mled_keyframe())):
                    dpg.add_text("Add or override new LED matrix statement to the timeline at the current playhead position.")

            dpg.add_drawlist(self.wtimeline.width, self.wtimeline.height, tag="timeline")

        with dpg.window(label="Maxtrix LED", tag="matrixLEDwindow", width=500, height=320, no_close=True):
            dpg.add_drawlist(self.MLED.window_width, self.MLED.window_height, tag="matrix_canvas")

        with dpg.window(label="Add Action", tag="addactionwindow", width=300, height=150, no_close=True, show=False, modal=True):
            dpg.add_combo(label="Matrix Device", tag="devicelistcombo")
            dpg.add_spacer()
            dpg.add_text("Please select action to add:")
            with dpg.group():
                dpg.add_button(label="Clear All Pixel", width=120)
                dpg.add_button(label="Fill All Pixel", width=75)
                dpg.add_button(label="Invert Pixel", width=75)

                dpg.add_spacer(width=100)
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
                dpg.add_button(label="Cancel", width=75, callback=lambda: dpg.configure_item("modal_id", show=False))

                dpg.bind_item_theme(delbtn, self.btn_red_theme)

    def menubar(self):
        with dpg.viewport_menu_bar(tag="menubar"):
            with dpg.menu(label="File"):
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
        dpg.create_viewport(title='MatrixLED Animator', width=1280, height=720)  # set viewport window
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
            ["addicon", "addicon.png"],
            ["updateicon", "updateicon.png"]
        ]

        with dpg.texture_registry():
            for TEXTURE_TAG, IMAGE_PATH in icons:
                width, height, channels, data = dpg.load_image(IMAGE_PATH)
                dpg.add_dynamic_texture(width=width, height=height, default_value=data, tag=TEXTURE_TAG)

        dpg.configure_app(docking=True, docking_space=True)
        dpg.configure_app(init_file="workspace2.ini")

        # -------------- add code here --------------
        self.window()
        self.menubar()
        #dpg.show_imgui_demo()

        self.wtimeline.render()

        # -------------------------------------------
        dpg.show_viewport()

        if platform.system() == "Windows":
            self.taskbar = WindowsTaskbar(get_hwnd_from_pid(os.getpid()))

            self.taskbar.setIcon("mleda.ico")
            self.taskbar.setTitle("myapp")

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
            self.wtimeline.height = dpg.get_item_height("timelinewindow") - 65
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
            self.update_taskbar(progress=int((self.wtimeline.current_frame/self.timeline.total_frames)*100))
            self.last_frame = self.wtimeline.current_frame

    def exit(self):
        dpg.destroy_context()

app = App()
app.init()