#pragma once
#include <array>
#include <vector>
namespace ckmac {
struct PostSettings {
    int inputSpace=0,screen=0,method=0;
    double despill=0,whitePoint=1;
    bool linearize=false,recoverDetails=false;
    std::array<double,3> picked{0,1,0};
};
std::array<double,3> detectScreen(const std::vector<float>& source,const std::vector<float>& keyed,int inputSpace=0);
// Operates on straight foreground; association remains writeOutput's job.
void applyPost(std::vector<float>& keyed,const std::vector<float>& source,const PostSettings& settings);
}
