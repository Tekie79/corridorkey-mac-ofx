#include "ckmac/pixels.hpp"
#include "ckmac/protocol.hpp"
#include "ckmac/creative.hpp"
#include "ckmac/capture_guard.hpp"
#include "ofxCore.h"
#include "ofxProgress.h"
#include <fcntl.h>
#include <unistd.h>
#include <sstream>
#include <atomic>
#include <cmath>
#ifdef CKMAC_INSTALLED_RUNTIME
#include "ckmac/worker_manager.hpp"
#endif

#include "ofxCore.h"
#include "ofxImageEffect.h"
#include "ofxMessage.h"
#include "ofxParam.h"
#include "ofxProperty.h"

#include <cstring>
#include <exception>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>
#include <map>
#include <chrono>
#include <random>
#include <set>

namespace {
OfxHost* host = nullptr;
const OfxPropertySuiteV1* props = nullptr;
const OfxImageEffectSuiteV1* effects = nullptr;
const OfxParameterSuiteV1* params = nullptr;
const OfxMessageSuiteV2* messages = nullptr;
const OfxMessageSuiteV1* messagesV1 = nullptr;
const OfxProgressSuiteV1* progress = nullptr;

struct Instance {
    OfxImageClipHandle source = nullptr, output = nullptr;
    OfxImageClipHandle hintClip=nullptr;
    OfxParamHandle socket = nullptr, inputSpace = nullptr, alphaHint = nullptr;
    OfxParamHandle hintQuality = nullptr, despill = nullptr, outputMode = nullptr;
    OfxParamHandle acquisitionProbe = nullptr;
    OfxParamHandle processing=nullptr,rangeStart=nullptr,rangeEnd=nullptr,revision=nullptr,hintTiming=nullptr;
    OfxParamHandle hintSource=nullptr;
    std::atomic<std::uint64_t> generation{0};
    std::timed_mutex renderMutex;
    std::map<std::string,OfxParamHandle> creative;
    std::mutex sampleMutex;
    std::array<double,3> detectedScreen{0,1,0};
    bool hasScreenSample=false;
    std::string owner;
    struct Capture {std::string signature,key;};
    std::map<std::int64_t,Capture> captures;
    std::map<double,Capture> frameCaptures;
    int capturedRevision=-1;
    ckmac::CaptureGuard captureGuard;
};
void require(OfxStatus status,const char* operation);
int integer(Instance* i,const char* name,double time){int v=0;require(params->paramGetValueAtTime(i->creative.at(name),time,&v),name);return v;}
double number(Instance* i,const char* name,double time){double v=0;require(params->paramGetValueAtTime(i->creative.at(name),time,&v),name);return v;}

void require(OfxStatus status, const char* operation) {
    if (status != kOfxStatOK) throw std::runtime_error(std::string("OFX host failed: ") + operation);
}
OfxPropertySetHandle effectProperties(OfxImageEffectHandle effect) {
    OfxPropertySetHandle value = nullptr;
    require(effects->getPropertySet(effect, &value), "get effect properties");
    return value;
}
Instance* instanceOf(OfxImageEffectHandle effect) {
    void* pointer = nullptr;
    require(props->propGetPointer(effectProperties(effect), kOfxPropInstanceData, 0, &pointer), "get instance data");
    if (!pointer) throw std::runtime_error("OFX instance is not initialized.");
    return static_cast<Instance*>(pointer);
}
void report(OfxImageEffectHandle effect, const char* type, const std::string& text) {
    if (messages && messages->setPersistentMessage)
        messages->setPersistentMessage(effect, type, "corridorkey.mac", "%s", text.c_str());
    else if (messagesV1 && messagesV1->message)
        messagesV1->message(effect, type, "corridorkey.mac", "%s", text.c_str());
}
void clearMessage(OfxImageEffectHandle effect) {
    if (messages && messages->clearPersistentMessage) messages->clearPersistentMessage(effect);
}

OfxStatus load() {
    if (!host || !host->fetchSuite) return kOfxStatErrMissingHostFeature;
    props = static_cast<const OfxPropertySuiteV1*>(host->fetchSuite(host->host, kOfxPropertySuite, 1));
    effects = static_cast<const OfxImageEffectSuiteV1*>(host->fetchSuite(host->host, kOfxImageEffectSuite, 1));
    params = static_cast<const OfxParameterSuiteV1*>(host->fetchSuite(host->host, kOfxParameterSuite, 1));
    messages = static_cast<const OfxMessageSuiteV2*>(host->fetchSuite(host->host, kOfxMessageSuite, 2));
    messagesV1 = static_cast<const OfxMessageSuiteV1*>(host->fetchSuite(host->host, kOfxMessageSuite, 1));
    progress = static_cast<const OfxProgressSuiteV1*>(host->fetchSuite(host->host, kOfxProgressSuite, 1));
    return props && effects && params ? kOfxStatOK : kOfxStatErrMissingHostFeature;
}

OfxStatus describe(OfxImageEffectHandle effect) {
    auto p = effectProperties(effect);
    props->propSetString(p, kOfxPropLabel, 0, "CorridorKey2.0 hp beta");
    props->propSetString(p, kOfxImageEffectPluginPropGrouping, 0, "Keying");
    props->propSetString(p, kOfxPropPluginDescription, 0,
        "Personal beta. CorridorKey 2.0 on Apple Silicon. GPU engine starts automatically. "
        "Select the actual input encoding. This beta is not yet qualified for production.");
    props->propSetString(p, kOfxImageEffectPropSupportedContexts, 0, kOfxImageEffectContextFilter);
    props->propSetString(p, kOfxImageEffectPropSupportedContexts, 1, kOfxImageEffectContextGeneral);
    props->propSetString(p, kOfxImageEffectPropSupportedPixelDepths, 0, kOfxBitDepthFloat);
    props->propSetInt(p, kOfxImageEffectPluginPropSingleInstance, 0, 0);
    props->propSetInt(p, kOfxImageEffectPluginPropHostFrameThreading, 0, 0);
    props->propSetString(p, kOfxImageEffectPluginRenderThreadSafety, 0, kOfxImageEffectRenderInstanceSafe);
    props->propSetInt(p, kOfxImageEffectPropSupportsTiles, 0, 0);
    props->propSetInt(p, kOfxImageEffectPropSupportsMultiResolution, 0, 0);
    props->propSetInt(p, kOfxImageEffectPropTemporalClipAccess, 0, 1);
    props->propSetInt(p, kOfxImageEffectPropSupportsMultipleClipDepths, 0, 0);
    props->propSetInt(p, kOfxImageEffectPropSupportsMultipleClipPARs, 0, 0);
    // Host images MUST be CPU pointers. MPS GPU computation is isolated in the
    // worker; advertising host Metal support would make these pointers unsafe.
    props->propSetString(p, "OfxImageEffectPropMetalRenderSupported", 0, "false");
    props->propSetString(p, "OfxImageEffectPropCudaRenderSupported", 0, "false");
    props->propSetString(p, "OfxImageEffectPropOpenCLRenderSupported", 0, "false");
    return kOfxStatOK;
}

using DescriptorMap=std::map<std::string,OfxPropertySetHandle>;
thread_local DescriptorMap* definingParameters=nullptr;
struct DescriptorScope {
    DescriptorMap properties;
    DescriptorMap* previous=definingParameters;
    DescriptorScope(){definingParameters=&properties;}
    ~DescriptorScope(){definingParameters=previous;}
};
OfxPropertySetHandle defineParam(OfxParamSetHandle set, const char* type, const char* name,
                                 const char* label, const char* hint) {
    OfxPropertySetHandle p = nullptr;
    require(params->paramDefine(set, type, name, &p), "define parameter");
    if(definingParameters)(*definingParameters)[name]=p;
    props->propSetString(p, kOfxPropLabel, 0, label);
    props->propSetString(p, kOfxParamPropHint, 0, hint);
    props->propSetInt(p, kOfxParamPropAnimates, 0, 0);
    return p;
}
void defineDouble(OfxParamSetHandle set, const char* name, const char* label,
                   const char* hint, double defaultValue) {
    auto p = defineParam(set, kOfxParamTypeDouble, name, label, hint);
    props->propSetDouble(p, kOfxParamPropDefault, 0, defaultValue);
    props->propSetDouble(p, kOfxParamPropMin, 0, 0);
    props->propSetDouble(p, kOfxParamPropMax, 0, 1);
    props->propSetDouble(p, kOfxParamPropDisplayMin, 0, 0);
    props->propSetDouble(p, kOfxParamPropDisplayMax, 0, 1);
    props->propSetDouble(p, kOfxParamPropIncrement, 0, 0.01);
    props->propSetInt(p, kOfxParamPropDigits, 0, 3);
}
OfxStatus describeContext(OfxImageEffectHandle effect) {
    DescriptorScope descriptors;
    for (const char* name : {kOfxImageEffectSimpleSourceClipName, kOfxImageEffectOutputClipName}) {
        OfxPropertySetHandle p = nullptr;
        require(effects->clipDefine(effect, name, &p), "define clip");
        props->propSetString(p, kOfxImageEffectPropSupportedComponents, 0, kOfxImageComponentRGBA);
        props->propSetInt(p, kOfxImageEffectPropSupportsTiles, 0, 0);
        props->propSetInt(p, kOfxImageEffectPropTemporalClipAccess, 0, 1);
        props->propSetInt(p, kOfxImageClipPropOptional, 0, 0);
        props->propSetString(p, kOfxImageClipPropFieldExtraction, 0, kOfxImageFieldDoubled);
    }
    OfxPropertySetHandle hintProperties=nullptr;
    require(effects->clipDefine(effect,"Hint",&hintProperties),"define optional matte clip");
    props->propSetString(hintProperties,kOfxImageEffectPropSupportedComponents,0,kOfxImageComponentRGBA);
    props->propSetInt(hintProperties,kOfxImageClipPropOptional,0,1);
    props->propSetInt(hintProperties,kOfxImageEffectPropTemporalClipAccess,0,1);
    props->propSetInt(hintProperties,kOfxImageEffectPropSupportsTiles,0,0);
    props->propSetString(hintProperties,kOfxImageClipPropFieldExtraction,0,kOfxImageFieldDoubled);
    OfxParamSetHandle set = nullptr;
    require(effects->getParamSet(effect, &set), "get parameter set");
    auto p = defineParam(set, kOfxParamTypeChoice, "inputSpace", "Input Encoding",
        "Choose the actual RGB transfer curve arriving at this node. sRGB/Rec.709 primaries only. "
        "Convert S-Log3, DaVinci Wide Gamut, ACES and other encodings before this node.");
    props->propSetString(p, kOfxParamPropChoiceOption, 0, "sRGB");
    props->propSetString(p, kOfxParamPropChoiceOption, 1, "Scene-linear Rec.709");
    props->propSetString(p, kOfxParamPropChoiceOption, 2, "Rec.709 Gamma 2.4");
    props->propSetInt(p, kOfxParamPropDefault, 0, 0);
    p=defineParam(set,kOfxParamTypeChoice,"processingMode","Mode","Temporal uses ordered continuous context, overlapping windows and full-resolution refinement. Set the exact shot range before analysis.");
    props->propSetString(p,kOfxParamPropChoiceOption,0,"Single Frame");props->propSetString(p,kOfxParamPropChoiceOption,1,"Temporal");props->propSetInt(p,kOfxParamPropDefault,0,0);
    for(const char* name:{"analysisStart","analysisEnd"}) {
        p=defineParam(set,kOfxParamTypeInteger,name,!std::strcmp(name,"analysisStart")?"Shot Start":"Shot End","Inclusive integer node-input frames. Set one shot only. End -1 uses the available source range; maximum 240 frames.");
        props->propSetInt(p,kOfxParamPropDefault,0,!std::strcmp(name,"analysisStart")?0:-1);
    }
    p=defineParam(set,kOfxParamTypeInteger,"analysisRevision","Analysis Revision","Serialized render-affecting revision for explicit reanalysis.");
    props->propSetInt(p,kOfxParamPropDefault,0,0);props->propSetInt(p,kOfxParamPropSecret,0,1);
    p=defineParam(set,kOfxParamTypeChoice,"hintSource","Hint Source","An optional aligned RGBA Hint input may supply its Alpha or linear luminance. Legacy Source Alpha remains compatible with saved projects.");
    props->propSetString(p,kOfxParamPropChoiceOption,0,"None / Legacy");
    props->propSetString(p,kOfxParamPropChoiceOption,1,"Source Alpha");
    props->propSetString(p,kOfxParamPropChoiceOption,2,"Hint Alpha");
    props->propSetString(p,kOfxParamPropChoiceOption,3,"Hint Luma");
    props->propSetInt(p,kOfxParamPropDefault,0,0);
    p=defineParam(set,kOfxParamTypeChoice,"hintTiming","Hint Frames","Use every aligned hint frame, or propagate the chosen Reference Frame through the temporal shot.");
    props->propSetString(p,kOfxParamPropChoiceOption,0,"All Frames");props->propSetString(p,kOfxParamPropChoiceOption,1,"Reference Frame");props->propSetInt(p,kOfxParamPropDefault,0,0);
    defineParam(set,kOfxParamTypePushButton,"analyzeShot","Analyze Shot / Reanalyze","Select Temporal and set the shot range. This advances the saved render revision; the next host Render performs bounded analysis with host progress/cancel.");
    defineParam(set,kOfxParamTypePushButton,"cancelAnalysis","Cancel Analysis","Stop this node's current wait; other nodes retain independent ownership.");
    p = defineParam(set, kOfxParamTypeBoolean, "alphaHint", "Legacy Alpha",
        "Use an upstream rough subject matte. Leave off for ordinary opaque footage. This is a single-frame hint.");
    props->propSetInt(p, kOfxParamPropDefault, 0, 0);
    defineDouble(set, "hintQuality", "Hint Strength", "Trust in the supplied matte. Existing saved 0.95 values remain unchanged.", 0.75);
    defineDouble(set, "despill", "Despill Amount",
        "Additional screen-color suppression after foreground recovery. Zero preserves the model's foreground.", 0.0);
    p = defineParam(set, kOfxParamTypeChoice, "outputMode", "Output", "Keyed RGBA is premultiplied. Preview modes are opaque.");
    props->propSetString(p, kOfxParamPropChoiceOption, 0, "Premultiplied");
    props->propSetString(p, kOfxParamPropChoiceOption, 1, "Matte");
    props->propSetString(p, kOfxParamPropChoiceOption, 2, "Straight FG");
    props->propSetString(p, kOfxParamPropChoiceOption, 3, "Original");
    props->propSetInt(p, kOfxParamPropDefault, 0, 0);
    p = defineParam(set, kOfxParamTypeString, "socketPath", "Worker Socket",
        "Absolute path to your local CorridorKey worker socket. Run bash scripts/start_worker.sh before rendering.");
    props->propSetString(p, kOfxParamPropDefault, 0, ckmac::defaultSocketPath().c_str());
    props->propSetString(p, kOfxParamPropStringMode, 0, kOfxParamStringIsSingleLine);
#ifdef CKMAC_INSTALLED_RUNTIME
    props->propSetInt(p, kOfxParamPropSecret, 0, 1);
#endif
    defineParam(set, kOfxParamTypePushButton, "checkWorker", "Details", "Open optional maintenance, verification and GPU diagnostics.");
    p = defineParam(set, kOfxParamTypeBoolean, "acquisitionProbe", "Developer: Probe Temporal Access", "Temporary feasibility probe. Fetches three ordered node-input frames during Render, copies and releases each.");
    props->propSetInt(p, kOfxParamPropDefault, 0, 0);
    props->propSetInt(p, kOfxParamPropSecret, 0, 1);
    for(auto group:{"statusGroup","controlsGroup","timeAwarenessGroup","alphaHintGroup","edgeSpillGroup","outputGroup","renderGroup","helpGroup"}){
        p=defineParam(set,kOfxParamTypeGroup,group,!std::strcmp(group,"statusGroup")?"Status":!std::strcmp(group,"controlsGroup")?"Controls":!std::strcmp(group,"timeAwarenessGroup")?"Time Awareness":!std::strcmp(group,"alphaHintGroup")?"Alpha Hint":!std::strcmp(group,"edgeSpillGroup")?"Despill":!std::strcmp(group,"outputGroup")?"Output":!std::strcmp(group,"renderGroup")?"Render":"Help & Support","");
        props->propSetInt(p,kOfxParamPropGroupOpen,0,!std::strcmp(group,"statusGroup")||!std::strcmp(group,"controlsGroup")||!std::strcmp(group,"renderGroup"));
    }
    auto boolean=[&](const char* name,const char* label,int value,const char* hint){auto q=defineParam(set,kOfxParamTypeBoolean,name,label,hint);props->propSetInt(q,kOfxParamPropDefault,0,value);};
    auto choice=[&](const char* name,const char* label,std::initializer_list<const char*> choices,const char* hint){auto q=defineParam(set,kOfxParamTypeChoice,name,label,hint);int n=0;for(auto c:choices)props->propSetString(q,kOfxParamPropChoiceOption,n++,c);props->propSetInt(q,kOfxParamPropDefault,0,0);};
    auto text=[&](const char* name,const char* label,const char* value,bool editable){auto q=defineParam(set,kOfxParamTypeString,name,label,"");props->propSetString(q,kOfxParamPropDefault,0,value);props->propSetString(q,kOfxParamPropStringMode,0,editable?kOfxParamStringIsSingleLine:kOfxParamStringIsLabel);props->propSetInt(q,kOfxParamPropEnabled,0,editable);if(!editable){props->propSetInt(q,kOfxParamPropPersistant,0,0);props->propSetInt(q,kOfxParamPropEvaluateOnChange,0,0);}};
    text("status","Engine","Starts on render",false);
    text("fitForecast","GPU Memory","See Details",false);
    boolean("inputIsLinear","Input is Linear?",0,"Sets Input Encoding to Linear Rec.709 when checked, sRGB when unchecked. Gamma 2.4 remains available in Input Encoding.");
    choice("internalResolution","Internal Resolution",{"Full","Two Thirds (Upscaled)","Half (Upscaled)","Quarter (Upscaled)"},"Explicit model resolution. Output retains the host canvas. Native MPS above 2048×1152 is currently refused; choose a lower profile explicitly.");
    boolean("reuseCapturedFrames","Reuse Captures",0,"Reuse verified captures across reanalysis. Playback reuses unchanged captures automatically. Source and hint identities are always checked.");
    boolean("useTimeAwareness","Use Time Awareness?",0,"Selects the saved Temporal processing mode. Turning this off selects Single Frame.");
    p=defineParam(set,kOfxParamTypeInteger,"window","Window","Actual neural temporal window. Higher values require more GPU memory; no automatic window reduction.");
    props->propSetInt(p,kOfxParamPropDefault,0,4);props->propSetInt(p,kOfxParamPropMin,0,1);props->propSetInt(p,kOfxParamPropMax,0,48);props->propSetInt(p,kOfxParamPropDisplayMin,0,1);props->propSetInt(p,kOfxParamPropDisplayMax,0,48);
    choice("vramLimit","GPU Limit",{"Auto","50%","60%","70%","80%","90%"},"Fraction of Metal's recommended working set, not a promise of currently free RAM. Auto uses an 80% allocator ceiling. A request that cannot fit fails without changing quality.");
    boolean("lowGpuMemory","Low GPU Memory",0,"Use smaller equivalent MLP, attention-query and attention-window execution chunks. Spatial resolution, temporal window and float32 precision stay selected.");
    boolean("useAlphaHint","Use Hint",1,"Enable the explicitly selected Source Alpha or connected Hint input.");
    choice("hintFrames","Hint Frames",{"All Frames","Single Frame (requires Time Awareness)"},"Single Frame propagates from Reference Frame in two ordered temporal passes.");
    text("referenceFrame","Reference Frame","",true);
    defineParam(set,kOfxParamTypePushButton,"referenceFrameSet","Set Reference","Use the current integer node-input frame as the temporal reset and hint reference.");
    defineDouble(set,"modelHintTrust","Internal Hint","Trust in the previous window's neural hint, independently of the external hint.",.95);
    choice("screenColour","Despill Color",{"Auto","Green","Blue","Picked"},"Controls only additional despill. Auto measures source pixels weighted by background matte; the model itself has no screen-color switch.");
    p=defineParam(set,kOfxParamTypeRGB,"screenColourPicked","Picked Color","Screen color for additional despill.");
    for(int c=0;c<3;c++){props->propSetDouble(p,kOfxParamPropDefault,c,c==1?1.:0.);props->propSetDouble(p,kOfxParamPropMin,c,0);props->propSetDouble(p,kOfxParamPropMax,c,1);}
    defineParam(set,kOfxParamTypePushButton,"sampleAutoColour","Freeze Color","Copy the last completed render's detected background into Picked Color and select Picked.");
    choice("spillMethod","Despill Method",{"Average","Double Limit","Neutral"},"Average redistributes excess screen chroma. Double Limit removes less. Neutral blends contaminated color toward luminance gray.");
    boolean("linearizeOutput","Linear Output",0,"Return scene-linear RGB before the host applies premultiplication. The alpha remains unchanged.");
    boolean("recoverDetails","Keep Solid Detail",0,"Restore the original straight RGB where raw model alpha exceeds 0.95, before additional despill.");
    defineDouble(set,"alphaWhitePoint","White Point","Remap alpha by this white point, clamping to [0,1] while preserving straight foreground. 1 is neutral.",1);
    {auto q=descriptors.properties.at("alphaWhitePoint");props->propSetDouble(q,kOfxParamPropMin,0,.001);props->propSetDouble(q,kOfxParamPropDisplayMin,0,.001);}
    text("shotStatus","Render","On demand",false);
    defineParam(set,kOfxParamTypePushButton,"processShot","Analyze Shot","Select Temporal and advance the saved analysis revision. The next full host render processes the selected shot.");
    defineParam(set,kOfxParamTypePushButton,"cancelPass","Cancel","Cancel this node's current wait and prevent late output activation.");
    boolean("displayRenderedFrames","Show Result",1,"Off explicitly selects Original output. On selects Premultiplied. This is a saved output selection, never an inference failure fallback.");
    for(auto pair:{std::pair<const char*,const char*>{"openCacheFolder","Open Folder"},{"chooseRenderFolder","Choose Folder"},{"collectDiagnostics","Support File"},{"startGuidedHelp","Help"},{"clearCache","Clear Shot Cache"},{"checkUpdates","Offline Update"}})
        defineParam(set,kOfxParamTypePushButton,pair.first,pair.second,"Local maintenance; no media is uploaded and no online update check is performed.");
    text("version","Version","0.9.7 beta",false);
    // Resolve draws StringIsLabel readouts with duplicate labels. Keep the
    // serialized identifiers for compatibility; Details exposes actual status.
    for(auto name:{"status","fitForecast","version"})props->propSetInt(definingParameters->at(name),kOfxParamPropSecret,0,1);
    for(const char* name:{"analyzeShot","cancelAnalysis","shotStatus","inputIsLinear","useTimeAwareness","hintFrames"})props->propSetInt(descriptors.properties.at(name),kOfxParamPropSecret,0,1);
    std::map<std::string,const char*> parents;
    for(auto n:{"status","fitForecast","checkWorker"})parents[n]="statusGroup";
    for(auto n:{"inputIsLinear","inputSpace","internalResolution","reuseCapturedFrames"})parents[n]="controlsGroup";
    for(auto n:{"processingMode","useTimeAwareness","window","vramLimit","lowGpuMemory"})parents[n]="timeAwarenessGroup";
    for(auto n:{"useAlphaHint","hintSource","alphaHint","hintQuality","hintTiming","hintFrames","referenceFrame","referenceFrameSet","modelHintTrust"})parents[n]="alphaHintGroup";
    for(auto n:{"screenColour","screenColourPicked","sampleAutoColour","spillMethod","despill"})parents[n]="edgeSpillGroup";
    for(auto n:{"outputMode","linearizeOutput","recoverDetails","alphaWhitePoint"})parents[n]="outputGroup";
    for(auto n:{"shotStatus","analysisStart","analysisEnd","processShot","analyzeShot","cancelPass","cancelAnalysis","displayRenderedFrames","openCacheFolder","chooseRenderFolder"})parents[n]="renderGroup";
    for(auto n:{"version","collectDiagnostics","startGuidedHelp","clearCache","checkUpdates"})parents[n]="helpGroup";
    for(auto& pair:parents)props->propSetString(descriptors.properties.at(pair.first),kOfxParamPropParent,0,pair.second);
    p = defineParam(set, kOfxParamTypePage, "Controls", "Controls", "");
    int n = 0;
    for(const char* child:{"statusGroup","controlsGroup","timeAwarenessGroup","alphaHintGroup","edgeSpillGroup","outputGroup","renderGroup","helpGroup"})props->propSetString(p,kOfxParamPropPageChild,n++,child);
    for(auto& pair:parents)props->propSetString(p,kOfxParamPropPageChild,n++,pair.first.c_str());
    return kOfxStatOK;
}

OfxStatus createInstance(OfxImageEffectHandle effect) {
    auto instance = std::make_unique<Instance>();
    {std::random_device random;std::ostringstream owner;owner<<std::hex;for(int i=0;i<8;i++)owner<<random()<<'-';instance->owner=owner.str();}
    require(effects->clipGetHandle(effect, kOfxImageEffectSimpleSourceClipName, &instance->source, nullptr), "get source clip");
    require(effects->clipGetHandle(effect, kOfxImageEffectOutputClipName, &instance->output, nullptr), "get output clip");
    require(effects->clipGetHandle(effect,"Hint",&instance->hintClip,nullptr),"get optional hint clip");
    OfxParamSetHandle set = nullptr;
    require(effects->getParamSet(effect, &set), "get parameter set");
    for (auto pair : {std::pair<const char*, OfxParamHandle*>{"socketPath", &instance->socket},
                      {"inputSpace", &instance->inputSpace}, {"alphaHint", &instance->alphaHint},
                      {"hintQuality", &instance->hintQuality}, {"despill", &instance->despill},
                      {"outputMode", &instance->outputMode}, {"acquisitionProbe", &instance->acquisitionProbe},
                      {"processingMode",&instance->processing},{"analysisStart",&instance->rangeStart},{"analysisEnd",&instance->rangeEnd},
                      {"analysisRevision",&instance->revision},{"hintTiming",&instance->hintTiming}})
        require(params->paramGetHandle(set, pair.first, pair.second, nullptr), "get parameter");
    require(params->paramGetHandle(set,"hintSource",&instance->hintSource,nullptr),"get hint source parameter");
    for(auto name:{"inputIsLinear","internalResolution","reuseCapturedFrames","useTimeAwareness","window","vramLimit","lowGpuMemory","useAlphaHint","hintFrames","referenceFrame","modelHintTrust","screenColour","screenColourPicked","spillMethod","linearizeOutput","recoverDetails","alphaWhitePoint","displayRenderedFrames","status","fitForecast","shotStatus"})
        require(params->paramGetHandle(set,name,&instance->creative[name],nullptr),"get creative control");
    require(props->propSetPointer(effectProperties(effect), kOfxPropInstanceData, 0, instance.get()), "store instance data");
    instance.release();
    return kOfxStatOK;
}
OfxStatus destroyInstance(OfxImageEffectHandle effect) {
    delete instanceOf(effect);
    props->propSetPointer(effectProperties(effect), kOfxPropInstanceData, 0, nullptr);
    return kOfxStatOK;
}

struct Image {
    OfxPropertySetHandle handle = nullptr;
    ~Image() { if (handle) effects->clipReleaseImage(handle); }
    ckmac::ImageView view() const {
        char* depth = nullptr;
        char* components = nullptr;
        require(props->propGetString(handle, kOfxImageEffectPropPixelDepth, 0, &depth), "get image depth");
        require(props->propGetString(handle, kOfxImageEffectPropComponents, 0, &components), "get image components");
        if (!depth || std::strcmp(depth, kOfxBitDepthFloat) || !components || std::strcmp(components, kOfxImageComponentRGBA))
            throw std::runtime_error("CorridorKey requires 32-bit float RGBA host images.");
        ckmac::ImageView value;
        void* data = nullptr;
        int bounds[4]{}, rowBytes = 0;
        require(props->propGetPointer(handle, kOfxImagePropData, 0, &data), "get image data");
        require(props->propGetIntN(handle, kOfxImagePropBounds, 4, bounds), "get image bounds");
        require(props->propGetInt(handle, kOfxImagePropRowBytes, 0, &rowBytes), "get image stride");
        value.data = static_cast<unsigned char*>(data);
        value.bounds = {bounds[0], bounds[1], bounds[2], bounds[3]};
        value.rowBytes = rowBytes;
        ckmac::validateImage(value);
        int rod[4]{};
        if(props->propGetIntN(handle,kOfxImagePropRegionOfDefinition,4,rod)==kOfxStatOK){
            if(rod[0]<bounds[0]||rod[1]<bounds[1]||rod[2]>bounds[2]||rod[3]>bounds[3]||rod[2]<=rod[0]||rod[3]<=rod[1])throw std::runtime_error("Host supplied only part of the required full source extent.");
            value.data+=(std::ptrdiff_t(rod[1])-bounds[1])*value.rowBytes+(std::ptrdiff_t(rod[0])-bounds[0])*4*sizeof(float);
            value.bounds={rod[0],rod[1],rod[2],rod[3]};ckmac::validateImage(value);
        }
        return value;
    }
};

void applyHint(Instance* instance,double time,std::vector<float>& rgba,const ckmac::Rect& bounds,int source) {
    if(source<2)return;
    OfxPropertySetHandle properties=nullptr;require(effects->clipGetPropertySet(instance->hintClip,&properties),"get hint connection");
    int connected=0;require(props->propGetInt(properties,kOfxImageClipPropConnected,0,&connected),"check hint connection");
    if(!connected)throw std::runtime_error("Connect an aligned RGBA matte to Hint, or choose None / Source Alpha.");
    Image image;require(effects->clipGetImage(instance->hintClip,time,nullptr,&image.handle),"acquire aligned matte input");
    auto view=image.view();
    if(view.bounds.x1!=bounds.x1||view.bounds.y1!=bounds.y1||view.bounds.x2!=bounds.x2||view.bounds.y2!=bounds.y2)
        throw std::runtime_error("Hint input must match Source dimensions, origin and sample time. Resize/align it before this node.");
    char* premult=nullptr;require(props->propGetString(image.handle,kOfxImageEffectPropPreMultiplication,0,&premult),"get hint association");
    auto pixels=ckmac::packStraight(view,premult&&!std::strcmp(premult,kOfxImagePreMultiplied));
    for(std::size_t i=0;i<rgba.size();i+=4)rgba[i+3]=source==2?pixels[i+3]:.2126F*pixels[i]+.7152F*pixels[i+1]+.0722F*pixels[i+2];
}

// OFX defines this identifier specifically for reusing analysed image data.
// Keep owned strings only; all image acquisition/release remains in Render.
// An absent identifier always takes the content-fingerprint path.
std::string imageSignature(const Image& image) {
    char* uid=nullptr;char* association=nullptr;
    if(props->propGetString(image.handle,kOfxImagePropUniqueIdentifier,0,&uid)!=kOfxStatOK||!uid||!*uid)return {};
    require(props->propGetString(image.handle,kOfxImageEffectPropPreMultiplication,0,&association),"get image association");
    auto v=image.view();std::ostringstream s;
    s<<std::strlen(uid)<<":"<<uid<<":"<<(association?association:"")<<":"<<v.bounds.x1<<":"<<v.bounds.y1<<":"<<v.bounds.x2<<":"<<v.bounds.y2;
    return s.str();
}
std::string captureSignature(Instance* instance,const Image& image,double time,int hintSource) {
    auto signature=imageSignature(image);
    if(signature.empty())return {};
    signature+=":"+std::to_string(hintSource);
    if(hintSource>=2) {
        Image hint;require(effects->clipGetImage(instance->hintClip,time,nullptr,&hint.handle),"validate hint identity");
        auto other=imageSignature(hint);if(other.empty())return {};
        auto a=image.view(),b=hint.view();
        if(a.bounds.x1!=b.bounds.x1||a.bounds.y1!=b.bounds.y1||a.bounds.x2!=b.bounds.x2||a.bounds.y2!=b.bounds.y2)
            throw std::runtime_error("Align Hint and Source dimensions before analysis.");
        signature+=":"+other;
    }
    return signature;
}

OfxStatus render(OfxImageEffectHandle effect, OfxPropertySetHandle in) {
    auto* instance = instanceOf(effect);
    std::unique_lock<std::timed_mutex> guard(instance->renderMutex,std::defer_lock);
    while(!guard.try_lock_for(std::chrono::milliseconds(100)))if(effects->abort&&effects->abort(effect))throw ckmac::Cancelled();
    const auto generation=instance->generation.load();
    if (effects->abort && effects->abort(effect)) throw ckmac::Cancelled();
    // Never interpret GPU resource handles as CPU pixel pointers, even if a
    // host mistakenly ignores this plug-in's advertised render capabilities.
    for (const char* property : {"OfxImageEffectPropMetalEnabled", "OfxImageEffectPropCudaEnabled", "OfxImageEffectPropOpenCLEnabled"}) {
        int enabled = 0;
        if (props->propGetInt(in, property, 0, &enabled) == kOfxStatOK && enabled)
            throw std::runtime_error("Host passed GPU buffers. CorridorKey Mac requires CPU OFX buffers; its worker performs GPU inference.");
    }
    double time = 0;
    require(props->propGetDouble(in, kOfxPropTime, 0, &time), "get render time");
    int window[4]{};
    require(props->propGetIntN(in, kOfxImageEffectPropRenderWindow, 4, window), "get render window");
    char* field = nullptr;
    if (props->propGetString(in, kOfxImageEffectPropFieldToRender, 0, &field) == kOfxStatOK
        && field && std::strcmp(field, kOfxImageFieldNone))
        throw std::runtime_error("Use progressive footage or deinterlace before CorridorKey.");
    int probe=0;
    require(params->paramGetValueAtTime(instance->acquisitionProbe,time,&probe),"get temporal probe");
    if(probe) {
        int capability=0;props->propGetInt(host->host,kOfxImageEffectPropTemporalClipAccess,0,&capability);
        bool showing=progress&&progress->progressStart(effect,"CorridorKey temporal acquisition probe")==kOfxStatOK;
        std::ostringstream evidence;evidence<<"{\"action\":\"Render\",\"temporal_host\":"<<capability<<",\"progress_started\":"<<(showing?"true":"false")<<",\"frames\":[";
        try {
            for(int i=0;i<3;i++) {
                if(effects->abort&&effects->abort(effect))throw ckmac::Cancelled();
                Image frame;require(effects->clipGetImage(instance->source,time+i,nullptr,&frame.handle),"temporal source acquisition");
                auto view=frame.view();auto owned=ckmac::packStraight(view,false);
                double checksum=0;for(std::size_t k=0;k<owned.size();k++)checksum+=owned[k]*double(k%97+1);
                auto signature=imageSignature(frame);
                if(i)evidence<<",";evidence<<"{\"time\":"<<time+i<<",\"samples\":"<<owned.size()<<",\"checksum\":"<<checksum<<",\"has_unique_id\":"<<(signature.empty()?"false":"true")<<",\"identity_hash\":\""<<std::hash<std::string>{}(signature)<<"\"}";
                if(showing&&progress->progressUpdate(effect,(i+1)/3.0)==kOfxStatReplyNo)throw ckmac::Cancelled();
            }
        }catch(...){if(showing)progress->progressEnd(effect);throw;}
        if(showing)progress->progressEnd(effect);evidence<<"]}\n";
        auto log="/private/tmp/ckmac-acquisition-"+std::to_string(getuid())+".jsonl";
        int fd=open(log.c_str(),O_CREAT|O_WRONLY|O_APPEND|O_NOFOLLOW,0600);
        if(fd>=0){auto s=evidence.str();::write(fd,s.data(),s.size());::close(fd);}
    }
    Image source, output;
    require(effects->clipGetImage(instance->source, time, nullptr, &source.handle), "fetch full source image");
    require(effects->clipGetImage(instance->output, time, nullptr, &output.handle), "fetch output image");
    auto sourceView = source.view(), outputView = output.view();
    int sourceRod[4]{};
    if (props->propGetIntN(source.handle, kOfxImagePropRegionOfDefinition, 4, sourceRod) == kOfxStatOK
        && (sourceRod[0] != sourceView.bounds.x1 || sourceRod[1] != sourceView.bounds.y1
            || sourceRod[2] != sourceView.bounds.x2 || sourceRod[3] != sourceView.bounds.y2))
        throw std::runtime_error("Host supplied a partial source image. CorridorKey requires the full frame.");
    char* premult = nullptr;
    require(props->propGetString(source.handle, kOfxImageEffectPropPreMultiplication, 0, &premult), "get source alpha representation");
    if (!premult || (std::strcmp(premult, kOfxImagePreMultiplied) && std::strcmp(premult, kOfxImageUnPreMultiplied)
                     && std::strcmp(premult, kOfxImageOpaque)))
        throw std::runtime_error("Unknown source alpha representation.");
    auto input = ckmac::packStraight(sourceView, !std::strcmp(premult, kOfxImagePreMultiplied));
    int space = 0, hint = 0, mode = 0;
    int processing=0,start=0,end=-1,revision=0,hintTiming=0;
    int hintSource=0;
    double quality = 0.95, despill = 0;
    char* socket = nullptr;
    require(params->paramGetValueAtTime(instance->socket, time, &socket), "get worker socket");
    require(params->paramGetValueAtTime(instance->inputSpace, time, &space), "get input encoding");
    require(params->paramGetValueAtTime(instance->alphaHint, time, &hint), "get hint setting");
    require(params->paramGetValueAtTime(instance->hintQuality, time, &quality), "get hint confidence");
    require(params->paramGetValueAtTime(instance->despill, time, &despill), "get despill");
    require(params->paramGetValueAtTime(instance->outputMode, time, &mode), "get output mode");
    require(params->paramGetValueAtTime(instance->processing,time,&processing),"get processing mode");
    require(params->paramGetValueAtTime(instance->rangeStart,time,&start),"get shot start");
    require(params->paramGetValueAtTime(instance->rangeEnd,time,&end),"get shot end");
    require(params->paramGetValueAtTime(instance->revision,time,&revision),"get analysis revision");
    require(params->paramGetValueAtTime(instance->hintTiming,time,&hintTiming),"get hint timing");
    require(params->paramGetValueAtTime(instance->hintSource,time,&hintSource),"get hint source");
    if(!integer(instance,"useAlphaHint",time)){hint=0;hintSource=0;}
    char* reference=nullptr;require(params->paramGetValueAtTime(instance->creative.at("referenceFrame"),time,&reference),"get reference frame");
    int referenceFrame=start;
    if(reference&&*reference){std::size_t used=0;referenceFrame=std::stoi(reference,&used);if(reference[used])throw std::runtime_error("Reference Frame must be an integer or empty for the shot start.");}
    ckmac::PostSettings post;post.inputSpace=space;post.despill=despill;
    post.screen=integer(instance,"screenColour",time);post.method=integer(instance,"spillMethod",time);
    post.linearize=integer(instance,"linearizeOutput",time);post.recoverDetails=integer(instance,"recoverDetails",time);post.whitePoint=number(instance,"alphaWhitePoint",time);
    require(params->paramGetValueAtTime(instance->creative.at("screenColourPicked"),time,&post.picked[0],&post.picked[1],&post.picked[2]),"get picked color");
    if (mode < 0 || mode > 3 || space < 0 || space > 2 || processing<0 || processing>1 || hintTiming<0 || hintTiming>1 || hintSource<0 || hintSource>3) throw std::runtime_error("Invalid parameter value.");
    std::vector<float> result;
    if (mode == static_cast<int>(ckmac::OutputMode::Original)) {
        result = std::move(input);
    } else {
        if(hintTiming==1&&processing==0&&(hint||hintSource))throw std::runtime_error("Single Frame hints require Temporal processing; select All Frames for a Single Frame key.");
        if(processing==0||hintTiming==0||time==referenceFrame)applyHint(instance,time,input,sourceView.bounds,hintSource);
        hint=hint||hintSource!=0;
        ckmac::Settings settings{static_cast<std::uint32_t>(space), hint != 0, quality, 0};
        settings.internalResolution=integer(instance,"internalResolution",time);settings.temporalWindow=integer(instance,"window",time);
        settings.memoryLimit=integer(instance,"vramLimit",time);settings.lowMemory=integer(instance,"lowGpuMemory",time);
        if(processing==1&&hintTiming==1&&hint&&settings.temporalWindow<2)
            throw std::runtime_error("Reference hints need Window 2 or higher.");
        settings.internalHintQuality=number(instance,"modelHintTrust",time);
        auto referenceIndex=processing==1?std::int64_t(referenceFrame)-start:0;
        if(referenceIndex<0||referenceIndex>239)throw std::runtime_error("Reference Frame must lie inside the selected shot.");
        settings.referenceIndex=static_cast<int>(referenceIndex);
        if(settings.internalResolution<0||settings.internalResolution>3)throw std::runtime_error("Invalid Internal Resolution.");
        const double scale[]{1.,2./3.,.5,.25};
        if(std::nearbyint((sourceView.bounds.x2-sourceView.bounds.x1)*scale[settings.internalResolution])>2048||std::nearbyint((sourceView.bounds.y2-sourceView.bounds.y1)*scale[settings.internalResolution])>1152)
            throw std::runtime_error("Choose Half or Quarter Internal Resolution for this canvas. This beta supports up to 2048 x 1152 internally.");
#ifdef CKMAC_INSTALLED_RUNTIME
        bool showing=false;
        if(processing==1)showing=progress&&progress->progressStart(effect,"CorridorKey: acquiring and analyzing the selected shot")==kOfxStatOK;
        struct EndProgress{OfxImageEffectHandle effect;bool showing;~EndProgress(){if(showing)progress->progressEnd(effect);}} endProgress{effect,showing};
        double completed=0;
        auto lastProgress=std::chrono::steady_clock::time_point::min();
        auto cancelled=[&] {
            if(instance->generation.load()!=generation)return true;
            if(effects->abort&&effects->abort(effect))return true;
            auto now=std::chrono::steady_clock::now();
            if(showing&&(lastProgress==std::chrono::steady_clock::time_point::min()||now-lastProgress>=std::chrono::milliseconds(100))) {
                lastProgress=now;return progress->progressUpdate(effect,completed)==kOfxStatReplyNo;
            }
            return false;
        };
        ckmac::WorkerManager client(cancelled,generation,instance->owner);
        if(processing==1) {
            if(end<0) {
                OfxPropertySetHandle cp=nullptr;require(effects->clipGetPropertySet(instance->source,&cp),"get available source range");
                double last=0;require(props->propGetDouble(cp,kOfxImageEffectPropFrameRange,1,&last),"resolve shot end");end=static_cast<int>(std::floor(last));
            }
            if(end<start||std::int64_t(end)-start+1<2||std::int64_t(end)-start+1>240||time<start||time>end||std::floor(time)!=time)
                throw std::runtime_error("Set an inclusive 2–240 frame shot range containing this frame. Bake fractional/variable retiming before temporal analysis.");
            std::vector<std::string> keys;
            std::vector<std::string> signatures,known;
            // Reanalysis can explicitly recapture even content-identical input;
            // ordinary playback never rewrites the entire shot every frame.
            if(instance->capturedRevision!=revision&&!integer(instance,"reuseCapturedFrames",time))instance->captures.clear();
            instance->capturedRevision=revision;
            for(const auto& item:instance->captures)if(item.first>=start&&item.first<=end)known.push_back(item.second.key);
            auto presentList=client.inputsPresent(known);
            std::set<std::string> present(presentList.begin(),presentList.end());
            for(std::int64_t t=start;t<=end;t++) {
                if(cancelled())throw ckmac::Cancelled();
                Image frame;require(effects->clipGetImage(instance->source,t,nullptr,&frame.handle),"acquire ordered shot input");
                auto view=frame.view();
                if(view.bounds.x1!=sourceView.bounds.x1||view.bounds.y1!=sourceView.bounds.y1||view.bounds.x2!=sourceView.bounds.x2||view.bounds.y2!=sourceView.bounds.y2)
                    throw std::runtime_error("Input geometry changed inside the shot. Bake to a constant canvas before analysis.");
                char* association=nullptr;require(props->propGetString(frame.handle,kOfxImageEffectPropPreMultiplication,0,&association),"get temporal alpha association");
                int activeHint=hintTiming==0||t==referenceFrame?hintSource:0;
                auto signature=captureSignature(instance,frame,t,activeHint);
                auto previous=instance->captures.find(t);
                if(!signature.empty()&&previous!=instance->captures.end()&&previous->second.signature==signature&&present.count(previous->second.key)) {
                    keys.push_back(previous->second.key);
                } else {
                    auto owned=ckmac::packStraight(view,association&&!std::strcmp(association,kOfxImagePreMultiplied));
                    applyHint(instance,t,owned,view.bounds,activeHint);
                    keys.push_back(client.stage(view.bounds.x2-view.bounds.x1,view.bounds.y2-view.bounds.y1,owned));
                    instance->captures[t]={signature,keys.back()};
                }
                signatures.push_back(signature);
                completed=.4*double(t-start+1)/double(end-start+1);
            }
            if(cancelled())throw ckmac::Cancelled();
            OfxPropertySetHandle cp=nullptr;require(effects->clipGetPropertySet(instance->source,&cp),"get temporal source metadata");
            double fps=0,sx=1,sy=1;
            bool hasFps=props->propGetDouble(cp,kOfxImageEffectPropFrameRate,0,&fps)==kOfxStatOK&&std::isfinite(fps)&&fps>0;
            if(!hasFps)hasFps=props->propGetDouble(effectProperties(effect),kOfxImageEffectPropFrameRate,0,&fps)==kOfxStatOK&&std::isfinite(fps)&&fps>0;
            props->propGetDouble(in,kOfxImageEffectPropRenderScale,0,&sx);props->propGetDouble(in,kOfxImageEffectPropRenderScale,1,&sy);
            std::ostringstream provenance;provenance.precision(17);
            provenance<<"{\"start\":"<<start<<",\"end\":"<<end<<",\"time_domain\":\"integer_OFX_frames\",\"fps\":";
            if(hasFps)provenance<<fps;else provenance<<"null";
            provenance<<",\"origin\":["<<sourceView.bounds.x1<<","<<sourceView.bounds.y1<<"],\"scale\":["<<sx<<","<<sy<<"]}";
            auto captureContext=provenance.str()+":"+std::to_string(sourceView.bounds.x2-sourceView.bounds.x1)+":"+std::to_string(sourceView.bounds.y2-sourceView.bounds.y1);
            if(!instance->captureGuard.observe(captureContext,keys))
                throw std::runtime_error("Capture ready. Render again to verify the shot before analysis. Keep upstream settings unchanged.");
            result=client.temporal(sourceView.bounds.x2-sourceView.bounds.x1,sourceView.bounds.y2-sourceView.bounds.y1,keys,unsigned(time-start),settings,revision,hintTiming==1,provenance.str());
            // Resolve does not expose a globally atomic upstream revision here.
            // Revalidate the complete causal frame set before host activation.
            // This also detects changes during inference when the host exposes
            // them. The separate-action capture guard above is necessary:
            // same-action revalidation alone can return cached old images.
            for(std::int64_t t=start;t<=end;t++) {
                if(cancelled())throw ckmac::Cancelled();
                Image frame;require(effects->clipGetImage(instance->source,t,nullptr,&frame.handle),"revalidate temporal source generation");
                auto view=frame.view();char* association=nullptr;
                require(props->propGetString(frame.handle,kOfxImageEffectPropPreMultiplication,0,&association),"revalidate alpha association");
                int activeHint=hintTiming==0||t==referenceFrame?hintSource:0;
                auto signature=captureSignature(instance,frame,t,activeHint);
                if(!signatures[std::size_t(t-start)].empty()&&!signature.empty()) {
                    if(signature!=signatures[std::size_t(t-start)])throw std::runtime_error("Source changed during analysis. Analyze the updated shot again.");
                } else {
                    auto owned=ckmac::packStraight(view,association&&!std::strcmp(association,kOfxImagePreMultiplied));
                    applyHint(instance,t,owned,view.bounds,activeHint);
                    auto key=client.stage(view.bounds.x2-view.bounds.x1,view.bounds.y2-view.bounds.y1,owned);
                    if(key!=keys[std::size_t(t-start)])throw std::runtime_error("Source changed during analysis. No temporal result was activated. Analyze the updated shot again.");
                }
                completed=.9+.1*double(t-start+1)/double(end-start+1);
            }
            // Bound identity metadata as shots/ranges change; never retain frames.
            if(instance->captures.size()>480) {
                for(auto i=instance->captures.begin();i!=instance->captures.end();) {
                    if(i->first<start||i->first>end)i=instance->captures.erase(i);else ++i;
                }
            }
        } else {
            auto signature=captureSignature(instance,source,time,hintSource);
            auto previous=instance->frameCaptures.find(time);
            std::string key;
            if(!signature.empty()&&previous!=instance->frameCaptures.end()&&previous->second.signature==signature) {
                if(!client.inputsPresent({previous->second.key}).empty())key=previous->second.key;
            }
            if(key.empty()) {
                key=client.stage(sourceView.bounds.x2-sourceView.bounds.x1,sourceView.bounds.y2-sourceView.bounds.y1,input);
                if(instance->frameCaptures.size()>=240)instance->frameCaptures.clear();
                instance->frameCaptures[time]={signature,key};
            }
            result=client.inferCaptured(sourceView.bounds.x2-sourceView.bounds.x1,sourceView.bounds.y2-sourceView.bounds.y1,key,settings);
        }
#else
        ckmac::Client client(socket ? socket : "", [effect] { return effects->abort && effects->abort(effect); });
        result = client.infer(static_cast<std::uint32_t>(sourceView.bounds.x2 - sourceView.bounds.x1),
                              static_cast<std::uint32_t>(sourceView.bounds.y2 - sourceView.bounds.y1), input, settings);
#endif
        {std::lock_guard<std::mutex> sampleGuard(instance->sampleMutex);instance->detectedScreen=ckmac::detectScreen(input,result,space);instance->hasScreenSample=true;}
        if(post.despill||post.linearize||post.recoverDetails||post.whitePoint!=1)ckmac::applyPost(result,input,post);
    }
    if(instance->generation.load()!=generation)throw ckmac::Cancelled();
    if (effects->abort && effects->abort(effect)) throw ckmac::Cancelled();
    ckmac::writeOutput(result, sourceView.bounds, outputView,
                       {window[0], window[1], window[2], window[3]}, static_cast<ckmac::OutputMode>(mode));
    clearMessage(effect);
    return kOfxStatOK;
}

OfxStatus getRod(OfxImageEffectHandle effect, OfxPropertySetHandle in, OfxPropertySetHandle out, bool roi) {
    double time = 0;
    require(props->propGetDouble(in, kOfxPropTime, 0, &time), "get region time");
    OfxRectD rod{};
    require(effects->clipGetRegionOfDefinition(instanceOf(effect)->source, time, &rod), "get source region");
    const double values[]{rod.x1, rod.y1, rod.x2, rod.y2};
    require(props->propSetDoubleN(out, roi ? "OfxImageClipPropRoI_Source" : kOfxImageEffectPropRegionOfDefinition,
                                   4, values), "set required full-frame region");
    return kOfxStatOK;
}

OfxStatus changed(OfxImageEffectHandle effect, OfxPropertySetHandle in) {
    char* name = nullptr;
    if (props->propGetString(in, kOfxPropName, 0, &name) != kOfxStatOK || !name) return kOfxStatReplyDefault;
    auto* instance=instanceOf(effect);
    double time=0;props->propGetDouble(in,kOfxPropTime,0,&time);
    int probe=0;params->paramGetValueAtTime(instance->acquisitionProbe,time,&probe);
    if(probe) {
        char* type=nullptr;char* reason=nullptr;
        props->propGetString(in,kOfxPropType,0,&type);props->propGetString(in,kOfxPropChangeReason,0,&reason);
        auto path="/private/tmp/ckmac-changes-"+std::to_string(getuid())+".log";
        int fd=open(path.c_str(),O_CREAT|O_WRONLY|O_APPEND|O_NOFOLLOW,0600);
        if(fd>=0){std::ostringstream s;s<<"change "<<name<<" "<<(type?type:"")<<" "<<(reason?reason:"")<<" "<<time<<"\n";auto text=s.str();::write(fd,text.data(),text.size());::close(fd);}
    }
    auto setInteger=[&](OfxParamHandle h,int value){int old=0;require(params->paramGetValue(h,&old),"read linked control");if(old!=value)require(params->paramSetValue(h,value),"set linked control");};
    if(!std::strcmp(name,"inputIsLinear"))setInteger(instance->inputSpace,integer(instance,name,time)?1:0);
    if(!std::strcmp(name,"useTimeAwareness"))setInteger(instance->processing,integer(instance,name,time));
    if(!std::strcmp(name,"hintFrames"))setInteger(instance->hintTiming,integer(instance,name,time));
    if(!std::strcmp(name,"displayRenderedFrames"))setInteger(instance->outputMode,integer(instance,name,time)?0:3);
    if(!std::strcmp(name,"processingMode")){int v=0;params->paramGetValue(instance->processing,&v);setInteger(instance->creative.at("useTimeAwareness"),v);}
    if(!std::strcmp(name,"hintTiming")){int v=0;params->paramGetValue(instance->hintTiming,&v);setInteger(instance->creative.at("hintFrames"),v);}
    if(!std::strcmp(name,"referenceFrameSet")){
        if(std::floor(time)!=time)throw std::runtime_error("Choose an integer frame for the temporal reference.");
        auto value=std::to_string(static_cast<int>(time));require(params->paramSetValue(instance->creative.at("referenceFrame"),value.c_str()),"set reference frame");
    }
    if(!std::strcmp(name,"sampleAutoColour")){
        std::array<double,3> colour;
        {std::lock_guard<std::mutex> guard(instance->sampleMutex);if(!instance->hasScreenSample)throw std::runtime_error("Render one keyed frame before freezing its auto despill color.");colour=instance->detectedScreen;}
        require(params->paramSetValue(instance->creative.at("screenColourPicked"),colour[0],colour[1],colour[2]),"freeze detected screen color");
        setInteger(instance->creative.at("screenColour"),3);
    }
    if(!std::strcmp(name,"analyzeShot")||!std::strcmp(name,"processShot")) {
        if(!std::strcmp(name,"processShot")){setInteger(instance->processing,1);setInteger(instance->creative.at("useTimeAwareness"),1);setInteger(instance->outputMode,0);}
        int revision=0;require(params->paramGetValue(instance->revision,&revision),"read analysis revision");
        require(params->paramSetValue(instance->revision,revision==2147483647?0:revision+1),"activate saved analysis revision");
        instance->generation.fetch_add(1);return kOfxStatOK;
    }
#ifdef CKMAC_INSTALLED_RUNTIME
    if(!std::strcmp(name,"clearCache")){
        ckmac::WorkerManager client({},instance->generation.load(),instance->owner);
        client.control("{\"op\":\"clear_shot\"}");
        int revision=0;params->paramGetValue(instance->revision,&revision);require(params->paramSetValue(instance->revision,revision==2147483647?0:revision+1),"invalidate deleted shot cache");
        report(effect,kOfxMessageMessage,"This node's unshared captured and processed cache entries were deleted. Shared entries were retained.");return kOfxStatOK;
    }
    if(!std::strcmp(name,"openCacheFolder")||!std::strcmp(name,"chooseRenderFolder")||!std::strcmp(name,"collectDiagnostics")||!std::strcmp(name,"startGuidedHelp")||!std::strcmp(name,"clearCache")||!std::strcmp(name,"checkUpdates")){
        ckmac::openMaintenance(name);return kOfxStatOK;
    }
#endif
    if(std::strcmp(name,"checkWorker")) {instance->generation.fetch_add(1);clearMessage(effect);return kOfxStatReplyDefault;}
#ifdef CKMAC_INSTALLED_RUNTIME
    ckmac::openManager();return kOfxStatOK;
#else
    char* path = nullptr;
    require(params->paramGetValue(instanceOf(effect)->socket, &path), "get worker socket");
    report(effect, kOfxMessageMessage, ckmac::Client(path ? path : "", {}, 5.0).health());
    return kOfxStatOK;
#endif
}

OfxStatus mainEntry(const char* action, const void* rawEffect, OfxPropertySetHandle in, OfxPropertySetHandle out) {
    auto effect = reinterpret_cast<OfxImageEffectHandle>(const_cast<void*>(rawEffect));
    try {
        if (!action) return kOfxStatErrValue;
        if (!std::strcmp(action, kOfxActionLoad)) return load();
        if (!std::strcmp(action, kOfxActionUnload)) return kOfxStatOK;
        if (!props || !effects || !params) return kOfxStatErrMissingHostFeature;
        if (!std::strcmp(action, kOfxActionDescribe)) return describe(effect);
        if (!std::strcmp(action, kOfxImageEffectActionDescribeInContext)) return describeContext(effect);
        if (!std::strcmp(action, kOfxActionCreateInstance)) return createInstance(effect);
        if (!std::strcmp(action, kOfxActionDestroyInstance)) return destroyInstance(effect);
        if (!std::strcmp(action, kOfxImageEffectActionRender)) return render(effect, in);
        if (!std::strcmp(action, kOfxImageEffectActionGetFramesNeeded)) {
            double time=0;require(props->propGetDouble(in,kOfxPropTime,0,&time),"frame dependencies time");
            int probe=0;require(params->paramGetValueAtTime(instanceOf(effect)->acquisitionProbe,time,&probe),"frame dependency mode");
            double range[]{time,time+(probe?2:0)};
            auto* instance=instanceOf(effect);int processing=0,start=0,end=-1;
            require(params->paramGetValueAtTime(instance->processing,time,&processing),"get temporal dependencies");
            if(processing==1) {
                require(params->paramGetValueAtTime(instance->rangeStart,time,&start),"get temporal dependency start");
                require(params->paramGetValueAtTime(instance->rangeEnd,time,&end),"get temporal dependency end");
                range[0]=start;
                if(end>=start)range[1]=end;
                else {OfxPropertySetHandle cp=nullptr;require(effects->clipGetPropertySet(instance->source,&cp),"get source range properties");require(props->propGetDouble(cp,kOfxImageEffectPropFrameRange,1,range+1),"get source dependency end");}
                if(!std::isfinite(range[1])||range[1]<range[0]||range[1]-range[0]+1<2||range[1]-range[0]+1>240)throw std::runtime_error("Set an explicit 2–240 frame shot range before temporal processing.");
            }
            require(props->propSetDoubleN(out,"OfxImageClipPropFrameRange_Source",2,range),"frame dependencies");
            int source=0,timing=0;require(params->paramGetValueAtTime(instance->hintSource,time,&source),"hint dependencies");
            require(params->paramGetValueAtTime(instance->hintTiming,time,&timing),"hint timing dependencies");
            if(source>=2){
                double reference=range[0];char* value=nullptr;require(params->paramGetValueAtTime(instance->creative.at("referenceFrame"),time,&value),"reference hint dependency");
                if(value&&*value){std::size_t used=0;reference=std::stoi(value,&used);if(value[used])throw std::runtime_error("Reference Frame must be an integer.");}
                double hintRange[]{processing==1&&timing==1?reference:range[0],processing==1&&timing==1?reference:range[1]};require(props->propSetDoubleN(out,"OfxImageClipPropFrameRange_Hint",2,hintRange),"hint frame dependencies");
            }
            return kOfxStatOK;
        }
        if (!std::strcmp(action, kOfxImageEffectActionGetRegionOfDefinition)) return getRod(effect, in, out, false);
        if (!std::strcmp(action, kOfxImageEffectActionGetRegionsOfInterest)) return getRod(effect, in, out, true);
        if (!std::strcmp(action, kOfxImageEffectActionGetClipPreferences)) {
            props->propSetString(out, kOfxImageEffectPropPreMultiplication, 0, kOfxImagePreMultiplied);
            props->propSetString(out, "OfxImageClipPropComponents_Output", 0, kOfxImageComponentRGBA);
            props->propSetString(out, "OfxImageClipPropDepth_Output", 0, kOfxBitDepthFloat);
            props->propSetInt(out, kOfxImageClipPropContinuousSamples, 0, 0);
            return kOfxStatOK;
        }
        if (!std::strcmp(action, kOfxActionInstanceChanged)) return changed(effect, in);
        return kOfxStatReplyDefault;
    } catch (const ckmac::Cancelled&) {
        return kOfxStatFailed;
    } catch (const std::bad_alloc&) {
        if (effect) report(effect, kOfxMessageError, "Not enough CPU memory for this frame. Reduce resolution and retry.");
        return kOfxStatErrMemory;
    } catch (const std::exception& error) {
        if (effect) report(effect, kOfxMessageError, error.what());
        return kOfxStatFailed;
    } catch (...) {
        if (effect) report(effect, kOfxMessageError, "Unexpected CorridorKey plugin error.");
        return kOfxStatFailed;
    }
}

void setHost(OfxHost* value) { host = value; }
OfxPlugin plugin{kOfxImageEffectPluginApi, 1, "org.harvestpictures.CorridorKeyMac", 0, 9, setHost, mainEntry};
}  // namespace

#if defined(__GNUC__) || defined(__clang__)
#define CK_EXPORT __attribute__((visibility("default")))
#else
#define CK_EXPORT
#endif
extern "C" CK_EXPORT int OfxGetNumberOfPlugins() { return 1; }
extern "C" CK_EXPORT OfxPlugin* OfxGetPlugin(int index) { return index == 0 ? &plugin : nullptr; }
