#import <Cocoa/Cocoa.h>
#include "ckmac/installation.hpp"
#include "ckmac/picker.hpp"
#include <stdexcept>

namespace ckmac {
std::string parsePickerResponse(const std::string& response) {
    if(response.empty()||response.size()>65536)throw std::runtime_error("The native file picker returned an invalid response. Retry the operation.");
    NSData* data=[NSData dataWithBytes:response.data() length:response.size()];
    id value=[NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    if(![value isKindOfClass:[NSDictionary class]]||[value count]!=3||
       ![value[@"version"] isEqual:@1]||![value[@"profile"] isEqual:@CKMAC_PROFILE])
        throw std::runtime_error("The native file picker does not match this installation. Repair from the matching offline installer.");
    id path=value[@"path"];
    if(path==[NSNull null])return {};
    if(![path isKindOfClass:[NSString class]]||![path isAbsolutePath])throw std::runtime_error("The native file picker returned an invalid path.");
    const char* bytes=[path UTF8String];
    if(!bytes)throw std::runtime_error("The selected path cannot be represented as UTF-8.");
    std::string result(bytes,[path lengthOfBytesUsingEncoding:NSUTF8StringEncoding]);
    if(result.find('\0')!=std::string::npos)throw std::runtime_error("The selected path contains an invalid character.");
    return result;
}

std::string chooseNativePath(PickerKind kind) {@autoreleasepool {
    // Never run a nested AppKit panel inside a Resolve parameter callback.
    // Resolve can leave that panel's URL validation disabled. The same signed,
    // protected Manager app owns this short-lived, independent Cocoa loop.
    NSTask* task=[NSTask new];
    task.executableURL=[NSURL fileURLWithPath:@CKMAC_MANAGER_PATH "/Contents/MacOS/" CKMAC_MANAGER_NAME];
    task.arguments=@[kind==PickerKind::BakeFolder?@"--choose-bake-folder":@"--choose-bake-manifest"];
    task.environment=@{@"PATH":@"/usr/bin:/bin",@"HOME":NSHomeDirectory()};
    NSPipe* output=[NSPipe pipe];task.standardOutput=output;
    NSError* error=nil;
    if(![task launchAndReturnError:&error])throw std::runtime_error("Unable to open the native file picker. Repair the Manager app from the offline installer.");
    NSData* data=[output.fileHandleForReading readDataToEndOfFile];[task waitUntilExit];
    if(task.terminationStatus!=0)throw std::runtime_error("The native file picker closed unexpectedly. The previous bake is preserved; retry.");
    return parsePickerResponse(std::string(static_cast<const char*>(data.bytes),data.length));
}}
}
