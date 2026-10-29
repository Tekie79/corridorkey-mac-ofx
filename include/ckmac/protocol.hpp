#pragma once

#include <cstdint>
#include <functional>
#include <stdexcept>
#include <string>
#include <vector>

namespace ckmac {
constexpr std::uint32_t protocolVersion = 1;
constexpr std::uint32_t maxDimension = 8192;
constexpr std::uint64_t maxPixels = 33554432;
constexpr std::size_t requestHeaderBytes = 40;
constexpr std::size_t responseHeaderBytes = 32;

struct Cancelled : std::runtime_error { Cancelled() : std::runtime_error("Render cancelled") {} };
struct Settings {
    std::uint32_t inputSpace = 0;  // sRGB=0, scene-linear Rec.709=1, Rec.709 Gamma 2.4=2.
    bool sourceAlphaHint = false;
    double hintQuality = 0.95;
    double despillStrength = 0.0;
    // Installed protocol v2; the development v1 wire format remains unchanged.
    int internalResolution = 0, temporalWindow = 4, memoryLimit = 0;
    bool lowMemory = false;
    double internalHintQuality = 0.95;
    int referenceIndex = 0;
};

std::string defaultSocketPath();
std::uint32_t checkedPayloadSize(std::uint32_t width, std::uint32_t height);

// The wire protocol is local-only. Header integers are big endian; pixel samples
// are explicitly little-endian IEEE-754 float32, top row first, straight RGBA.
class Client {
public:
    explicit Client(std::string socketPath,
                    std::function<bool()> cancelled = {},
                    double timeoutSeconds = 600.0);
    std::vector<float> infer(std::uint32_t width, std::uint32_t height,
                             const std::vector<float>& straightRgba,
                             const Settings& settings) const;
    std::string health() const;
private:
    std::vector<unsigned char> transact(std::uint32_t operation,
                                        std::uint32_t width, std::uint32_t height,
                                        const std::vector<float>& pixels,
                                        const Settings& settings) const;
    std::string path_;
    std::function<bool()> cancelled_;
    double timeout_;
};
}  // namespace ckmac
