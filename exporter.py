def export_to_arduino_header(timeline, devices_info, project_name="animation", fps=6,
                             invert_horizontal=False, invert_vertical=False, rotate=0, player=True):
    """
    Export timeline animation to Arduino header file

    Args:
        timeline: Timeline object with animation data
        devices_info: List/dict of device configurations
        project_name: Name for the header file and arrays
        fps: Frames per second for timing
        invert_horizontal: Flip animation horizontally (mirror X axis)
        invert_vertical: Flip animation vertically (mirror Y axis)
        rotate: Rotation option (0=none, 1=90° CW, 2=90° CCW)

    Returns:
        String containing the complete header file content
    """
    # Prepare project name
    project_name = project_name.strip()
    safe_name = project_name.replace(" ", "_").replace("-", "_")

    # Determine matrix dimensions (assuming 8x8 for MAX7219)
    MATRIX_WIDTH = 8
    MATRIX_HEIGHT = 8

    def transform_pixel(x, y):
        """Apply transformations to pixel coordinates"""
        # Apply rotation first
        if rotate == 1:  # 90° CW
            x, y = MATRIX_HEIGHT - 1 - y, x
        elif rotate == 2:  # 90° CCW
            x, y = y, MATRIX_WIDTH - 1 - x

        # Apply horizontal inversion (mirror X)
        if invert_horizontal:
            x = MATRIX_WIDTH - 1 - x

        # Apply vertical inversion (mirror Y)
        if invert_vertical:
            y = MATRIX_HEIGHT - 1 - y

        return x, y

    # Collect all frames with changes
    frames_data = []
    total_frames = int(timeline.total_frames)

    for frame in range(total_frames):
        # Get scene state at this frame
        frame_data = timeline.get_scene_state(frame)

        if "mled" in frame_data and frame_data["mled"]:
            # Transform pixel coordinates in the frame data
            transformed_frame = {}
            for device_id, device_data in frame_data["mled"].items():
                transformed_device = device_data.copy()

                # Transform pixels if they exist
                if "pixels" in device_data and device_data["pixels"]:
                    transformed_pixels = []
                    for px in device_data["pixels"]:
                        new_x, new_y = transform_pixel(px["x"], px["y"])
                        transformed_pixels.append({
                            "x": new_x,
                            "y": new_y,
                            "state": px["state"]
                        })
                    transformed_device["pixels"] = transformed_pixels

                transformed_frame[device_id] = transformed_device

            frames_data.append((frame, transformed_frame))

    # Build header file
    header = []
    guard_name = f"{project_name.upper()}_ANIMATION_H"

    header.append(f"#ifndef {guard_name}")
    header.append(f"#define {guard_name}")
    header.append("")
    header.append("// Auto-generated animation data")
    header.append(f"// Project: {project_name}")
    header.append(f"// FPS: {fps}")
    header.append(f"// Total Frames: {total_frames}")
    header.append(f"// Frame Duration: {1000 // fps}ms")
    header.append(f"// Invert Horizontal: {invert_horizontal}")
    header.append(f"// Invert Vertical: {invert_vertical}")
    header.append(f"// Rotate: {['None', '90° CW', '90° CCW'][rotate] if rotate in [0, 1, 2] else 'Invalid'}")
    header.append("")

    # Animation metadata
    header.append(f"const uint16_t ANIM_TOTAL_FRAMES = {total_frames};")
    header.append(f"const uint8_t ANIM_FPS = {fps};")
    header.append(f"const uint16_t ANIM_FRAME_DELAY = {1000 // fps};")
    header.append(f"const uint16_t ANIM_KEYFRAME_COUNT = {len(frames_data)};")
    header.append("")

    # Generate compact frame data
    # Format: frame_number, device_id, action_type, data_count, [data...]
    # action_type: 0=clear, 1=set_intensity, 2=set_pixels

    header.append("// Frame data format: frame, device, action, count, [data...]")
    header.append("// Actions: 0=clear, 1=intensity, 2=pixels")
    header.append(f"const uint16_t PROGMEM {safe_name.lower()}_data[] = {{")

    data_entries = []

    for frame_num, devices in frames_data:
        for device_id, device_data in devices.items():
            dev_id = int(device_id)

            # Clear action
            if device_data.get("clear_first", False):
                data_entries.append(f"  {frame_num}, {dev_id}, 0, 0")

            # Intensity action
            intensity = device_data.get("intensity", 15)
            data_entries.append(f"  {frame_num}, {dev_id}, 1, 1, {intensity}")

            # Pixel data - encode as row bytes for space efficiency
            pixels = device_data.get("pixels", [])
            if pixels:
                # Convert pixel list to row-based encoding
                rows = {}
                for px in pixels:
                    x, y, state = px["x"], px["y"], px["state"]
                    if y not in rows:
                        rows[y] = 0
                    if state:
                        rows[y] |= (1 << x)

                # Emit row data
                row_data = []
                for row in sorted(rows.keys()):
                    row_data.append(f"{row}, {rows[row]}")

                data_entries.append(
                    f"  {frame_num}, {dev_id}, 2, {len(rows)}, " + ", ".join(row_data)
                )

    header.append(",\n".join(data_entries))
    header.append("};")
    header.append("")

    # Calculate total data size
    total_size = sum(line.count(',') + 1 for line in data_entries)
    header.append(f"#define {safe_name}_DATA_SIZE {total_size}")
    header.append(f"const uint16_t ANIM_DATA_SIZE = {total_size};")
    header.append("")

    # Legacy single-animation playback helper
    header.append("// Legacy single animation playback helper")
    header.append("// For multiple animations, use MultiAnimationPlayer.h instead")
    header.append(f"const uint16_t* const animationData PROGMEM = {safe_name.lower()}_data;")
    header.append("")

    # Helper functions
    if player:
        header.append("// Single Animation playback helper class")
        header.append("class AnimationPlayer {")
        header.append("private:")
        header.append("  uint16_t dataIndex;")
        header.append("  uint16_t currentFrame;")
        header.append("  unsigned long lastUpdate;")
        header.append("  ")
        header.append("public:")
        header.append("  AnimationPlayer() : dataIndex(0), currentFrame(0), lastUpdate(0) {}")
        header.append("  ")
        header.append("  void begin() {")
        header.append("    dataIndex = 0;")
        header.append("    currentFrame = 0;")
        header.append("    lastUpdate = millis();")
        header.append("  }")
        header.append("  ")
        header.append("  bool update(MAX7219_LED_MATRIX& display) {")
        header.append("    unsigned long now = millis();")
        header.append("    if (now - lastUpdate < ANIM_FRAME_DELAY) return false;")
        header.append("    ")
        header.append("    lastUpdate = now;")
        header.append("    ")
        header.append("    // Process all actions for current frame")
        header.append("    while (dataIndex < ANIM_DATA_SIZE) {")
        header.append("      uint16_t frame = pgm_read_word(&animationData[dataIndex++]);")
        header.append("      if (frame > currentFrame) {")
        header.append("        dataIndex--; // Push back")
        header.append("        break;")
        header.append("      }")
        header.append("      ")
        header.append("      uint8_t device = pgm_read_word(&animationData[dataIndex++]);")
        header.append("      uint8_t action = pgm_read_word(&animationData[dataIndex++]);")
        header.append("      uint8_t count = pgm_read_word(&animationData[dataIndex++]);")
        header.append("      ")
        header.append("      if (action == 0) { // Clear")
        header.append("        display.clearDevice(device);")
        header.append("      } else if (action == 1) { // Intensity")
        header.append("        uint8_t intensity = pgm_read_word(&animationData[dataIndex++]);")
        header.append("        display.setIntensityDevice(device, intensity);")
        header.append("      } else if (action == 2) { // Pixels")
        header.append("        for (uint8_t i = 0; i < count; i++) {")
        header.append("          uint8_t row = pgm_read_word(&animationData[dataIndex++]);")
        header.append("          uint8_t value = pgm_read_word(&animationData[dataIndex++]);")
        header.append("          display.setRow(device, row, value);")
        header.append("        }")
        header.append("      }")
        header.append("    }")
        header.append("    ")
        header.append("    currentFrame++;")
        header.append("    ")
        header.append("    // Loop or stop")
        header.append("    if (currentFrame >= ANIM_TOTAL_FRAMES) {")
        header.append("      currentFrame = 0;")
        header.append("      dataIndex = 0;")
        header.append("      return true; // Animation completed")
        header.append("    }")
        header.append("    ")
        header.append("    return false;")
        header.append("  }")
        header.append("};")
        header.append("")

    header.append(f"#endif // {guard_name}")

    return "\n".join(header)


# Example usage in App class:
def add_export_to_app_class():
    """
    Add this method to your App class to enable Arduino export
    """
    code = '''
    def export_to_arduino_callback(self, sender, app_data):
        """Export animation to Arduino header file"""
        filepath = app_data['file_path_name']

        # Ensure .h extension
        if not filepath.endswith('.h'):
            filepath += '.h'

        # Get project name from filename
        import os
        project_name = os.path.splitext(os.path.basename(filepath))[0]

        # Get inversion settings (add checkboxes to your UI for these)
        invert_h = False  # dpg.get_value("invert_horizontal_checkbox")
        invert_v = False  # dpg.get_value("invert_vertical_checkbox")

        # Generate header content
        header_content = export_to_arduino_header(
            self.timeline,
            self.MLED.devices,
            project_name=project_name,
            fps=self.project_fps,
            invert_horizontal=invert_h,
            invert_vertical=invert_v
        )

        # Write to file
        with open(filepath, 'w') as f:
            f.write(header_content)

        print(f"Arduino header exported to: {filepath}")
    '''
    return code


# Example Arduino sketch using the generated header
def generate_example_sketch():
    """Generate example Arduino sketch"""
    sketch = '''
#include "DPH_MAX7219_Matrix.h"
#include "animation.h"  // Your generated header file

MAX7219_LED_MATRIX display(0, 2, 1, 1);
AnimationPlayer player;

void setup() {
  display.begin();
  display.clear();
  player.begin();
}

void loop() {
  bool completed = player.update(display);

  if (completed) {
    // Animation loop completed
    // Add delay or do something else
    delay(1000);
  }
}
'''
    return sketch


if __name__ == "__main__":
    print("Arduino Header Exporter for MatrixLED Animator")
    print("=" * 50)
    print("\nThis module provides space-efficient Arduino export.")
    print("\nFeatures:")
    print("- Row-based byte encoding (8 pixels = 1 byte)")
    print("- PROGMEM storage for flash memory")
    print("- Built-in playback helper class")
    print("- Frame timing management")
    print("\nAdd the export_to_arduino_callback method to your App class")
    print("to enable Arduino header file export from your application.")