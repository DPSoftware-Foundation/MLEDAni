import serial
import time

class MAX7219_Serial:
    """
    Python interface for controlling MAX7219 LED matrix over serial communication.
    Mirrors the Arduino DPH_MAX7219_Matrix library functions.
    """

    def __init__(self, port, baudrate=115200, timeout=1):
        """
        Initialize serial connection to Arduino.

        Args:
            port (str): Serial port (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux)
            baudrate (int): Baud rate for serial communication
            timeout (float): Read timeout in seconds
        """
        self.ser = serial.Serial(port, baudrate, timeout=timeout)

    def _send_command(self, cmd_id, *args):
        """Send command to Arduino with arguments."""
        # Format: [CMD_ID][ARG1][ARG2]...
        data = bytes([cmd_id] + list(args))
        self.ser.write(data)
        #time.sleep(0.01)  # Small delay for processing

    def clear(self):
        """Clear all displays."""
        self._send_command(0x01)

    def clear_device(self, device):
        """
        Clear specific device.

        Args:
            device (int): Device number (0-based)
        """
        self._send_command(0x02, device)

    def set_row(self, device, row, value):
        """
        Set entire row with byte value.

        Args:
            device (int): Device number
            row (int): Row number (0-7)
            value (int): Byte value (0-255)
        """
        self._send_command(0x03, device, row, value)

    def set_column(self, device, col, value):
        """
        Set entire column with byte value.

        Args:
            device (int): Device number
            col (int): Column number (0-7)
            value (int): Byte value (0-255)
        """
        self._send_command(0x04, device, col, value)

    def set_led(self, device, row, col, state):
        """
        Set individual LED state.

        Args:
            device (int): Device number
            row (int): Row number (0-7)
            col (int): Column number (0-7)
            state (bool): True for ON, False for OFF
        """
        self._send_command(0x05, device, row, col, 1 if state else 0)

    def set_pixel(self, x, y, state):
        """
        Set pixel at absolute coordinates.

        Args:
            x (int): X coordinate
            y (int): Y coordinate
            state (bool): True for ON, False for OFF
        """
        self._send_command(0x06, x, y, 1 if state else 0)

    def draw_bitmap(self, device, bitmap):
        """
        Draw 8x8 bitmap on device.

        Args:
            device (int): Device number
            bitmap (list/tuple): 8 bytes representing the bitmap
        """
        if len(bitmap) != 8:
            raise ValueError("Bitmap must be exactly 8 bytes")
        self._send_command(0x07, device, *bitmap)

    def set_intensity(self, intensity):
        """
        Set brightness for all displays.

        Args:
            intensity (int): Brightness level (0-15)
        """
        self._send_command(0x08, intensity & 0x0F)

    def set_intensity_device(self, device, intensity):
        """
        Set brightness for specific device.

        Args:
            device (int): Device number
            intensity (int): Brightness level (0-15)
        """
        self._send_command(0x09, device, intensity & 0x0F)

    def close(self):
        """Close serial connection."""
        self.ser.close()


# Example usage
if __name__ == "__main__":
    # Connect to Arduino (change 'COM3' to your port)
    display = MAX7219_Serial('COM14', baudrate=115200)

    try:
        # Clear display
        display.clear()
        display.set_intensity(5)

        # Draw pattern similar to Arduino example
        for y in range(8):
            for x in range(8):
                display.set_led(0, x, y, True)
                time.sleep(0.05)

        time.sleep(1)
        display.clear()

        # Draw a bitmap (smiley face)
        smiley = [
            0b00111100,
            0b01000010,
            0b10100101,
            0b10000001,
            0b10100101,
            0b10011001,
            0b01000010,
            0b00111100
        ]
        display.draw_bitmap(0, smiley)

        # Fade effect
        for brightness in range(16):
            display.set_intensity(brightness)
            time.sleep(0.1)

    finally:
        display.close()