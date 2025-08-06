cmake_minimum_required(VERSION 3.10)

project(image_tool)

set(CMAKE_CXX_STANDARD 11)

# Set OpenCV_DIR to point to the local build
set(OpenCV_DIR ${CMAKE_CURRENT_SOURCE_DIR}/build)
set(CMAKE_PREFIX_PATH ${CMAKE_CURRENT_SOURCE_DIR}/build ${CMAKE_PREFIX_PATH})

# Find OpenCV package
find_package(OpenCV REQUIRED)

# Include directories
include_directories(${OpenCV_INCLUDE_DIRS})

add_executable(thermal_homography src/thermal_homography.cpp)
target_link_libraries(thermal_homography PRIVATE ${OpenCV_LIBS})

add_executable(undistort_table src/undistort_table.cpp)
target_link_libraries(undistort_table ${OpenCV_LIBS})

