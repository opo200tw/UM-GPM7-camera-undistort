# Build
This build is for the C++ tools (`thermal_homography`, and the older `undistort_table`). The dewarp table needs no build, see [Dewarp table](#dewarp-table).

First, you have to build opencv 4.11.0 on your host. Follow the official instruction:
https://docs.opencv.org/4.x/d7/d9f/tutorial_linux_install.html

You can disable some unnecessary options for speedup:
```
# Download and unpack sources

wget -O opencv.zip https://github.com/opencv/opencv/archive/4.x.zip
wget -O opencv_contrib.zip https://github.com/opencv/opencv_contrib/archive/4.x.zip
unzip opencv.zip
unzip opencv_contrib.zip

# Build target

mkdir build
cd build
cmake -D OPENCV_EXTRA_MODULES_PATH=../opencv_contrib-4.11.0/modules ../opencv-4.11.0 \
      -D ENABLE_SSE3=OFF \
      -D OPENCV_GENERATE_PKGCONFIG=ON \
      -D WITH_TBB=OFF \
      -D WITH_V4L=ON \
      -D WITH_QT=OFF \
      -D WITH_GTK=ON \
      -D BUILD_opencv_python3=ON \
      -D BUILD_opencv_highgui=ON \
      -D WITH_OPENCL=OFF \
      -D BUILD_EXAMPLES=ON ..

cmake --build . -- -j 16
sudo make install
sudo ldconfig
```

Second, build our application

```
mkdir build
cd build
cmake ..
cd ..
make
```

# thermal_homography

### Purpose
Find a homography from thermal image to the camera.

### How to use it

#### 1. Setup thermal features
Connect 16 thermal feature points and make sure those features can be captured by both thermal camera and cmos camera.

![Thermal Feature Points](images/thermal_feature.png)

#### 2. Record thermal data
This method is dumb because there is no proper method to record thermal data so far.

 - Modify ```set_HTPA_debug_log(2);``` in ```sensorProject\HTPA\src\main.c``` for recording data.
 - Run HTPA project and record its console log.
 - Remove non integer log. Remove ~ 10 lines of log at the beginning. Search ```vdd``` and remove it.
   
#### 3. Record video on camera
I use gstreamer to record the RTSP stream.

 - Run tutk project
 - Run Gstreamer RTSP client to store the video. Please replace url and location.
 ```
 gst-launch-1.0 rtspsrc location=rtsp://192.168.0.31:8080 ! `
	application/x-rtp, media=video, encoding-name=H264  ! `
	queue ! rtph264depay ! h264parse ! tee name=t `
	t. ! queue ! matroskamux ! filesink location=received_h264.mkv `
	t. ! queue ! avdec_h264 ! autovideosink sync=false
 ```

#### 4. Execute thermal_homography
```
cd build
./thermal_homography [thermal_file] [video_file]
```
 - Input the number of feature points you have, 16 in our case.
 - For thermal data, press ```n``` for next frame, press ```space``` for clicking, press ```esc``` when you finished.
 - For video data, press ```n``` for next frame, press ```space``` for clicking, press ```esc``` when you finished.
 - The homography information is showed on the console.

# Dewarp table
`dewarp_table.py` turns chessboard footage into the `dewarp_int.bin` the firmware loads, with no window and no key presses. It needs Python 3 with `opencv-python` and `numpy` from pip; no OpenCV build.

The table is one little-endian 32-bit entry per output pixel of the stream: source row in bits 31..16, source column in bits 15..0, rounded to the nearest pixel and clamped into the frame. The firmware reads it with nearest-neighbour remapping, so no fractional table is written.

### 1. Record the raw stream
The RTSP stream is already remapped by the IPU when the card holds `dewarp_int.bin`. Take the file off the card first and check that the UART shows `Failed to open dewarp_int.bin, using Identity table` after boot; footage taken through an old table calibrates to a table that does nothing, and `calibrate` warns when that happens.

Record with `start_gstreamer.sh` (or pass the `rtsp://` URL straight to the script). Hold a chessboard with 6x9 inner corners (7x10 squares) in front of the camera and move it across the whole frame, corners and edges included, tilting it on the way.

### 2. Calibrate
`python3 dewarp_table.py calibrate <video, rtsp:// URL or image directory>` finds the board in every 10th frame, stops after 40 boards (or at the end of the input, or on Ctrl-C), calibrates and writes `camera_param.yml` and `dewarp_int.bin`. It prints the table size, its CRC32 and the largest pixel shift. It fails, writing nothing, when a frame is not 1280x720, the board is found in fewer than 10 frames, or the reprojection error is above 1 px. `--board`, `--size`, `--step`, `--max-views`, `--min-views`, `--max-rms`, `-o` and `--params` change those defaults; the shared ones (`--board`, `--size`, `--step`, `--max-views`) go before the subcommand.

### 3. Check
`python3 dewarp_table.py check <footage>` prints how far the board's rows and columns bend from straight lines (median and largest over the frames, in pixels). Adding `--table dewarp_int.bin` remaps each frame with the table first, the way the firmware does, so running it on the raw footage predicts the result. On the device, copy the table to the card root, check that the UART shows `Loaded dewarp table: 3686400 bytes from dewarp_int.bin, crc32 <value>` with the CRC32 `calibrate` printed, record again and run `check` on that footage: the bend should drop to about the value predicted on the raw footage.

### Tests
`python3 -m unittest discover tests` renders a chessboard through a known lens, calibrates it and compares the table with the one the known lens gives. It also checks the bit layout, rounding and clamping.

`src/undistort_table.cpp` is the earlier interactive tool. It needs camera parameters from `opencv_interactive-calibration` and shows each frame in a window; `dewarp_table.py` replaces it.