#include "ckmac/pixels.hpp"
#include "ckmac/protocol.hpp"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <stdexcept>

namespace ckmac {
namespace {
std::size_t widthOf(const Rect& bounds) { return static_cast<std::size_t>(std::int64_t(bounds.x2) - bounds.x1); }
std::size_t heightOf(const Rect& bounds) { return static_cast<std::size_t>(std::int64_t(bounds.y2) - bounds.y1); }
unsigned char* address(const ImageView& image, int x, int y) {
    return image.data + static_cast<std::ptrdiff_t>(std::int64_t(y) - image.bounds.y1) * image.rowBytes
           + static_cast<std::ptrdiff_t>(std::int64_t(x) - image.bounds.x1) * 4 * sizeof(float);
}
}  // namespace

void validateImage(const ImageView& image) {
    const auto width = std::int64_t(image.bounds.x2) - image.bounds.x1;
    const auto height = std::int64_t(image.bounds.y2) - image.bounds.y1;
    if (width <= 0 || height <= 0 || width > maxDimension || height > maxDimension)
        throw std::runtime_error("Invalid OFX image bounds.");
    checkedPayloadSize(static_cast<std::uint32_t>(width), static_cast<std::uint32_t>(height));
    if (!image.data || image.rowBytes == std::numeric_limits<std::ptrdiff_t>::min()
        || std::abs(image.rowBytes) < width * 16)
        throw std::runtime_error("Invalid OFX image data or row stride.");
    if (std::uint64_t(std::abs(image.rowBytes)) * std::uint64_t(height)
        > std::uint64_t(std::numeric_limits<std::ptrdiff_t>::max()))
        throw std::runtime_error("OFX image stride exceeds the addressable range.");
}

std::vector<float> packStraight(const ImageView& image, bool premultiplied) {
    validateImage(image);
    const auto width = widthOf(image.bounds), height = heightOf(image.bounds);
    std::vector<float> packed(width * height * 4);
    for (std::size_t row = 0; row < height; ++row) {
        const int y = static_cast<int>(std::int64_t(image.bounds.y2) - 1 - static_cast<std::int64_t>(row));
        for (std::size_t col = 0; col < width; ++col) {
            float pixel[4];
            std::memcpy(pixel, address(image, static_cast<int>(std::int64_t(image.bounds.x1) + static_cast<std::int64_t>(col)), y), sizeof(pixel));
            for (float value : pixel)
                if (!std::isfinite(value)) throw std::runtime_error("Source has non-finite pixels. Sanitize the image before keying.");
            pixel[3] = std::clamp(pixel[3], 0.0F, 1.0F);
            if (premultiplied) {
                for (int channel = 0; channel < 3; ++channel)
                    pixel[channel] = pixel[3] > 1e-6F ? pixel[channel] / pixel[3] : 0.0F;
            }
            std::memcpy(packed.data() + (row * width + col) * 4, pixel, sizeof(pixel));
        }
    }
    return packed;
}

void writeOutput(const std::vector<float>& packed, const Rect& sourceBounds,
                 const ImageView& output, const Rect& window, OutputMode mode) {
    validateImage(output);
    const auto width = widthOf(sourceBounds), height = heightOf(sourceBounds);
    if (sourceBounds.x2 <= sourceBounds.x1 || sourceBounds.y2 <= sourceBounds.y1
        || width > maxDimension || height > maxDimension || packed.size() != width * height * 4)
        throw std::runtime_error("Invalid result dimensions.");
    if (mode < OutputMode::Keyed || mode > OutputMode::Original)
        throw std::runtime_error("Invalid output mode.");
    const Rect clipped{std::max(window.x1, output.bounds.x1), std::max(window.y1, output.bounds.y1),
                       std::min(window.x2, output.bounds.x2), std::min(window.y2, output.bounds.y2)};
    for (int y = clipped.y1; y < clipped.y2; ++y) {
        for (int x = clipped.x1; x < clipped.x2; ++x) {
            float pixel[4]{};
            if (x >= sourceBounds.x1 && x < sourceBounds.x2 && y >= sourceBounds.y1 && y < sourceBounds.y2) {
                const auto row = static_cast<std::size_t>(std::int64_t(sourceBounds.y2) - 1 - y);
                const auto col = static_cast<std::size_t>(std::int64_t(x) - sourceBounds.x1);
                std::memcpy(pixel, packed.data() + (row * width + col) * 4, sizeof(pixel));
                const float alpha = std::clamp(pixel[3], 0.0F, 1.0F);
                switch (mode) {
                case OutputMode::Keyed:
                    for (int channel = 0; channel < 3; ++channel) pixel[channel] *= alpha;
                    pixel[3] = alpha;
                    break;
                case OutputMode::Matte: pixel[0] = pixel[1] = pixel[2] = alpha; pixel[3] = 1; break;
                case OutputMode::Foreground:
                case OutputMode::Original: pixel[3] = 1; break;
                }
            }
            std::memcpy(address(output, x, y), pixel, sizeof(pixel));
        }
    }
}
}  // namespace ckmac
