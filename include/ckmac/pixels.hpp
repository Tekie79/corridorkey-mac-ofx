#pragma once

#include <cstddef>
#include <vector>

namespace ckmac {
struct Rect { int x1, y1, x2, y2; };
struct ImageView {
    unsigned char* data = nullptr;
    Rect bounds{};
    std::ptrdiff_t rowBytes = 0;
};
enum class OutputMode { Keyed = 0, Matte = 1, Foreground = 2, Original = 3 };

// OFX's (x1,y1) is the lower-left pixel. A negative row stride is legal.
void validateImage(const ImageView& image);
std::vector<float> packStraight(const ImageView& image, bool premultiplied);
void writeOutput(const std::vector<float>& topDownStraight, const Rect& sourceBounds,
                 const ImageView& output, const Rect& renderWindow, OutputMode mode);
}  // namespace ckmac
