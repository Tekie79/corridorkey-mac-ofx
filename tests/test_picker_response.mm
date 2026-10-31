#import <Foundation/Foundation.h>
#include "ckmac/picker.hpp"
#include "ckmac/installation.hpp"
#include <stdexcept>
#include <cstdio>

int main(){@autoreleasepool{try {
    auto response=[](id path,NSString* profile=@CKMAC_PROFILE){
        NSData* data=[NSJSONSerialization dataWithJSONObject:@{@"version":@1,@"profile":profile,@"path":path} options:0 error:nil];
        return std::string(static_cast<const char*>(data.bytes),data.length);
    };
    const char* path="/Volumes/QA test/日本語/manifest.json";
    if(ckmac::parsePickerResponse(response(@(path)))!=path)throw std::runtime_error("Unicode/space path damaged");
    if(!ckmac::parsePickerResponse(response([NSNull null])).empty())throw std::runtime_error("Cancel was not empty");
    for(const auto& invalid:{std::string(),std::string("{}"),std::string("[]"),std::string(65537,'x'),
         response(@"relative/manifest.json"),response(@42),response(@"/tmp/a",@"foreign-profile"),
         std::string("{\"version\":1,\"profile\":\"") + CKMAC_PROFILE + "\",\"path\":\"/tmp/a\\u0000b\"}"}){
        bool refused=false;try{ckmac::parsePickerResponse(invalid);}catch(const std::runtime_error&){refused=true;}
        if(!refused)throw std::runtime_error("Invalid picker response accepted");
    }
    puts("picker_response: selected/cancel/Unicode and malformed/cross-profile/NUL responses passed");return 0;
}catch(const std::exception& e){fprintf(stderr,"%s\n",e.what());return 1;}}}
