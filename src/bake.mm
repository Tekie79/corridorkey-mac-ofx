#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#include <CommonCrypto/CommonDigest.h>
#include "ckmac/bake.hpp"
#include "ckmac/picker.hpp"
#include <cstring>
#include <cmath>
#include <fstream>
#include <filesystem>
#include <stdexcept>
#include <map>
#include <algorithm>
namespace ckmac {
namespace {
[[noreturn]] void bad(const char* why){throw std::runtime_error(why);}
NSDictionary* manifest(const std::string& path){
    NSData* data=[NSData dataWithContentsOfFile:@(path.c_str())];
    if(!data||data.length>2*1024*1024)bad("NeedsRelink: baked manifest is unavailable. Relink the verified bake; no analysis was started.");
    id d=[NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    if(![d isKindOfClass:[NSDictionary class]]||[d[@"version"] intValue]!=1||![d[@"state"] isEqual:@"Verified"]||![d[@"files"] isKindOfClass:[NSArray class]])bad("Invalid baked manifest");
    return d;
}
std::string string(NSString* s){if(![s isKindOfClass:[NSString class]])bad("Invalid baked string");return s.UTF8String;}
std::vector<float> decode(NSData* data,unsigned width,unsigned height,const std::string& kind,const std::string& precision){
    const unsigned char* bytes=static_cast<const unsigned char*>(data.bytes);size_t size=data.length,pos=0;
    auto u32=[&](){if(pos+4>size)bad("Truncated baked EXR");uint32_t n=0;for(int i=0;i<4;i++)n|=uint32_t(bytes[pos++])<<(8*i);return n;};
    auto u64=[&](){uint64_t a=u32(),b=u32();return a|(b<<32);};
    auto z=[&](){std::string s;while(pos<size&&bytes[pos]){if(s.size()>255)bad("Invalid EXR name");s+=char(bytes[pos++]);}if(pos==size)bad("Truncated EXR name");++pos;return s;};
    if(u32()!=20000630||u32()!=2)bad("Unsupported baked EXR version");
    struct Channel {std::string name;unsigned type;};std::vector<Channel> channels;
    bool canvas=false,compression=false;
    while(true){
        auto name=z();if(name.empty())break;auto type=z();auto n=u32();size_t end=pos+n;
        if(end>size||n>65536)bad("Invalid EXR attribute size");
        if(name=="compression"){if(type!="compression"||n!=1||bytes[pos]!=0)bad("Bake requires uncompressed EXR");compression=true;}
        if(name=="dataWindow"){
            if(type!="box2i"||n!=16)bad("Invalid EXR data window");
            auto x=int32_t(u32()),y=int32_t(u32()),x2=int32_t(u32()),y2=int32_t(u32());
            if(x!=0||y!=0||int64_t(x2)+1!=width||int64_t(y2)+1!=height)bad("Baked EXR canvas mismatch");canvas=true;
        }
        if(name=="channels"){
            if(type!="chlist")bad("Invalid EXR channels");
            while(pos<end&&bytes[pos]){
                auto c=z();auto t=u32();u32();auto xs=u32(),ys=u32();
                if(t!=(precision=="half"?1:2)||xs!=1||ys!=1||channels.size()>=4)bad("Unsupported EXR channel");channels.push_back({c,t});
            }
        }
        pos=end;
    }
    if(!canvas||!compression)bad("Missing EXR metadata");
    std::string names;size_t row=0;
    for(auto& c:channels){names+=c.name;row+=width*(c.type==1?2:4);}
    if(names!=(kind=="alpha"?"A":"ABGR"))bad("Baked EXR alpha/RGBA channels mismatch");
    std::vector<uint64_t> offsets(height);for(auto& o:offsets)o=u64();
    std::vector<float> result(size_t(width)*height*4,0);
    auto half=[](unsigned h){
        uint32_t sign=(h&0x8000)<<16,e=(h>>10)&31,m=h&1023,bits;
        if(e==0){
            if(!m)bits=sign;
            else {uint32_t exponent=113;while(!(m&1024)){m<<=1;--exponent;}bits=sign|(exponent<<23)|((m&1023)<<13);}
        }else bits=sign|((e==31?255:e+112)<<23)|(m<<13);
        float value;std::memcpy(&value,&bits,4);return value;
    };
    for(unsigned y=0;y<height;y++){
        if(offsets[y]>size||size-offsets[y]<8)bad("Invalid EXR offset");pos=size_t(offsets[y]);
        if(u32()!=y||u32()!=row||row>size-pos)bad("Invalid EXR scanline");
        for(auto& c:channels){
            unsigned component=c.name=="R"?0:c.name=="G"?1:c.name=="B"?2:3;
            for(unsigned x=0;x<width;x++){
                float v;
                if(c.type==1){unsigned h=bytes[pos]|(unsigned(bytes[pos+1])<<8);pos+=2;v=half(h);}
                else {auto bits=u32();std::memcpy(&v,&bits,4);}
                if(!std::isfinite(v)||(component==3&&(v<0||v>1)))bad("Baked EXR contains invalid samples");
                result[(size_t(y)*width+x)*4+component]=v;
            }
        }
    }
    return result;
}
}
BakeInfo inspectBake(const std::string& path,bool verifyAll){@autoreleasepool {
    auto d=manifest(path);BakeInfo i;i.path=path;i.kind=string(d[@"kind"]);i.generation=string(d[@"generation"]);i.encoding=string(d[@"rgb_encoding"]);
    if(i.kind!="alpha"&&i.kind!="rgba")bad("Invalid bake type");
    if(i.encoding!="linear"&&i.encoding!="srgb"&&i.encoding!="rec709_gamma24")bad("Unsupported baked RGB encoding");
    if(i.generation.size()!=64||i.generation.find_first_not_of("0123456789abcdef")!=std::string::npos)bad("Invalid bake generation");
    int w=[d[@"width"] intValue],h=[d[@"height"] intValue];
    if(w<1||h<1||w>8192||h>8192||int64_t(w)*h>33554432)bad("Invalid bake extent");
    NSArray* origin=d[@"origin"];if(![origin isKindOfClass:[NSArray class]]||origin.count!=2)bad("Invalid bake origin");
    int x=[origin[0] intValue],y=[origin[1] intValue];if(std::abs(int64_t(x))+w>2147483647||std::abs(int64_t(y))+h>2147483647)bad("Invalid bake origin");
    i.pixelAspect=[d[@"pixel_aspect"] doubleValue];if(!std::isfinite(i.pixelAspect)||i.pixelAspect<=0)bad("Invalid baked pixel aspect");
    auto precision=string(d[@"precision"]);if(precision!="half"&&precision!="float")bad("Invalid baked EXR precision");
    i.bounds={x,y,x+w,y+h};i.start=[d[@"start"] intValue];i.end=[d[@"end"] intValue];i.fps=[d[@"fps"] doubleValue];
    NSArray* files=d[@"files"];
    if(int64_t(i.end)-i.start+1<1||int64_t(i.end)-i.start+1>240||files.count!=NSUInteger(int64_t(i.end)-i.start+1)||!std::isfinite(i.fps)||i.fps<=0)bad("Invalid bake frame mapping");
    for(int64_t t=i.start;t<=i.end;t++){
        NSDictionary* entry=files[NSUInteger(t-i.start)];std::string name=string(entry[@"name"]);
        if([entry[@"frame"] longLongValue]!=t||std::filesystem::path(name).filename()!=name||std::filesystem::path(name).extension()!=".exr")bad("Invalid baked frame filename");
        if(verifyAll)readBake(i,int(t));
    }
    NSDictionary* post=d[@"post"];
    i.post.inputSpace=i.encoding=="linear"?1:i.encoding=="rec709_gamma24"?2:0;
    if([post isKindOfClass:[NSDictionary class]]){
        i.post.despill=[post[@"despill"] doubleValue];i.post.whitePoint=post[@"whitePoint"]?[post[@"whitePoint"] doubleValue]:1;
        i.post.screen=[post[@"screen"] intValue];i.post.method=[post[@"method"] intValue];
        i.post.linearize=[post[@"linearize"] boolValue];i.post.recoverDetails=[post[@"recoverDetails"] boolValue];
        NSArray* picked=post[@"picked"];if([picked isKindOfClass:[NSArray class]]&&picked.count==3)for(int c=0;c<3;c++)i.post.picked[c]=[picked[c] doubleValue];
    }
    return i;
}}
std::vector<float> readBake(const BakeInfo& info,int frame){@autoreleasepool {
    if(frame<info.start||frame>info.end)bad("Requested frame is outside the verified bake");
    auto d=manifest(info.path);NSDictionary* entry=d[@"files"][NSUInteger(frame-info.start)];
    std::string name=string(entry[@"name"]);if(std::filesystem::path(name).filename()!=name)bad("Invalid baked frame path");
    auto path=std::filesystem::path(info.path).parent_path()/name;
    NSData* data=[NSData dataWithContentsOfFile:@(path.c_str()) options:NSDataReadingMappedIfSafe error:nil];
    if(!data)bad("NeedsRelink: baked media unavailable. Relink the bake; no model work was started.");
    if(data.length>size_t(info.bounds.x2-info.bounds.x1)*(info.bounds.y2-info.bounds.y1)*16+1024*1024)bad("Invalid baked EXR length");
    unsigned char hash[CC_SHA256_DIGEST_LENGTH];CC_SHA256(data.bytes,CC_LONG(data.length),hash);char hex[65];for(int n=0;n<32;n++)snprintf(hex+n*2,3,"%02x",hash[n]);
    if(string(entry[@"sha256"])!=hex)bad("Baked EXR checksum mismatch; relink a verified version");
    return decode(data,unsigned(info.bounds.x2-info.bounds.x1),unsigned(info.bounds.y2-info.bounds.y1),info.kind,string(d[@"precision"]));
}}
std::vector<float> fitBake(std::vector<float> rgba,int width,int height,int targetWidth,int targetHeight,const std::string& encoding,bool alphaOnly){
    if(width<1||height<1||targetWidth<1||targetHeight<1||targetWidth>8192||targetHeight>8192||int64_t(targetWidth)*targetHeight>33554432||rgba.size()!=size_t(width)*height*4)bad("Invalid bake resampling canvas");
    if(width==targetWidth&&height==targetHeight)return rgba;
    auto decode=[&](double x){if(encoding=="linear")return x;double a=std::abs(x);return std::copysign(encoding=="rec709_gamma24"?std::pow(a,2.4):a<=.04045?a/12.92:std::pow((a+.055)/1.055,2.4),x);};
    auto encode=[&](double x){if(encoding=="linear")return x;double a=std::abs(x);return std::copysign(encoding=="rec709_gamma24"?std::pow(a,1/2.4):a<=.0031308?12.92*a:1.055*std::pow(a,1/2.4)-.055,x);};
    if(!alphaOnly&&encoding!="linear")for(size_t i=0;i<rgba.size();i+=4)for(int c=0;c<3;c++)rgba[i+c]=float(decode(rgba[i+c]));
    std::vector<float> out(size_t(targetWidth)*targetHeight*4,0);
    for(int y=0;y<targetHeight;y++){
        double sy=std::clamp((y+.5)*height/targetHeight-.5,0.,double(height-1));int y0=int(sy),y1=std::min(y0+1,height-1);double fy=sy-y0;
        for(int x=0;x<targetWidth;x++){
            double sx=std::clamp((x+.5)*width/targetWidth-.5,0.,double(width-1));int x0=int(sx),x1=std::min(x0+1,width-1);double fx=sx-x0;
            for(int c=alphaOnly?3:0;c<4;c++){
                double top=rgba[(size_t(y0)*width+x0)*4+c]*(1-fx)+rgba[(size_t(y0)*width+x1)*4+c]*fx;
                double bottom=rgba[(size_t(y1)*width+x0)*4+c]*(1-fx)+rgba[(size_t(y1)*width+x1)*4+c]*fx;
                double value=top*(1-fy)+bottom*fy;
                value=c==3?std::clamp(value,0.,1.):encode(value);
                if(!std::isfinite(value)||std::abs(value)>3.402823466e38)bad("Bake resampling exceeded finite float range");
                out[(size_t(y)*targetWidth+x)*4+c]=float(value);
            }
        }
    }
    return out;
}
std::string chooseBakeFolder(){
    return chooseNativePath(PickerKind::BakeFolder);
}
std::string chooseBakeManifest(){
    return chooseNativePath(PickerKind::BakeManifest);
}
}
