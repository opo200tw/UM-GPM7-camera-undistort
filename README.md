# Build
First, you have to build opencv 4.11.0 on your host. Follow the official instruction:
https://docs.opencv.org/4.x/d7/d9f/tutorial_linux_install.html

You can disable some unnecessary options for speedup:
```
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

# Undistort table
1. Record a video with a chessboard.
2. Get camera parameter with opencv tool.
```
./opencv_interactive-calibration -v=[video file] -t=chessboard -w=6 -h=9 -of=[camera_param.yaml]
```
3. Generate undistort table for General Plus format
```
./undistort_table ./undistort_video [video_file] [camera_param.yaml] [float_table_name] [int_table_name]
```