import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, List, Dict, Optional


class OpenCVImporter:
    """Import video or image files to timeline using OpenCV"""

    def __init__(self, timeline, mled_width: int = 16, mled_height: int = 16):
        """
        Initialize the OpenCV importer

        Args:
            timeline: Timeline object to import into
            mled_width: Width of MLED display (default 16)
            mled_height: Height of MLED display (default 16)
        """
        self.timeline = timeline
        self.mled_width = mled_width
        self.mled_height = mled_height

    def frame_to_pixels(self, frame: np.ndarray, threshold: int = 128) -> List[Dict]:
        """
        Convert a frame to MLED pixel format

        Args:
            frame: OpenCV frame (BGR format)
            threshold: Brightness threshold for pixel state (0-255)

        Returns:
            List of pixel dictionaries with x, y, state
        """
        # Resize frame to MLED dimensions
        resized = cv2.resize(frame, (self.mled_width, self.mled_height),
                             interpolation=cv2.INTER_AREA)

        # Convert to grayscale
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)

        # Generate pixel list (only include lit pixels)
        pixels = []
        for y in range(self.mled_height):
            for x in range(self.mled_width):
                brightness = gray[y, x]
                if brightness >= threshold:
                    # Map brightness to state (1-255)
                    state = max(1, int((brightness / 255.0) * 255))
                    pixels.append({"x": x, "y": y, "state": state})

        return pixels

    def import_image(self,
                     image_path: str,
                     device_id: str = "0",
                     start_pos: int = 0,
                     duration: int = 30,
                     intensity: int = 255,
                     threshold: int = 128) -> bool:
        """
        Import a single image to timeline

        Args:
            image_path: Path to image file
            device_id: MLED device ID (as string)
            start_pos: Timeline position to start at
            duration: How many frames to hold the image
            intensity: LED intensity (0-255)
            threshold: Brightness threshold for pixel detection

        Returns:
            True if successful, False otherwise
        """
        try:
            # Load image
            frame = cv2.imread(image_path)
            if frame is None:
                print(f"Error: Could not load image {image_path}")
                return False

            # Convert to pixels
            pixels = self.frame_to_pixels(frame, threshold)

            # Ensure timeline object exists
            if "mled" not in self.timeline.objects:
                self.timeline.create_object("mled")

            # Create statement with duration
            self.timeline.new_statement(
                "mled",
                device_id,
                start_pos,
                start_pos + duration,
                {
                    "clear_first": True,
                    "pixels": pixels,
                    "intensity": intensity
                }
            )

            print(f"Imported image: {image_path} ({len(pixels)} pixels lit)")
            return True

        except Exception as e:
            print(f"Error importing image: {e}")
            return False

    def import_video(self,
                     video_path: str,
                     device_id: str = "0",
                     start_pos: int = 0,
                     intensity: int = 15,
                     threshold: int = 128,
                     frame_skip: int = 0,
                     max_frames: Optional[int] = None) -> bool:
        """
        Import video file to timeline

        Args:
            video_path: Path to video file
            device_id: MLED device ID (as string)
            start_pos: Timeline position to start at
            intensity: LED intensity (0-255)
            threshold: Brightness threshold for pixel detection
            frame_skip: Number of frames to skip between imports (0 = import every frame)
            max_frames: Maximum number of frames to import (None = all frames)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Open video
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"Error: Could not open video {video_path}")
                return False

            # Get video properties
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            print(f"Video: {video_path}")
            print(f"FPS: {fps}, Total frames: {total_frames}")

            # Ensure timeline object exists
            if "mled" not in self.timeline.objects:
                self.timeline.create_object("mled")

            frame_count = 0
            imported_count = 0
            current_pos = start_pos

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Check if we should process this frame
                if frame_count % (frame_skip + 1) == 0:
                    # Convert to pixels
                    pixels = self.frame_to_pixels(frame, threshold)

                    # Create statement for this frame (1 frame duration)
                    self.timeline.new_statement(
                        "mled",
                        device_id,
                        current_pos,
                        current_pos + 1,
                        {
                            "clear_first": False,  # Don't clear between frames
                            "pixels": pixels,
                            "intensity": intensity
                        }
                    )

                    current_pos += 1
                    imported_count += 1

                    # Check max frames limit
                    if max_frames and imported_count >= max_frames:
                        break

                    # Progress indicator
                    if imported_count % 10 == 0:
                        print(f"Imported {imported_count} frames...")

                frame_count += 1

            cap.release()

            print(f"Import complete: {imported_count} frames imported to timeline")
            return True

        except Exception as e:
            print(f"Error importing video: {e}")
            return False

    def import_with_color_mapping(self,
                                  source_path: str,
                                  device_id: str = "0",
                                  start_pos: int = 0,
                                  intensity: int = 255,
                                  color_mode: str = "brightness",
                                  **kwargs) -> bool:
        """
        Import with advanced color mapping options

        Args:
            source_path: Path to image or video
            device_id: MLED device ID
            start_pos: Timeline start position
            intensity: LED intensity
            color_mode: "brightness", "red", "green", "blue", "custom"
            **kwargs: Additional arguments for import_image or import_video

        Returns:
            True if successful
        """
        # Determine if source is image or video
        path = Path(source_path)
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv'}
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}

        if path.suffix.lower() in video_extensions:
            return self.import_video(source_path, device_id, start_pos,
                                     intensity, **kwargs)
        elif path.suffix.lower() in image_extensions:
            return self.import_image(source_path, device_id, start_pos,
                                     intensity=intensity, **kwargs)
        else:
            print(f"Error: Unsupported file format {path.suffix}")
            return False