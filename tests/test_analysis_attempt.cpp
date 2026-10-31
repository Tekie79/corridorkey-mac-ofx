#include "ckmac/analysis_attempt.hpp"
#include "ckmac/capture_guard.hpp"
#include <atomic>
#include <thread>
void check(bool ok){if(!ok)throw std::runtime_error("Analysis attempt regression");}
int main(){
    ckmac::AnalysisAttempt attempt;auto now=ckmac::AnalysisAttempt::Clock::now();
    check(!attempt.begin(1,now));attempt.arm(1,now);check(attempt.pending(now));
    {auto render=attempt.begin(1,now);check(bool(render));check(!attempt.pending(now));}
    check(!attempt.begin(1,now)); // Success/error/abort all finish via scope.
    attempt.arm(1,now);check(!attempt.pending(now+std::chrono::seconds(31)));
    check(!attempt.begin(1,now+std::chrono::seconds(31))); // Host never rendered.
    attempt.arm(1,now);attempt.cancel();check(!attempt.begin(1,now));
    attempt.arm(1,now);check(!attempt.begin(2,now)); // Stale host generation.
    attempt.arm(1,now);std::atomic<int> started{0};
    auto begin=[&]{auto render=attempt.begin(1,now);if(render)++started;};
    std::thread a(begin),b(begin);a.join();b.join();check(started==1);
    // Exact two independent host renders: one click, complete causal set,
    // confirmation, analysis. The preceding baked generation is never changed.
    ckmac::CaptureGuard capture;
    std::vector<std::string> keys;for(int i=0;i<60;i++)keys.push_back("frame"+std::to_string(i));
    check(!capture.observe("old",keys));check(capture.observe("old",keys));
    keys[27]="edited frame";attempt.arm(3,now);
    {auto render=attempt.begin(3,now);check(bool(render));render.verifySource("new");
     check(!capture.observe("new",keys));render.awaitConfirmation("new",now);}
    check(attempt.pending(now));
    {auto render=attempt.begin(3,now);check(bool(render));render.verifySource("new");
     check(capture.observe("new",keys));render.analyzing();}
    check(!attempt.pending(now));check(!attempt.begin(3,now));
    // A changed source/settings generation on confirmation is a real failure.
    attempt.arm(4,now);
    {auto render=attempt.begin(4,now);render.awaitConfirmation("new",now);}
    bool rejected=false;
    try{auto render=attempt.begin(4,now);render.verifySource("changed again");}
    catch(const std::runtime_error&){rejected=true;}
    check(rejected&&!attempt.pending(now)&&!attempt.begin(4,now));
    // No blind third pass, permanent pending state, or canceled intent on reopen.
    attempt.arm(5,now);
    {auto render=attempt.begin(5,now);render.awaitConfirmation("new",now);}
    try{auto render=attempt.begin(5,now);render.awaitConfirmation("new",now);check(false);}
    catch(const std::runtime_error&){}
    check(!attempt.pending(now));
    attempt.arm(6,now);
    {auto render=attempt.begin(6,now);render.awaitConfirmation("new",now);}
    check(!attempt.begin(6,now+std::chrono::seconds(31)));
    attempt.arm(7,now);
    {auto old=attempt.begin(7,now);attempt.arm(8,now);}
    check(attempt.pending(now)); // An older destructor cannot clear a new click.
    {auto render=attempt.begin(8,now);attempt.cancel();}
    check(!attempt.pending(now));
    ckmac::AnalysisAttempt reopened;check(!reopened.begin(8,now));
}
