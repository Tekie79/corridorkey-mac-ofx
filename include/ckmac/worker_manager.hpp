#pragma once
#include "ckmac/protocol.hpp"
#include "ckmac/creative.hpp"
#include <string>
#include <vector>

namespace ckmac {
void openManager();
void openMaintenance(const std::string& action);
std::string cacheDirectory();
void chooseCacheDirectory();
void revealCacheDirectory();
// No work is performed until ensure()/request(). Safe to construct in a scan.
struct BakeOptions {
    int sizeMode=0,width=3840,height=2160,sourceWidth=0,sourceHeight=0;
    bool fullFloat=false,sourceSizeExplicit=false,resolveHost=false;
    std::string sourceManifest;
};
struct CleanupReport {bool complete=false;std::string message;};
class WorkerManager {
public:
    explicit WorkerManager(std::function<bool()> cancelled = {},std::uint64_t generation=0,const std::string& owner="");
    std::string ensure();
    std::string status();
    std::vector<float> infer(unsigned width, unsigned height,
                             const std::vector<float>& pixels, const Settings& settings);
    bool framePresent(unsigned width,unsigned height,const std::string& key,const Settings& settings);
    std::vector<float> inferCaptured(unsigned width,unsigned height,const std::string& key,const Settings& settings);
    // JSON control transport is bounded and authenticated, independent of v1.
    std::string control(const std::string& json);
    CleanupReport clearAnalysis(const std::string& generation="");
    static std::string fingerprint(unsigned width,unsigned height,const std::vector<float>& pixels);
    std::string bake(const std::string& generation,const std::string& destination,const std::string& kind,const PostSettings& post,const BakeOptions& options={});
    bool bakeOwnsAnalysis=false;
    std::string lastGeneration;
    bool cacheHit=false;
    std::vector<std::string> analysisStatus(unsigned width,unsigned height,const std::vector<std::string>& keys,unsigned requested,const Settings& settings,int revision,bool firstHint,const std::string& provenance);
    std::string stage(unsigned width,unsigned height,const std::vector<float>& pixels,bool reuse=true);
    std::vector<std::string> inputsPresent(const std::vector<std::string>& keys);
    std::vector<float> temporal(unsigned width,unsigned height,const std::vector<std::string>& keys,
        unsigned requested,const Settings& settings,int revision,bool firstHint,const std::string& provenance="{}",bool resume=false);
private:
    std::function<bool()> cancelled_;
    std::string endpoint_, token_, build_;
    std::string session_;
    std::uint64_t generation_=0,request_=0;
    std::vector<unsigned char> exchange(const std::string& json,
                                        const void* data, std::size_t bytes,
                                        std::string* metadata = nullptr);
    void waitReady();
};
}
