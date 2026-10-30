#pragma once
#include <atomic>
#include <chrono>
#include <cstdint>

namespace ckmac {
// A button arms one Render, not a persistent mode. Taking it before any host
// call/lock means every return, abort and exception restores baked navigation.
// A request the host never renders expires without background host-suite calls.
class AnalysisAttempt {
public:
    using Clock=std::chrono::steady_clock;
    void arm(Clock::time_point now=Clock::now()) {
        until_.store(ticks(now+std::chrono::seconds(30)));
    }
    bool pending(Clock::time_point now=Clock::now()) const {
        return until_.load()>ticks(now);
    }
    bool take(Clock::time_point now=Clock::now()) {
        return until_.exchange(0)>ticks(now);
    }
    void cancel(){until_.store(0);}
private:
    static std::int64_t ticks(Clock::time_point now) {
        return std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count();
    }
    std::atomic<std::int64_t> until_{0};
};
}
