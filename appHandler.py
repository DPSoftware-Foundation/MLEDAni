import dearpygui.dearpygui as dpg

class InputHandler:
    def __init__(self, appself):
        self.app = appself

    def on_mouse_click(self, sender, app_data):
        self.app.wtimeline.handle_mouse_click(app_data)
        self.app.MLED.on_mouse_click(sender, app_data)

    def on_wheel_mouse(self, sender, app_data):
        self.app.wtimeline.handle_mouse_wheel(app_data)
        self.app.MLED.on_mouse_wheel(sender, app_data)

    def on_mouse_release(self, sender, app_data):
        self.app.wtimeline.handle_mouse_release(app_data)
        self.app.MLED.on_mouse_release(sender, app_data)

    def on_mouse_drag(self, sender, app_data):
        self.app.wtimeline.handle_mouse_drag(app_data)
        self.app.MLED.on_mouse_drag(sender, app_data)

    def on_key_press(self, sender, key):
        if key == 32:
            if not self.app.is_play:
                self.app.start_playback(None, None)
            else:
                self.app.stop_playback(None, None)
        elif key == 0x25:
            if self.app.is_play:
                self.app.stop_playback(None, None)

            self.app.wtimeline.current_frame -= 1
            self.app.wtimeline.set_playhead_frame(self.app.wtimeline.current_frame)
            self.app.timeline_object_callback(self.app.timeline.get_scene_state(self.app.wtimeline.current_frame))

            self.app.gui.set_status(self.app.timeline.current_position, self.app.timeline.total_frames, self.app.timeline.frame_rate, 0, "SEEK", (-255, 0, 0, 255))
        elif key == 0x27:
            if self.app.is_play:
                self.app.stop_playback(None, None)

            self.app.wtimeline.current_frame += 1
            self.app.wtimeline.set_playhead_frame(self.app.wtimeline.current_frame)
            self.app.timeline_object_callback(self.app.timeline.get_scene_state(self.app.wtimeline.current_frame))

            self.app.gui.set_status(self.app.timeline.current_position, self.app.timeline.total_frames, self.app.timeline.frame_rate, 0, "SEEK", (-255, 0, 0, 255))
        elif key == 85: # U for update
            self.app.update_mled_keyframe()

        #print(key)

    def register(self):
        with dpg.handler_registry():
            dpg.add_mouse_click_handler(callback=self.on_mouse_click)
            dpg.add_mouse_wheel_handler(callback=self.on_wheel_mouse)
            dpg.add_mouse_drag_handler(callback=self.on_mouse_drag)

            dpg.add_mouse_release_handler(callback=self.on_mouse_release)
            dpg.add_key_press_handler(callback=self.on_key_press)