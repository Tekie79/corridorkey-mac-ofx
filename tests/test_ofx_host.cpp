// Minimal independent OFX host harness: exercises the exported plugin contract.
// It does not stand in for DaVinci Resolve or Apple GPU acceptance testing.
#include "ofxCore.h"
#include "ofxImageEffect.h"
#include "ofxParam.h"
#include "ofxProperty.h"
#include "ofxMessage.h"
#include <array>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <iostream>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>
#ifdef CKMAC_INSTALLED_RUNTIME
#include "ckmac/bake.hpp"
#endif

extern "C" int OfxGetNumberOfPlugins();
extern "C" OfxPlugin* OfxGetPlugin(int);

namespace {
void check(bool ok, const char* why) { if(!ok) throw std::runtime_error(why); }
struct Properties {
    std::map<std::string,std::vector<int>> integers;
    std::map<std::string,std::vector<double>> doubles;
    std::map<std::string,std::vector<void*>> pointers;
    std::map<std::string,std::vector<std::string>> strings;
};
OfxPropertySetHandle handle(Properties& p) { return reinterpret_cast<OfxPropertySetHandle>(&p); }
Properties& property(OfxPropertySetHandle p) { return *reinterpret_cast<Properties*>(p); }
template<class T> OfxStatus set(std::map<std::string,std::vector<T>>& map,const char* name,int i,T value) {
    if(i<0) return kOfxStatErrBadIndex;
    auto& array=map[name]; if(array.size()<=static_cast<std::size_t>(i)) array.resize(i+1); array[i]=value; return kOfxStatOK;
}
template<class T> OfxStatus get(std::map<std::string,std::vector<T>>& map,const char* name,int i,T* value) {
    auto found=map.find(name);
    if(found==map.end()) return kOfxStatErrUnknown;
    if(i<0 || found->second.size()<=static_cast<std::size_t>(i)) return kOfxStatErrBadIndex;
    *value=found->second[i]; return kOfxStatOK;
}
OfxStatus setInt(OfxPropertySetHandle p,const char*n,int i,int v){return set(property(p).integers,n,i,v);}
OfxStatus setDouble(OfxPropertySetHandle p,const char*n,int i,double v){return set(property(p).doubles,n,i,v);}
OfxStatus setPointer(OfxPropertySetHandle p,const char*n,int i,void*v){return set(property(p).pointers,n,i,v);}
OfxStatus setString(OfxPropertySetHandle p,const char*n,int i,const char*v){return set(property(p).strings,n,i,std::string(v));}
OfxStatus getInt(OfxPropertySetHandle p,const char*n,int i,int*v){return get(property(p).integers,n,i,v);}
OfxStatus getDouble(OfxPropertySetHandle p,const char*n,int i,double*v){return get(property(p).doubles,n,i,v);}
OfxStatus getPointer(OfxPropertySetHandle p,const char*n,int i,void**v){return get(property(p).pointers,n,i,v);}
OfxStatus getString(OfxPropertySetHandle p,const char*n,int i,char**v){
    auto& map=property(p).strings; auto found=map.find(n);
    if(found==map.end())return kOfxStatErrUnknown;
    if(i<0||found->second.size()<=static_cast<std::size_t>(i))return kOfxStatErrBadIndex;
    *v=const_cast<char*>(found->second[i].c_str());return kOfxStatOK;
}
OfxStatus setDoubles(OfxPropertySetHandle p,const char*n,int count,const double*v){for(int i=0;i<count;++i)setDouble(p,n,i,v[i]);return kOfxStatOK;}
OfxStatus getInts(OfxPropertySetHandle p,const char*n,int count,int*v){for(int i=0;i<count;++i){auto s=getInt(p,n,i,v+i);if(s!=kOfxStatOK)return s;}return kOfxStatOK;}

struct Parameter{std::string type;Properties properties;};
struct ParamSet{std::map<std::string,Parameter> parameters;bool descriptor=true;};
struct Clip{Properties properties,image;std::vector<float> pixels;};
struct Effect{Properties properties;ParamSet parameters;std::map<std::string,Clip> clips;bool aborted=false;};
int fetched=0,released=0; std::string lastMessage;
Effect& effect(OfxImageEffectHandle e){return *reinterpret_cast<Effect*>(e);}
Clip& clip(OfxImageClipHandle c){return *reinterpret_cast<Clip*>(c);}
OfxStatus effectProps(OfxImageEffectHandle e,OfxPropertySetHandle*p){*p=handle(effect(e).properties);return kOfxStatOK;}
OfxStatus effectParams(OfxImageEffectHandle e,OfxParamSetHandle*p){*p=reinterpret_cast<OfxParamSetHandle>(&effect(e).parameters);return kOfxStatOK;}
OfxStatus defineClip(OfxImageEffectHandle e,const char*n,OfxPropertySetHandle*p){*p=handle(effect(e).clips[n].properties);return kOfxStatOK;}
OfxStatus getClip(OfxImageEffectHandle e,const char*n,OfxImageClipHandle*c,OfxPropertySetHandle*p){
    auto found=effect(e).clips.find(n);if(found==effect(e).clips.end())return kOfxStatErrUnknown;
    *c=reinterpret_cast<OfxImageClipHandle>(&found->second);if(p)*p=handle(found->second.properties);return kOfxStatOK;
}
OfxStatus getClipProps(OfxImageClipHandle c,OfxPropertySetHandle*p){*p=handle(clip(c).properties);return kOfxStatOK;}
OfxStatus getImage(OfxImageClipHandle c,OfxTime,const OfxRectD*,OfxPropertySetHandle*p){*p=handle(clip(c).image);++fetched;return kOfxStatOK;}
OfxStatus releaseImage(OfxPropertySetHandle){++released;return kOfxStatOK;}
OfxStatus clipRod(OfxImageClipHandle c,OfxTime,OfxRectD*r){
    auto& v=clip(c).image.integers[kOfxImagePropBounds];if(v.size()!=4)return kOfxStatErrValue;
    *r={double(v[0]),double(v[1]),double(v[2]),double(v[3])};return kOfxStatOK;
}
int abortEffect(OfxImageEffectHandle e){return effect(e).aborted;}
OfxStatus defineParameter(OfxParamSetHandle raw,const char*t,const char*n,OfxPropertySetHandle*p){
    auto& param=reinterpret_cast<ParamSet*>(raw)->parameters[n];param.type=t;*p=handle(param.properties);return kOfxStatOK;
}
OfxStatus getParameter(OfxParamSetHandle raw,const char*n,OfxParamHandle*p,OfxPropertySetHandle*props){
    if(reinterpret_cast<ParamSet*>(raw)->descriptor)return kOfxStatErrBadHandle;
    auto& map=reinterpret_cast<ParamSet*>(raw)->parameters;auto found=map.find(n);if(found==map.end())return kOfxStatErrUnknown;
    *p=reinterpret_cast<OfxParamHandle>(&found->second);if(props)*props=handle(found->second.properties);return kOfxStatOK;
}
OfxStatus value(Parameter& p,va_list args){
    if(p.type==kOfxParamTypeString)return getString(handle(p.properties),kOfxParamPropDefault,0,va_arg(args,char**));
    if(p.type==kOfxParamTypeDouble)return getDouble(handle(p.properties),kOfxParamPropDefault,0,va_arg(args,double*));
    if(p.type==kOfxParamTypeRGB){for(int i=0;i<3;i++){auto status=getDouble(handle(p.properties),kOfxParamPropDefault,i,va_arg(args,double*));if(status!=kOfxStatOK)return status;}return kOfxStatOK;}
    return getInt(handle(p.properties),kOfxParamPropDefault,0,va_arg(args,int*));
}
OfxStatus paramValue(OfxParamHandle raw,...){va_list args;va_start(args,raw);auto s=value(*reinterpret_cast<Parameter*>(raw),args);va_end(args);return s;}
OfxStatus paramValueAtTime(OfxParamHandle raw,OfxTime time,...){va_list args;va_start(args,time);auto s=value(*reinterpret_cast<Parameter*>(raw),args);va_end(args);return s;}
OfxStatus setParamValue(OfxParamHandle raw,...){
    auto& p=*reinterpret_cast<Parameter*>(raw);va_list args;va_start(args,raw);
    OfxStatus status=kOfxStatOK;
    if(p.type==kOfxParamTypeString)status=setString(handle(p.properties),kOfxParamPropDefault,0,va_arg(args,const char*));
    else if(p.type==kOfxParamTypeDouble)status=setDouble(handle(p.properties),kOfxParamPropDefault,0,va_arg(args,double));
    else status=setInt(handle(p.properties),kOfxParamPropDefault,0,va_arg(args,int));
    va_end(args);return status;
}
OfxStatus setMessage(void*,const char*,const char*,const char*format,...){
    va_list args;va_start(args,format);char text[2048];std::vsnprintf(text,sizeof(text),format,args);va_end(args);lastMessage=text;return kOfxStatOK;
}
OfxStatus clearMessage(void*){lastMessage.clear();return kOfxStatOK;}
OfxPropertySuiteV1 propertySuite{};
OfxImageEffectSuiteV1 effectSuite{};
OfxParameterSuiteV1 parameterSuite{};
OfxMessageSuiteV2 messageSuite{};
const void* fetchSuite(OfxPropertySetHandle,const char*n,int v){
    if(!std::strcmp(n,kOfxPropertySuite)&&v==1)return &propertySuite;
    if(!std::strcmp(n,kOfxImageEffectSuite)&&v==1)return &effectSuite;
    if(!std::strcmp(n,kOfxParameterSuite)&&v==1)return &parameterSuite;
    if(!std::strcmp(n,kOfxMessageSuite)&&v==2)return &messageSuite;
    return nullptr;
}
void initializeSuites(){
    propertySuite.propSetInt=setInt;propertySuite.propSetDouble=setDouble;propertySuite.propSetString=setString;propertySuite.propSetPointer=setPointer;
    propertySuite.propGetInt=getInt;propertySuite.propGetDouble=getDouble;propertySuite.propGetString=getString;propertySuite.propGetPointer=getPointer;
    propertySuite.propSetDoubleN=setDoubles;propertySuite.propGetIntN=getInts;
    effectSuite.getPropertySet=effectProps;effectSuite.getParamSet=effectParams;effectSuite.clipDefine=defineClip;
    effectSuite.clipGetHandle=getClip;effectSuite.clipGetPropertySet=getClipProps;effectSuite.clipGetImage=getImage;
    effectSuite.clipReleaseImage=releaseImage;effectSuite.clipGetRegionOfDefinition=clipRod;effectSuite.abort=abortEffect;
    parameterSuite.paramDefine=defineParameter;parameterSuite.paramGetHandle=getParameter;parameterSuite.paramGetValue=paramValue;parameterSuite.paramGetValueAtTime=paramValueAtTime;parameterSuite.paramSetValue=setParamValue;
    messageSuite.message=setMessage;messageSuite.setPersistentMessage=setMessage;messageSuite.clearPersistentMessage=clearMessage;
}
void prepareImage(Clip& c,const std::vector<float>& pixels){
    c.pixels=pixels;
    c.image.integers[kOfxImagePropBounds]={-2,3,0,5};
    c.image.integers[kOfxImagePropRegionOfDefinition]={-2,3,0,5};
    c.image.integers[kOfxImagePropRowBytes]={32};
    c.image.pointers[kOfxImagePropData]={c.pixels.data()};
    c.image.strings[kOfxImageEffectPropPixelDepth]={kOfxBitDepthFloat};
    c.image.strings[kOfxImageEffectPropComponents]={kOfxImageComponentRGBA};
    c.image.strings[kOfxImageEffectPropPreMultiplication]={kOfxImagePreMultiplied};
}
void put32(unsigned char*p,std::uint32_t v){p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;}
void readBytes(int fd,void*buffer,std::size_t size){auto*p=static_cast<unsigned char*>(buffer);while(size){auto n=::recv(fd,p,size,0);check(n>0,"Mock worker read failed");p+=n;size-=n;}}
struct Worker {
    std::string directory,path;int fd=-1;std::thread thread;std::exception_ptr failure;
    Worker(){
        char temp[]="/tmp/ckmac-host-XXXXXX";auto made=::mkdtemp(temp);check(made,"temp directory failed");directory=made;path=directory+"/worker.sock";
        fd=::socket(AF_UNIX,SOCK_STREAM,0);check(fd>=0,"worker socket failed");
        sockaddr_un address{};address.sun_family=AF_UNIX;std::memcpy(address.sun_path,path.c_str(),path.size()+1);
        check(!::bind(fd,reinterpret_cast<sockaddr*>(&address),sizeof(address)),"worker bind failed");::chmod(path.c_str(),0600);check(!::listen(fd,1),"worker listen failed");
        thread=std::thread([this]{
            int peer=::accept(fd,nullptr,nullptr);
            try{
                check(peer>=0,"worker accept failed");
                struct timeval timeout{2,0};::setsockopt(peer,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
                std::array<unsigned char,40> header{};readBytes(peer,header.data(),header.size());
                check(!std::memcmp(header.data(),"CKM1",4),"Bad OFX client request");
                std::array<float,16> input{};readBytes(peer,input.data(),sizeof(input));
                // Source top-left RGB is premultiplied (0.1,0.2,0.3), alpha=.5.
                check(std::abs(input[0]-.2F)<1e-6F && std::abs(input[1]-.4F)<1e-6F && input[3]==.5F,"Host source orientation/alpha wrong");
                std::array<float,16> output{.8F,.4F,.2F,.25F, .6F,.2F,.1F,.5F, .4F,.3F,.2F,1.F, .2F,.1F,0.F,0.F};
                std::array<unsigned char,32> reply{};std::memcpy(reply.data(),"CKR1",4);put32(reply.data()+4,1);put32(reply.data()+12,2);put32(reply.data()+16,2);put32(reply.data()+20,sizeof(output));
#ifdef MSG_NOSIGNAL
                check(::send(peer,reply.data(),reply.size(),MSG_NOSIGNAL)==static_cast<ssize_t>(reply.size()),"reply header failed");
                check(::send(peer,output.data(),sizeof(output),MSG_NOSIGNAL)==static_cast<ssize_t>(sizeof(output)),"reply pixels failed");
#else
                int noSignal=1;::setsockopt(peer,SOL_SOCKET,SO_NOSIGPIPE,&noSignal,sizeof(noSignal));
                check(::send(peer,reply.data(),reply.size(),0)==static_cast<ssize_t>(reply.size()),"reply header failed");
                check(::send(peer,output.data(),sizeof(output),0)==static_cast<ssize_t>(sizeof(output)),"reply pixels failed");
#endif
            }catch(...){failure=std::current_exception();}
            if(peer>=0)::close(peer);
        });
    }
    void finish(){if(thread.joinable())thread.join();if(failure)std::rethrow_exception(failure);}
    ~Worker(){if(fd>=0){::shutdown(fd,SHUT_RDWR);::close(fd);}if(thread.joinable())thread.join();::unlink(path.c_str());::rmdir(directory.c_str());}
};
}

int main(int argc,char** argv){
    try {
        initializeSuites();Properties hostProperties;OfxHost host{handle(hostProperties),fetchSuite};
        check(OfxGetNumberOfPlugins()==1 && !OfxGetPlugin(1),"Plugin exports incorrect");
        auto* plugin=OfxGetPlugin(0);check(plugin&&plugin->apiVersion==1,"Plugin API invalid");plugin->setHost(&host);
        check(plugin->mainEntry(kOfxActionLoad,nullptr,nullptr,nullptr)==kOfxStatOK,"Load failed");
        Effect e;auto raw=reinterpret_cast<OfxImageEffectHandle>(&e);Properties in,out;
        auto action=[&](const char*name){return plugin->mainEntry(name,raw,handle(in),handle(out));};
        check(action(kOfxActionDescribe)==kOfxStatOK,"Describe failed");
        check(e.properties.strings["OfxImageEffectPropMetalRenderSupported"][0]=="false","Must not advertise host Metal buffers");
        check(action(kOfxImageEffectActionDescribeInContext)==kOfxStatOK,"Context description failed");
        check(e.clips["Source"].properties.integers[kOfxImageClipPropOptional][0]==1,"RGBA bake must allow disconnected Source");
        prepareImage(e.clips["Source"],{.2F,.1F,0.F,1.F, .1F,.1F,.1F,1.F, .1F,.2F,.3F,.5F, .4F,.4F,.4F,1.F});
        prepareImage(e.clips["Output"],std::vector<float>(16,-9.F));
        e.parameters.descriptor=false;
        check(action(kOfxActionCreateInstance)==kOfxStatOK,"Instance create failed");
        in.doubles[kOfxPropTime]={12.0};in.integers[kOfxImageEffectPropRenderWindow]={-2,3,0,5};in.strings[kOfxImageEffectPropFieldToRender]={kOfxImageFieldNone};
        check(action(kOfxImageEffectActionGetRegionsOfInterest)==kOfxStatOK,"ROI failed");
        check(out.doubles["OfxImageClipPropRoI_Source"]==std::vector<double>({-2,3,0,5}),"Inference must request full source");
        check(action(kOfxImageEffectActionGetClipPreferences)==kOfxStatOK,"Clip preferences failed");
        check(out.strings[kOfxImageEffectPropPreMultiplication][0]==kOfxImagePreMultiplied,"Output must advertise premultiplication");
        check(out.integers[kOfxImageEffectFrameVarying][0]==1,"Baked sequences must vary with time even over static Source");
#ifdef CKMAC_INSTALLED_RUNTIME
        check(argc==2,"Pass a verified RGBA bake manifest to the native baked-mode harness");
        auto info=ckmac::inspectBake(argv[1],true);
        e.parameters.parameters["bakedManifest"].properties.strings[kOfxParamPropDefault]={argv[1]};
        in.doubles[kOfxPropTime]={double(info.start)};
        // No Source pixel pointer and no worker. Any accidental Source access
        // fails immediately through format validation rather than a false pass.
        e.clips["Source"].image.strings[kOfxImageEffectPropPixelDepth]={kOfxBitDepthShort};
        fetched=released=0;
        check(action(kOfxImageEffectActionRender)==kOfxStatOK,lastMessage.c_str());
        check(fetched==1&&released==1,"RGBA bake must fetch only Output");
        auto& result=e.clips["Output"].pixels;
        // Fixture: source origin -2,3,2x2; top-row alpha .25; bottom .5.
        check(result[0]==-1.F&&result[3]==.5F&&result[8]==-.5F&&result[11]==.25F,"Native baked samples/orientation/HDR mismatch");
        check(action(kOfxActionSyncPrivateData)==kOfxStatOK,"Serialize completed analysis identity");
        check(e.parameters.parameters["savedAnalysisGeneration"].properties.strings[kOfxParamPropDefault][0]==info.generation,"Analysis identity must survive project save");
        check(action(kOfxActionDestroyInstance)==kOfxStatOK,"baked destroy");
        // Recreate instance from saved host params, no inference process.
        check(action(kOfxActionCreateInstance)==kOfxStatOK,"baked recreate");
        check(action(kOfxImageEffectActionRender)==kOfxStatOK,lastMessage.c_str());
        check(action(kOfxActionDestroyInstance)==kOfxStatOK,"baked destroy after reopen");
        // A different host canvas must be filled, not letterboxed into one corner.
        e.clips["Output"].pixels.assign(64,-9.F);
        e.clips["Output"].image.integers[kOfxImagePropBounds]={-2,3,2,7};
        e.clips["Output"].image.integers[kOfxImagePropRegionOfDefinition]={-2,3,2,7};
        e.clips["Output"].image.integers[kOfxImagePropRowBytes]={64};
        e.clips["Output"].image.pointers[kOfxImagePropData]={e.clips["Output"].pixels.data()};
        in.integers[kOfxImageEffectPropRenderWindow]={-2,3,2,7};
        check(action(kOfxActionCreateInstance)==kOfxStatOK,"scaled bake create");
        check(action(kOfxImageEffectActionRender)==kOfxStatOK,"scaled bake render");
        check(e.clips["Output"].pixels[3]==.5F&&e.clips["Output"].pixels[63]==.25F,"Full-frame alpha mapping must fill enlarged canvas");
        check(e.clips["Output"].pixels[0]==-1.F&&e.clips["Output"].pixels[60]==-.5F,"Scaled signed foreground/premultiplication mismatch");
        check(action(kOfxActionDestroyInstance)==kOfxStatOK,"scaled bake destroy");
        prepareImage(e.clips["Output"],std::vector<float>(16,-9.F));in.integers[kOfxImageEffectPropRenderWindow]={-2,3,0,5};
        // Missing media fails explicitly without inference or Source fallback.
        e.parameters.parameters["bakedManifest"].properties.strings[kOfxParamPropDefault]={std::string(argv[1])+".offline"};
        check(action(kOfxActionCreateInstance)==kOfxStatOK,"relink instance create");
        check(action(kOfxImageEffectActionRender)==kOfxStatFailed,"Missing bake must fail");
        check(lastMessage.find("NeedsRelink")!=std::string::npos,"Missing bake needs an explicit relink state");
        e.parameters.parameters["previousBake"].properties.strings[kOfxParamPropDefault]={argv[1]};
        in.strings[kOfxPropName]={"revertBake"};
        check(action(kOfxActionInstanceChanged)==kOfxStatOK,"Revert verified bake");
        check(action(kOfxImageEffectActionRender)==kOfxStatOK,"Reverted bake render");
        check(action(kOfxActionDestroyInstance)==kOfxStatOK,"relink destroy");
        std::cout<<"native_bake: full validation, worker/source absent, signed HDR, origin, alpha, orientation and saved-parameter recreation passed; not Resolve qualification\n";
        return 0;
#else
        (void)argc;(void)argv;
        {
            Worker worker;e.parameters.parameters["socketPath"].properties.strings[kOfxParamPropDefault]={worker.path};
            check(action(kOfxImageEffectActionRender)==kOfxStatOK,lastMessage.c_str());worker.finish();
        }
        auto& result=e.clips["Output"].pixels;
        check(std::abs(result[8]-.2F)<1e-6F && std::abs(result[9]-.1F)<1e-6F && result[11]==.25F,"Keyed render orientation/premultiplication wrong");
        check(result[0]==.4F && result[3]==1.F && result[4]==0.F && result[7]==0.F,"Lower-row model result wrong");
        check(fetched==released,"Render leaked OFX image handles");
        e.parameters.parameters["socketPath"].properties.strings[kOfxParamPropDefault]={"/no-worker.sock"};
        check(action(kOfxImageEffectActionRender)==kOfxStatFailed,"Missing worker must fail rather than silently bypass");
        check(lastMessage.find("worker is not running")!=std::string::npos,"Missing worker diagnostic absent");
        check(fetched==released,"Failure leaked images");
        e.parameters.parameters["outputMode"].properties.integers[kOfxParamPropDefault]={3};
        check(action(kOfxImageEffectActionRender)==kOfxStatOK,"Explicit Original preview should work without worker");
        check(lastMessage.empty(),"Successful preview did not clear stale error");
        e.clips["Source"].image.strings[kOfxImageEffectPropPixelDepth]={kOfxBitDepthShort};
        check(action(kOfxImageEffectActionRender)==kOfxStatFailed,"Unsupported pixels should fail");
        check(fetched==released,"Rejected format leaked images");
        e.aborted=true;check(action(kOfxImageEffectActionRender)==kOfxStatFailed,"Abort ignored");
        in.strings[kOfxPropName]={"processShot"};
        check(action(kOfxActionInstanceChanged)==kOfxStatOK,"Analyze/Resume action failed");
        check(e.parameters.parameters["analysisRevision"].properties.integers[kOfxParamPropDefault][0]==0,"Analyze/Resume must be idempotent");
        check(e.parameters.parameters["analysisRequest"].properties.integers[kOfxParamPropDefault][0]==1,"Analyze/Resume must invalidate host output");
        in.strings[kOfxPropName]={"forceReanalyze"};
        check(action(kOfxActionInstanceChanged)==kOfxStatOK,"Force Reanalyze failed");
        check(e.parameters.parameters["analysisRevision"].properties.integers[kOfxParamPropDefault][0]==1,"Force must create a new revision");
        check(action(kOfxActionDestroyInstance)==kOfxStatOK,"Destroy failed");
        check(plugin->mainEntry(kOfxActionUnload,nullptr,nullptr,nullptr)==kOfxStatOK,"Unload failed");
        std::cout<<"ofx_host: exported actions, real transport render, alpha/origin, ROI, errors, cancellation and image lifetime passed\n";
        return 0;
#endif
    }catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
}
