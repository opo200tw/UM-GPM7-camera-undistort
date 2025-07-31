cmake_minimum_required(VERSION 3.10)

project(thermal)

set(CMAKE_CXX_STANDARD 11)

# Find OpenCV package
find_package(OpenCV REQUIRED)

# Include directories
include_directories(${OpenCV_INCLUDE_DIRS})

add_executable(thermal_homography src/thermal_homography.cpp)
target_link_libraries(thermal_homography PRIVATE ${OpenCV_LIBS})

