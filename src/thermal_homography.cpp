#include <iostream>
#include <fstream>
#include <unistd.h>
#include <opencv2/opencv.hpp>
using namespace std;
#define HEIGHT 40
#define WIDTH  60
#define SCALE_FOR_DISPLAY 8
#define NORMALIZE_LIMIT 255
#define TEMPATURE_THRESHOLD 350
#define CLICKING_FRAME_TH "clicking_frame_th"
#define CLICKING_FRAME_VIDEO "clicking_frame_video"
vector<cv::Point> points_th;
vector<cv::Point> points_video;
int n_pts = 0;
cv::Mat frame_th_bgr(HEIGHT, WIDTH, CV_8UC3);
cv::Mat frame_video;
cv::Mat large_display_frame;

bool get_frame(std::ifstream& file, cv::Mat &frame) {
    for (int i = 0; i < HEIGHT; ++i) {
        for (int j = 0; j < WIDTH; ++j) {
            if (!(file >> frame.at<float>(i,j))) {
                cout << "End of file" << std::endl;
                return false;
            }
        }
    }
    return true; // Frame read successfully
}
void onMouse(int event, int x, int y, int flags, void* userdata) {
    if (event == cv::EVENT_LBUTTONDOWN) {
        std::cout << "Left mouse button clicked at (" << x/SCALE_FOR_DISPLAY << ", " << y/SCALE_FOR_DISPLAY << ")" << std::endl;

        cv::circle(large_display_frame, cv::Point(x, y), 10, cv::Scalar(0, 255, 0), -1); // Draw filled green circle
        cv::imshow(CLICKING_FRAME_TH, large_display_frame);

        points_th.push_back(cv::Point(x/SCALE_FOR_DISPLAY, y/SCALE_FOR_DISPLAY));
        if (points_th.size() >= n_pts) {
            std::cout << "Reached the limit of " << n_pts << " points." << std::endl;
        } else {
            std::cout << "Current number of points: " << points_th.size() << std::endl;
        }
    }
}
void onMouseVideo(int event, int x, int y, int flags, void* userdata) {
    if (event == cv::EVENT_LBUTTONDOWN) {
        std::cout << "Left mouse button clicked at (" << x << ", " << y << ")" << std::endl;

        cv::circle(frame_video, cv::Point(x, y), 10, cv::Scalar(0, 255, 0), -1); // Draw filled green circle
        cv::imshow(CLICKING_FRAME_VIDEO, frame_video);

        points_video.push_back(cv::Point(x, y));
        if (points_video.size() >= n_pts) {
            std::cout << "Reached the limit of " << n_pts << " points." << std::endl;
        } else {
            std::cout << "Current number of points: " << points_th.size() << std::endl;
        }
    }
}
void print_frame(const cv::Mat &frame) {
    for (int i = 0; i < frame.rows; ++i) {
        for (int j = 0; j < frame.cols; ++j) {
            int type = frame.type();
            if (type == CV_32F) {
                std::cout << frame.at<float>(i, j) << " ";
            } else if (type == CV_8U) {
                std::cout << static_cast<int>(frame.at<uchar>(i, j)) << " ";
            } else if (type == CV_16U) {
                std::cout << frame.at<uint16_t>(i, j) << " ";
            } else if (type == CV_64F) {
                std::cout << frame.at<double>(i, j) << " ";
            } else {
                std::cout << "? ";
            }
        }
        std::cout << std::endl;
    }
}
int main(int argc, char **argv) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <input_file>" << std::endl;
        return 1;
    }
    std::ifstream file(argv[1]);
    if (!file.is_open()) {
        std::cerr << "Error opening file." << std::endl;
        return 1;
    }

    cv::Mat frame(HEIGHT, WIDTH, CV_32F);
    cv::Mat small_display_frame(HEIGHT, WIDTH, CV_8U);
    large_display_frame = cv::Mat(HEIGHT*SCALE_FOR_DISPLAY, WIDTH*SCALE_FOR_DISPLAY, CV_8U);
    
    int count = 0;
    double minVal, maxVal;
    double runtime_threshold = 0.0;
    
	cout<<"input the number you want to select:"<<endl;
	cin>>n_pts;

    cv::namedWindow(CLICKING_FRAME_TH);
    cv::setMouseCallback(CLICKING_FRAME_TH, onMouse, nullptr);
    // Read and process frames until EOF or error
    while (get_frame(file, frame)) {
        count++;
        if (count < 10)
            continue;
        cv::GaussianBlur(frame, frame, cv::Size(3, 3), 0);
        cv::normalize(frame, small_display_frame, 
                        0, 255, cv::NORM_MINMAX, CV_8U);

        cv::resize(small_display_frame, 
                        large_display_frame, 
                        large_display_frame.size(),
                        0, 0, cv::INTER_LINEAR);

        cv::applyColorMap(large_display_frame, frame_th_bgr, 
                            cv::COLORMAP_JET);

        // Display
        cv::imshow("Thermal Frame", large_display_frame);
        //cv::imshow("Thermal Frame Color", frame_th_bgr);
        int key = cv::waitKey(0); // or cv::waitKey(delay)
        if (key == 32) {
            // Space key was pressed
            cv::imshow(CLICKING_FRAME_TH, large_display_frame);
        }
        else if (key == 27) { // ESC key
            std::cout << "Exiting..." << std::endl;
            break; // Exit the loop on ESC key
        }
    }

    file.close();
    if (argc < 3) {
        return 0;
    }
    cv::VideoCapture cap(argv[2]);
    if (!cap.isOpened()) {
        std::cerr << "Error opening video file." << std::endl;
        return 1;
    }

    cv::namedWindow(CLICKING_FRAME_VIDEO);
    cv::setMouseCallback(CLICKING_FRAME_VIDEO, onMouseVideo, nullptr);
    while (true) {
        cap >> frame_video;
        if (frame_video.empty()) {
            std::cout << "End of video file." << std::endl;
            break; // Exit the loop if no more frames
        }
        cv::imshow("Video Frame", frame_video);
        int key = cv::waitKey(0);
        if (key == 32) {
            // Space key was pressed
            cv::imshow(CLICKING_FRAME_VIDEO, frame_video);
        }
        else if (key == 27) { // ESC key
            std::cout << "Exiting video playback..." << std::endl;
            break; // Exit the loop on ESC key
        }
    }

    
    cout<< "mapping:" << endl;
    for (auto &point : points_th) {
        cout<< "Thermal Point: (" << point.x << ", " << point.y << ")" << endl;
    }
    cout<< "to" << endl;
    for (auto &point : points_video) {
        cout<< "Video Point: (" << point.x << ", " << point.y << ")" << endl;
    }
    cout<<endl;

    cv::Mat homography;    
    homography = findHomography(points_th, points_video,0);
    cout<< "Homography Matrix: " << endl;
    cout << homography << endl;

    cout<<"Verfiying..." << endl;
    double h[3][3];
    for (int i = 0; i < 3; ++i)
        for (int j = 0; j < 3; ++j)
            h[i][j] = homography.at<double>(i, j);

    for (auto &point : points_th) {
        double x_src = point.x;
        double y_src = point.y;
        double x = h[0][0]*x_src + h[0][1]*y_src + h[0][2];
        double y = h[1][0]*x_src + h[1][1]*y_src + h[1][2];
        double w = h[2][0]*x_src + h[2][1]*y_src + h[2][2];
        x /= w;
        y /= w;
        cout << "dst_point: (" << x << ", " << y << ")" << endl;
        cv::circle(frame_video, cv::Point(cvRound(x), cvRound(y)), 8, cv::Scalar(255, 0, 255), -1);
    }

    imshow("Video Frame with Mapped Points", frame_video);
    cv::waitKey(0);


    return 0;
}