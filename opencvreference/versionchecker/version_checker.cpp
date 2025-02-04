#include <opencv2/core.hpp>
#include <iostream>

int main() {
    std::cout << "CV_VERSION (macro): " << CV_VERSION << std::endl;
    std::cout << "OpenCV version: " << cv::getVersionString() << std::endl;
    return 0;
}
