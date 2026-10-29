#pragma once
#include <string>
#include <vector>

namespace ckmac {
// A host may cache an early source frame for the lifetime of a Render action
// while serving a later frame after an upstream edit. Re-reading within that
// action is not an independent observation. Never submit a newly observed
// causal set until another Render action has observed the identical set.
// This stores identities only; no host image handles or pixel buffers survive.
class CaptureGuard {
    std::string context_;
    std::vector<std::string> keys_;
public:
    bool observe(const std::string& context, const std::vector<std::string>& keys) {
        if (context == context_ && keys == keys_ && !keys.empty()) return true;
        context_ = context;
        keys_ = keys;
        return false;
    }
    void reset() { context_.clear(); keys_.clear(); }
};
}
