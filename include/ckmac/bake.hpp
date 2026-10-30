#pragma once
#include "ckmac/pixels.hpp"
#include "ckmac/creative.hpp"
#include <string>
#include <vector>
namespace ckmac {
struct BakeInfo {
    std::string path,generation,kind,encoding;
    Rect bounds;
    PostSettings post;
    int start=0,end=0;
    double fps=0,pixelAspect=1;
};
BakeInfo inspectBake(const std::string& manifest,bool verifyAll=false);
std::vector<float> readBake(const BakeInfo& info,int frame);
std::vector<float> fitBake(std::vector<float> rgba,int width,int height,int targetWidth,int targetHeight,const std::string& encoding,bool alphaOnly=false);
std::string chooseBakeFolder();
std::string chooseBakeManifest();
}
