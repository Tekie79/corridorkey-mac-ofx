#include "ckmac/protocol.hpp"

#include <cmath>
#include <iostream>
#include <stdexcept>
#include <vector>

// Integration-only client for the REAL Python LocalServer with a deterministic
// fake model: output RGB = input RGB * 2, alpha = 0.25. Never used by the plugin.
int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("Usage: bridge_probe /absolute/worker.sock");
        const std::vector<float> input{
            0.1F, 0.2F, 0.3F, 1.0F,
            0.4F, 0.5F, 0.6F, 0.8F,
            0.7F, 0.2F, 0.9F, 0.5F,
            0.01F, 0.02F, 0.03F, 0.25F
        };
        const ckmac::Settings settings{2, true, 0.75, 0.125};
        ckmac::Client client(argv[1], {}, 5.0);
        const auto health = client.health();
        const auto output = client.infer(2, 2, input, settings);
        if (output.size() != input.size()) throw std::runtime_error("Wrong output dimensions");
        for (std::size_t i = 0; i < output.size(); ++i) {
            const float expected = i % 4 == 3 ? 0.25F : input[i] * 2.0F;
            if (std::abs(output[i] - expected) > 1e-6F)
                throw std::runtime_error("Cross-language output sample differs from the fake backend contract");
        }
        std::cout << "{\"health\":" << health << ",\"rgba\":[";
        for (std::size_t i = 0; i < output.size(); ++i) {
            if (i) std::cout << ',';
            std::cout << output[i];
        }
        std::cout << "]}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
