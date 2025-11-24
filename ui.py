import time
from datetime import datetime
import dearpygui.dearpygui as dpg

class GUI:
    def __init__(self, appself):
        self.app = appself

        self.actual_frame_rate = 0.0
        self.frame_count = 0
        self.frame_start_time = 0

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
        fps_ratio = self.actual_frame_rate / self.app.timeline.frame_rate if self.app.timeline.frame_rate > 0 else 1.0

        if fps_ratio >= 0.9:  # Normal (realtime) - Green
            color = (0, 255, 0, 255)  # Green
        elif fps_ratio >= 0.5:  # Slower but not more than half - Yellow
            color = (255, 255, 0, 255)  # Yellow
        else:  # Slower than half - Red
            color = (255, 0, 0, 255)  # Red

        self.set_status(self.app.timeline.current_position, self.app.timeline.total_frames, self.app.timeline.frame_rate, self.actual_frame_rate, None, color)

    def open_add_action_modal(self):
        # Populate device list
        device_list = []
        for device, devdata in self.app.MLED.devices.items():
            device_list.append(f"Device {device} ({devdata.label}) ({devdata.width}x{devdata.height})")

        dpg.configure_item("devicelistcombo", items=device_list, default_value=device_list[0] if device_list else "")

        dpg.configure_item("addactionwindow", show=True)

    def open_property_modal(self):
        if not self.app.selected_object_tl:
            return

        object_id, track_name, clip_id = self.app.selected_object_tl

        data = self.app.timeline.objects[object_id].tracks[track_name].statements

        for stmt in data:
            if stmt.id == clip_id:
                #print("Open property modal for:", stmt)

                if isinstance(stmt.data, dict) and "clear_first" in stmt.data:
                    dpg.set_value("auto_clear_checkbox", stmt.data["clear_first"])
                else:
                    dpg.set_value("auto_clear_checkbox", True)

                dpg.configure_item("modal_id", show=True)

                break

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

    def window(self):
        with dpg.window(label="Timeline", tag="timelinewindow", width=500, height=320, no_close=True):

            with dpg.group(horizontal=True):
                with dpg.group(tag="startbtn"):
                    with dpg.tooltip(dpg.add_image_button("playicon", width=20, height=20, callback=self.app.start_playback)):
                        dpg.add_text("Play")

                with dpg.group(tag="stopbtn", show=False):
                    with dpg.tooltip(dpg.add_image_button("stopicon", width=20, height=20, callback=self.app.stop_playback)):
                        dpg.add_text("Pause and Stop")

                dpg.add_spacer(width=25)

                with dpg.tooltip(dpg.add_image_button("addicon", width=20, height=20, callback=lambda: self.open_add_action_modal())):
                    dpg.add_text("Add new action to the Matrix LED.")

                with dpg.tooltip(dpg.add_image_button("updateicon", width=20, height=20, callback=lambda: self.app.update_mled_keyframe())):
                    dpg.add_text("Add or override new LED matrix statement to the timeline at the current playhead position.")

                with dpg.tooltip(dpg.add_image_button("importicon", width=20, height=20, callback=lambda: dpg.show_item("oivdialog"))):
                    dpg.add_text("Import Video or Image")

                dpg.add_slider_int(label="Intensity", tag="intensity_slider", default_value=15, min_value=0, max_value=15, width=100, height=20)

            dpg.add_drawlist(self.app.wtimeline.width, self.app.wtimeline.height, tag="timeline")

            with dpg.group(horizontal=True):
                dpg.add_input_int(label="Length (frames)", tag="plengthin", default_value=self.app.project_length, width=150, callback=self.app.change_project_settings)
                dpg.add_input_int(label="Frame Rate (FPS)", tag="pfpsin", default_value=self.app.project_fps, width=150, callback=self.app.change_project_settings)
                dpg.add_checkbox(label="Loop", default_value=self.app.is_loop_enable, callback=lambda s, a: setattr(self.app, 'is_loop_enable', a))

        with dpg.window(label="Maxtrix LED", tag="matrixLEDwindow", width=500, height=320, no_close=True):
            dpg.add_drawlist(self.app.MLED.window_width, self.app.MLED.window_height, tag="matrix_canvas")

        with dpg.window(label="New Project", tag="newprojectwindow", no_close=False, show=False, modal=True):
            dpg.add_input_text(label="Project Name", tag="newprojectnamein", default_value="Untitled", width=200)
            dpg.add_input_int(label="Project Length (frames)", tag="newprojectlengthin", default_value=300, width=200)
            dpg.add_input_int(label="Project Frame Rate (FPS)", tag="newprojectfpsin", default_value=6, width=200)
            dpg.add_input_int(label="Number of Matrix LED Devices", tag="newprojectdevicescountin", default_value=1, width=200, min_value=1, min_clamped=True)
            dpg.add_text("For editing layout of Matrix LED devices, please do it after creating the project and edit at project file.")
            dpg.add_spacer()
            dpg.add_text("Note: This will reset current project. Please save first!")
            with dpg.group(horizontal=True):
                dpg.add_button(label="Create", width=75, callback=lambda: self.app.new_project(
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
                dpg.add_button(label="Clear All Pixel", width=120, callback=lambda: self.app.add_action_callback(0))
                dpg.add_button(label="Fill All Pixel", width=120, callback=lambda: self.app.add_action_callback(1))

                dpg.add_spacer(width=150)
                dpg.add_button(label="Cancel", width=75, callback=lambda: dpg.configure_item("addactionwindow", show=False))

        with dpg.window(label="Action", modal=True, show=False, tag="modal_id", no_title_bar=True):
            dpg.add_text("Please select action for the selected item:")
            dpg.add_separator()
            with dpg.group():
                dpg.add_checkbox(label="Auto Clear Before Action", tag="auto_clear_checkbox", default_value=True)
                dpg.add_button(label="Update", width=75, callback=lambda: self.app.property_modal_callback(-1))
                dpg.add_spacer()
                dpg.add_button(label="Duplicate", width=75, callback=lambda: self.app.property_modal_callback(1))
                delbtn = dpg.add_button(label="Delete", width=75, callback=lambda: self.app.property_modal_callback(0))
                dpg.add_spacer(width=100)
                dpg.add_button(label="Cancel", width=75, callback=lambda: self.app.property_modal_callback(-2))

                dpg.bind_item_theme(delbtn, self.app.btn_red_theme)

        with dpg.file_dialog(directory_selector=False, show=False, modal=True, label="Open Project", callback=self.app.open_project, tag="openprojectdialog", width=700, height=400):
            dpg.add_file_extension(".mledp", color=(0, 255, 0, 255), custom_text="[MLED Project]")

        with dpg.file_dialog(directory_selector=False, show=False, modal=True, label="Save Project", callback=self.app.save_project_callback, tag="saveprojectdialog", width=700, height=400):
            dpg.add_file_extension(".mledp", color=(0, 255, 0, 255), custom_text="[MLED Project]")

        with dpg.file_dialog(directory_selector=False, show=False, modal=True, label="Export to DPH_MAX7219", callback=self.app.export_header, tag="exportheaderdialog", width=700, height=400, default_filename="animation"):
            dpg.add_file_extension(".h", color=(0, 255, 0, 255), custom_text="[Header]")

            dpg.add_checkbox(label="Invert Vertical", tag="export_invert_vertical_checkbox", default_value=False)
            dpg.add_checkbox(label="Invert Horizontal", tag="export_invert_horizontal_checkbox", default_value=False)
            dpg.add_radio_button(["No Rotate", "90 clockwise", "90 counter-clockwise"], label="Rotate", tag="export_rotate_radiobutton", horizontal=False, default_value="No Rotate")
            dpg.add_spacer()
            dpg.add_checkbox(label="Include player helpper", tag="export_include_helper_checkbox", default_value=True)

        with dpg.file_dialog(directory_selector=False, show=False, modal=True, label="Import Video or Image", callback=self.app.import_iv, tag="oivdialog", width=700, height=400):
            dpg.add_file_extension(".mp4", color=(0, 255, 0, 255), custom_text="[Video]")
            dpg.add_file_extension(".mkv", color=(0, 255, 0, 255), custom_text="[Video]")
            dpg.add_file_extension(".jpeg", color=(0, 255, 0, 255), custom_text="[Image]")
            dpg.add_file_extension(".jpg,", color=(0, 255, 0, 255), custom_text="[Image]")
            dpg.add_file_extension(".png", color=(0, 255, 0, 255), custom_text="[Image]")

            dpg.add_checkbox(label="Invert Vertical", tag="oiv_invert_vertical_checkbox", default_value=False)
            dpg.add_checkbox(label="Invert Horizontal", tag="oiv_invert_horizontal_checkbox", default_value=False)
            dpg.add_radio_button(["No Rotate", "90 clockwise", "90 counter-clockwise"], label="Rotate", tag="oiv_rotate_radiobutton", horizontal=False, default_value="No Rotate")

        with dpg.window(label="Configuration", tag="configwindow", show=False, modal=True, width=500):
            with dpg.tab_bar():
                with dpg.tab(label="Live Preview"):
                    dpg.add_checkbox(label="Enable", default_value=self.app.appconfig.lp_ena, callback=lambda s, a: setattr(self.app.appconfig, 'lp_ena', a))
                    dpg.add_input_text(label="Serial Port", default_value=self.app.appconfig.lp_port, callback=lambda s, a: setattr(self.app.appconfig, 'lp_port', a))
                    dpg.add_input_int(label="Baud Rate", default_value=self.app.appconfig.lp_speed, callback=lambda s, a: setattr(self.app.appconfig, 'lp_speed', a))
                    dpg.add_text("For USB-CDC supported. It work with any baud rate.")
                    dpg.add_spacer(height=5)
                    dpg.add_text("Matrix LED Device Settings:")
                    dpg.add_checkbox(label="Invert Vertical", default_value=self.app.appconfig.lp_mled_invertV, callback=lambda s, a: setattr(self.app.appconfig, 'lp_mled_invertV', a))
                    dpg.add_checkbox(label="Invert Horizontal", default_value=self.app.appconfig.lp_mled_invertH, callback=lambda s, a: setattr(self.app.appconfig, 'lp_mled_invertH', a))
                    dpg.add_radio_button(["No Rotate", "90 clockwise", "90 counter-clockwise"], label="Rotate", horizontal=True, default_value=self.app.appconfig.lp_mled_rotate, callback=lambda s, a: setattr(self.app.appconfig, 'lp_mled_rotate', a))

            dpg.add_spacer(height=10)
            dpg.add_text("Please restart the application to apply changes for some settings.")

        with dpg.window(label="About", tag="aboutwindow", show=False):
            dpg.add_text(self.app.apptitle)
            dpg.add_text(f"Version {self.app.appversion}")
            dpg.add_spacer()
            dpg.add_text(f"Copyright (C) 2024-2025 DPSoftware Foundation All rights reserved. (GPLv3)")

    def menubar(self):
        with dpg.viewport_menu_bar(tag="menubar"):
            with dpg.menu(label="File"):
                dpg.add_menu_item(label="New Project", callback=lambda: dpg.configure_item("newprojectwindow", show=True))
                dpg.add_menu_item(label="Open Project", callback=lambda: dpg.show_item("openprojectdialog"))
                dpg.add_menu_item(label="Save Project", callback=lambda: self.app.save_project())
                dpg.add_menu_item(label="Save Project As...", callback=lambda: self.app.save_project(True))
                dpg.add_spacer()
                dpg.add_menu_item(label="Export to DPH_MAX7219 Header", callback=lambda: dpg.show_item("exportheaderdialog"))
                dpg.add_spacer()
                dpg.add_menu_item(label="Exit", callback=lambda: self.app.exit())
            with dpg.menu(label="Config"):
                dpg.add_menu_item(label="Configuration", callback=lambda: dpg.configure_item("configwindow", show=True))
            with dpg.menu(label="Help"):
                dpg.add_menu_item(label="About", callback=lambda: dpg.configure_item("aboutwindow", show=True))

            # Enhanced frame status display
            dpg.add_text(f"Time: -/- | Frame: -/- | FPS: ???", tag="frame_status")