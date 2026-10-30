#include "ckmac/analysis_attempt.hpp"
#include <cassert>
#include <thread>
int main(){
    ckmac::AnalysisAttempt attempt;auto now=ckmac::AnalysisAttempt::Clock::now();
    assert(!attempt.take(now));attempt.arm(now);assert(attempt.pending(now));
    assert(attempt.take(now));assert(!attempt.pending(now));assert(!attempt.take(now));
    attempt.arm(now);assert(!attempt.pending(now+std::chrono::seconds(31)));
    assert(!attempt.take(now+std::chrono::seconds(31))); // Host never rendered.
    attempt.arm(now);attempt.cancel();assert(!attempt.take(now));
    attempt.arm(now);int first=0,second=0;
    std::thread a([&]{first=attempt.take(now);});std::thread b([&]{second=attempt.take(now);});
    a.join();b.join();assert(first+second==1);
    // A failed/in-flight attempt has no persistent flag to strand a bake.
    attempt.arm(now);assert(attempt.take(now));attempt.arm(now);assert(attempt.take(now));
}
