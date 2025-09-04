#include <opencv2/opencv.hpp>
#include <iostream>
#include <fstream>

using namespace std;

void write_gp_map(const cv::Mat &map1, cv::Mat &map2, 
            const std::string &float_table_name, const std::string &int_table_name) {
    std::ofstream out_file_float(float_table_name, std::ios::binary);
    if (!out_file_float.is_open()) {
        std::cerr << "Failed to open file for writing: " << float_table_name << std::endl;
        return;
    }
    std::ofstream out_file_int(int_table_name, std::ios::binary);
    if (!out_file_int.is_open()) {
        std::cerr << "Failed to open file for writing: " << int_table_name << std::endl;
        return;
    }
    for (int i=0;i<map1.rows;++i) {
        for (int j=0;j<map1.cols;++j) {
            /*
            4 bit X fraction | 12 bit X integer | 4 bit Y fraction | 12 bit Y integer 
            */
            int val = 0;
            // Reconstruct full floating-point coordinates from OpenCV maps
            short ix_cv = map1.at<cv::Vec2s>(i, j)[0];
            short iy_cv = map1.at<cv::Vec2s>(i, j)[1];
            unsigned short val_cv = map2.at<unsigned short>(i, j);
            char fx_cv = (val_cv & 31) / 32.0;
            char fy_cv = ((val_cv >> 5) & 31) / 32.0;

            fx_cv = fx_cv >> 1;
            fy_cv = fy_cv >> 1;
            ix_cv = (ix_cv << 4) >> 4;
            iy_cv = (iy_cv << 4) >> 4;

            val = fy_cv << 28 | iy_cv << 16 |
                  fx_cv << 12 | ix_cv;
            out_file_float.write(reinterpret_cast<const char*>(&val), sizeof(val));

            //int_map
            val = (iy_cv << 16) | ix_cv;
            out_file_int.write(reinterpret_cast<const char*>(&val), sizeof(val));
        }
    }

    out_file_float.close();
    out_file_int.close();
    std::cout << "Undistortion maps (binary) saved to: " << float_table_name << std::endl;
    std::cout << "Undistortion maps (binary) saved to: " << int_table_name << std::endl;
}

int main(int argc, char** argv)
{
    if (argc < 5) {
        std::cerr << "./undistort_table [video_file] [camera_params.yml] [float_table_name] [int_table_name]" << std::endl;
        return -1;
    }

    std::string videoPath = argv[1];
    std::string cameraPath = argv[2];
    std::string gp_undistort_map_float_filename = argv[3];
    std::string gp_undistort_map_int_filename = argv[4];

    // Load camera parameters
    cv::Mat cameraMatrix, distCoeffs;
    cv::FileStorage fs(cameraPath, cv::FileStorage::READ);
    if (!fs.isOpened()) {
        std::cerr << "Failed to open camera parameter file: " << cameraPath << std::endl;
        return -1;
    }
    fs["cameraMatrix"] >> cameraMatrix;
    fs["dist_coeffs"] >> distCoeffs;
    fs.release();
    std::cout << "Camera Matrix:\n" << cameraMatrix << std::endl;
    std::cout << "Distortion Coefficients:\n" << distCoeffs << std::endl;

    // Open video file
    cv::VideoCapture cap(videoPath);
    if (!cap.isOpened()) {
        std::cerr << "Cannot open video file: " << videoPath << std::endl;
        return -1;
    }

    // Get frame size
    cv::Mat frame;
    cap >> frame;
    if (frame.empty()) {
        std::cerr << "Empty first frame!" << std::endl;
        return -1;
    }

    cv::Size frameSize = frame.size();

    // Precompute undistortion maps
    cv::Mat map1, map2;
    cv::Mat map1u, map2u;
    // map1u type: 16SC2
    // map2u type: 16UC1
    cv::initUndistortRectifyMap(cameraMatrix, distCoeffs, cv::Mat(),
        cameraMatrix, frameSize, CV_16SC2, map1u, map2u);

    cout<<"first 8 pixel in map1u: ";
    for (int i = 0; i < 8; i++) {

        double ix = map1u.at<cv::Vec2s>(0, i)[0];
        double iy = map1u.at<cv::Vec2s>(0, i)[1];

        ushort val = map2u.at<ushort>(0, i);

        // Unpack the 5-bit fractional parts
        // OpenCV formula: (fy << 5) | fx
        // Use 10 bits in total.
        double fx = (val & 31) / 32.0; // Lower 5 bits are for x
        double fy = ((val >> 5) & 31) / 32.0; // Next 5 bits are for y

        // Reconstruct the floating point coordinate
        double x = ix + fx;
        double y = iy + fy;
        std::cout << "(" << x << ", " << y << ")" << ",";
    }
    cout<<endl;
    cout<<"first 8 pixel in map1 double: ";
    cv::initUndistortRectifyMap(cameraMatrix, distCoeffs, cv::Mat(),
    cameraMatrix, frameSize, CV_32FC2, map1, map2);
    for (int i = 0; i < 8; i++) {
        cout<<"(" << map1.at<cv::Vec2f>(0, i)[0] << ", " 
            << map1.at<cv::Vec2f>(0, i)[1] << ")" << ",";
    }
    cout<<endl;

    write_gp_map(map1u, map2u, gp_undistort_map_float_filename, gp_undistort_map_int_filename);

    // Main loop
    while (true) {
        cap >> frame;
        if (frame.empty())
            break;

        cv::Mat undistorted;

        cv::remap(frame, undistorted, map1u, map2u, cv::INTER_LINEAR);

        cv::imshow("Original", frame);
        cv::imshow("Undistorted", undistorted);

        char key = cv::waitKey(0);
        if (key == 27)  // ESC key
            break;
    }

    cap.release();
    cv::destroyAllWindows();
    return 0;
}
