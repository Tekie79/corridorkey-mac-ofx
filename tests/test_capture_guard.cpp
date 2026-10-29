#include "ckmac/capture_guard.hpp"
#include <stdexcept>
#include <iostream>
void check(bool value) { if (!value) throw std::runtime_error("Unsafe temporal capture accepted"); }
int main() {
    ckmac::CaptureGuard a,b;
    // The acquisition straddles an edit. A same-action reread could still
    // return these cached identities; there must be no submission yet.
    check(!a.observe("shot 0..2", {"old0","old1","new2"}));
    // A subsequent host action exposes the complete new source generation.
    check(!a.observe("shot 0..2", {"new0","new1","new2"}));
    check(a.observe("shot 0..2", {"new0","new1","new2"}));
    check(!a.observe("shot 1..3", {"new0","new1","new2"}));
    check(!b.observe("shot 1..3", {"new0","new1","new2"}));
    a.reset();
    check(!a.observe("shot 1..3", {"new0","new1","new2"}));
    std::cout << "Temporal submission waits for independent stable capture; range and instance isolation passed\n";
}
