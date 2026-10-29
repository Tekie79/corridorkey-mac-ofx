#include "ckmac/pixels.hpp"
#include <cmath>
#include <cstring>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <vector>

namespace {
void check(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
bool close(float a, float b) { return std::abs(a - b) < 1e-6F; }
template<class F> void rejects(F function) {
    bool caught = false;
    try { function(); } catch (const std::runtime_error&) { caught = true; }
    check(caught, "Expected invalid image to be rejected");
}
}
int main() {
    try {
        // A padded image with a negative stride and a nonzero, negative origin.
        // Memory order is top row then bottom row, unlike logical OFX Y order.
        std::vector<float> memory(20, -77.0F);
        const float top[]{0.2F, 0.1F, 0.0F, 0.5F, 0.8F, 0.6F, 0.4F, 1.0F};
        const float bottom[]{0.1F, 0.2F, 0.3F, 0.5F, 0.2F, 0.4F, 0.6F, 1.0F};
        std::memcpy(memory.data(), top, sizeof(top));
        std::memcpy(memory.data() + 10, bottom, sizeof(bottom));
        ckmac::ImageView source{reinterpret_cast<unsigned char*>(memory.data() + 10), {-3, 7, -1, 9}, -40};
        auto packed = ckmac::packStraight(source, true);
        check(close(packed[0], 0.4F) && close(packed[1], 0.2F) && close(packed[3], 0.5F), "Top-left unpack/unpremultiply failed");
        check(close(packed[8], 0.2F) && close(packed[9], 0.4F), "Bottom row was flipped incorrectly");
        check(memory[8] == -77.0F && memory[18] == -77.0F, "Input padding was modified");

        std::vector<float> out(20, -91.0F);
        ckmac::ImageView target{reinterpret_cast<unsigned char*>(out.data()), {-3, 7, -1, 9}, 40};
        ckmac::writeOutput(packed, source.bounds, target, {-3, 8, -2, 9}, ckmac::OutputMode::Keyed);
        check(close(out[10], 0.2F) && close(out[11], 0.1F) && close(out[13], 0.5F), "Premultiplied output mismatch");
        check(out[0] == -91.0F && out[14] == -91.0F && out[18] == -91.0F, "Render wrote outside render window or into padding");
        ckmac::writeOutput(packed, source.bounds, target, source.bounds, ckmac::OutputMode::Matte);
        check(out[0] == 0.5F && out[1] == 0.5F && out[3] == 1.0F, "Matte must be opaque preview");
        ckmac::writeOutput(packed, source.bounds, target, source.bounds, ckmac::OutputMode::Foreground);
        check(close(out[10], 0.4F) && out[13] == 1.0F, "Straight foreground preview mismatch");
        auto bad = source;
        bad.rowBytes = 20;
        rejects([&] { ckmac::packStraight(bad, false); });
        memory[0] = std::numeric_limits<float>::quiet_NaN();
        rejects([&] { ckmac::packStraight(source, false); });
        memory[0] = 1.0F;
        memory[3] = 0.0F;
        packed = ckmac::packStraight(source, true);
        check(packed[0] == 0 && packed[1] == 0 && packed[2] == 0, "Zero alpha unpremultiply must not divide by zero");
        std::cout << "pixels: negative stride, origins, flip, alpha, padding, window and invalid input passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
