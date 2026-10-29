#import <Cocoa/Cocoa.h>
#include "ckmac/worker_manager.hpp"

@interface Manager : NSObject <NSApplicationDelegate>
@property NSWindow* window;
@property NSTextView* text;
@end
@implementation Manager
- (void)applicationDidFinishLaunching:(NSNotification*)n {
    self.window=[[NSWindow alloc] initWithContentRect:NSMakeRect(0,0,700,490) styleMask:NSWindowStyleMaskTitled|NSWindowStyleMaskClosable|NSWindowStyleMaskMiniaturizable backing:NSBackingStoreBuffered defer:NO];
    self.window.title=@"CorridorKey2.0 hp beta Manager";
    [self.window center];
    NSArray* labels=@[@"Verify",@"GPU status",@"Release GPU",@"Repair…",@"Keep Models",@"Remove All",@"Storage",@"Open Cache",@"Choose Cache…",@"Support File",@"User Guide",@"Notices"];
    NSArray* actions=@[NSStringFromSelector(@selector(verify:)),NSStringFromSelector(@selector(status:)),NSStringFromSelector(@selector(releaseGPU:)),NSStringFromSelector(@selector(repair:)),NSStringFromSelector(@selector(keep:)),NSStringFromSelector(@selector(remove:)),NSStringFromSelector(@selector(storage:)),NSStringFromSelector(@selector(openCache:)),NSStringFromSelector(@selector(chooseCache:)),NSStringFromSelector(@selector(diagnostics:)),NSStringFromSelector(@selector(help:)),NSStringFromSelector(@selector(notices:))];
    for(NSUInteger i=0;i<labels.count;i++) {
        NSButton* b=[NSButton buttonWithTitle:labels[i] target:self action:NSSelectorFromString(actions[i])];
        b.frame=NSMakeRect(12+(i%6)*114,445-(i/6)*36,110,30);[self.window.contentView addSubview:b];
    }
    NSScrollView* scroll=[[NSScrollView alloc] initWithFrame:NSMakeRect(16,16,668,374)];
    self.text=[[NSTextView alloc] initWithFrame:scroll.bounds];self.text.editable=NO;
    self.text.font=[NSFont systemFontOfSize:13];scroll.documentView=self.text;scroll.hasVerticalScroller=YES;
    [self.window.contentView addSubview:scroll];
    self.text.string=@"Personal beta — native workflow qualification is incomplete.\n\nNormal editing starts the GPU engine automatically.\n\nVerify checks installed files. Repair locates and validates your offline installer. Uninstall options open a scoped removal package and require normal macOS authorization. Keep Models retains the shared model set.\n\nDo not use this beta for irreplaceable work until the qualification report passes.";
    [self.window makeKeyAndOrderFront:nil];[NSApp activateIgnoringOtherApps:YES];
}
- (void)runMaintenance:(NSString*)command package:(NSString*)package {
    self.text.string=@"Checking…";
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{
        @autoreleasepool {
            NSString* root=@"/Library/Application Support/HarvestPictures/CorridorKeyMac";
            NSData* data=[NSData dataWithContentsOfFile:[root stringByAppendingPathComponent:@"active.json"]];
            NSDictionary* m=data?[NSJSONSerialization JSONObjectWithData:data options:0 error:nil]:nil;
            if(!m){dispatch_async(dispatch_get_main_queue(),^{self.text.string=@"Installation manifest is missing. Open your original offline installer to repair.";});return;}
            NSTask* task=[NSTask new];task.executableURL=[NSURL fileURLWithPath:m[@"python"]];
            NSMutableArray* args=[@[@"-I",@"-B",@"-m",@"ckmac.maintenance",command] mutableCopy];
            if(package)[args addObjectsFromArray:@[@"--package",package]];
            try{[args addObjectsFromArray:@[@"--cache-root",@(ckmac::cacheDirectory().c_str())]];}catch(const std::exception& e){NSString* failure=@(e.what());dispatch_async(dispatch_get_main_queue(),^{self.text.string=failure;});return;}
            task.arguments=args;task.environment=@{@"PATH":@"/usr/bin:/bin",@"HOME":NSHomeDirectory(),@"PYTHONDONTWRITEBYTECODE":@"1"};
            NSPipe* pipe=[NSPipe pipe];task.standardOutput=pipe;task.standardError=pipe;
            NSError* error=nil;BOOL launched=[task launchAndReturnError:&error];
            NSString* output=launched?[[NSString alloc] initWithData:[pipe.fileHandleForReading readDataToEndOfFile] encoding:NSUTF8StringEncoding]:error.localizedDescription;
            if(launched)[task waitUntilExit];
            BOOL ok=launched&&task.terminationStatus==0;
            dispatch_async(dispatch_get_main_queue(),^{self.text.string=output?:@"No diagnostic output";if(ok&&package)[[NSWorkspace sharedWorkspace] openURL:[NSURL fileURLWithPath:package]];});
        }
    });
}
- (void)verify:(id)s {[self runMaintenance:@"verify" package:nil];}
- (void)storage:(id)s {[self runMaintenance:@"storage" package:nil];}
- (void)openCache:(id)s {try{ckmac::revealCacheDirectory();self.text.string=@(ckmac::cacheDirectory().c_str());}catch(const std::exception& e){self.text.string=@(e.what());}}
- (void)chooseCache:(id)s {try{ckmac::chooseCacheDirectory();self.text.string=[NSString stringWithFormat:@"Cache location: %@\nExisting files were retained. Active renders must finish before an engine can be drained.",@(ckmac::cacheDirectory().c_str())];}catch(const std::exception& e){self.text.string=@(e.what());}}
- (void)diagnostics:(id)s {[self runMaintenance:@"diagnostics" package:nil];}
- (void)help:(id)s {
    NSString* path=@"/Library/Application Support/HarvestPictures/CorridorKeyMac/Maintenance/USER_GUIDE.md";
    if(![[NSWorkspace sharedWorkspace] openURL:[NSURL fileURLWithPath:path]])self.text.string=@"The installed guide is missing. Repair from the offline package.";
}
- (void)notices:(id)s {
    NSData* data=[NSData dataWithContentsOfFile:@"/Library/Application Support/HarvestPictures/CorridorKeyMac/active.json"];
    NSDictionary* m=data?[NSJSONSerialization JSONObjectWithData:data options:0 error:nil]:nil;
    if(m)[[NSWorkspace sharedWorkspace] openURL:[NSURL fileURLWithPath:[m[@"code_root"] stringByAppendingPathComponent:@"THIRD_PARTY_NOTICES.md"]]];
}
- (void)application:(NSApplication*)application openURLs:(NSArray<NSURL*>*)urls {
    for(NSURL* url in urls){
        if(![url.scheme isEqual:@"ckmachp"])continue;
        if([url.host isEqual:@"openCacheFolder"])[self openCache:nil];
        else if([url.host isEqual:@"chooseRenderFolder"])[self chooseCache:nil];
        else if([url.host isEqual:@"collectDiagnostics"])[self diagnostics:nil];
        else if([url.host isEqual:@"startGuidedHelp"])[self help:nil];
        else if([url.host isEqual:@"checkUpdates"])[self repair:nil];
    }
}
- (void)status:(id)s {
    self.text.string=@"Preparing GPU engine…";
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{
        std::string answer;try{answer=ckmac::WorkerManager().status();}catch(const std::exception& e){answer=e.what();}
        NSString* value=@(answer.c_str());dispatch_async(dispatch_get_main_queue(),^{self.text.string=value;});
    });
}
- (void)releaseGPU:(id)s {
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^{
        std::string answer;try{answer=ckmac::WorkerManager().control("{\"op\":\"release\"}");}catch(const std::exception& e){answer=e.what();}
        NSString* value=@(answer.c_str());dispatch_async(dispatch_get_main_queue(),^{self.text.string=value;});
    });
}
- (void)repair:(id)s {
    NSOpenPanel* p=[NSOpenPanel openPanel];p.allowedFileTypes=@[@"pkg"];p.canChooseDirectories=NO;
    p.message=@"Locate the matching offline installer. Its complete contents and executable hooks will be verified before opening Installer.";
    if([p runModal]==NSModalResponseOK)[self runMaintenance:@"validate-repair" package:p.URL.path];
}
- (void)uninstall:(NSString*)kind {
    NSString* path=[@"/Library/Application Support/HarvestPictures/CorridorKeyMac/Maintenance" stringByAppendingPathComponent:[NSString stringWithFormat:@"CorridorKeyMac-Uninstall-%@.pkg",kind]];
    [self runMaintenance:@"validate-uninstall" package:path];
}
- (void)keep:(id)s {[self uninstall:@"KeepModels"];}
- (void)remove:(id)s {[self uninstall:@"RemoveAll"];}
- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication*)sender{return YES;}
@end
int main(){@autoreleasepool{NSApplication* app=[NSApplication sharedApplication];Manager* m=[Manager new];app.delegate=m;[app setActivationPolicy:NSApplicationActivationPolicyRegular];[app run];}return 0;}
