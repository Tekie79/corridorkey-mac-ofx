#import <Foundation/Foundation.h>
#import <AppKit/AppKit.h>
#import <Security/Security.h>
#import <CommonCrypto/CommonDigest.h>
#include "ckmac/worker_manager.hpp"
#include <array>
#include <algorithm>
#include <arpa/inet.h>
#include <chrono>
#include <cmath>
#include <fcntl.h>
#include <poll.h>
#include <spawn.h>
#include <sys/file.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>

namespace ckmac {
namespace {
constexpr const char* manifestPath = "/Library/Application Support/HarvestPictures/CorridorKeyMac/active.json";
struct FD { int n=-1; ~FD(){if(n>=0)close(n);} };
void fail(const std::string& s) { throw std::runtime_error(s + " Open CorridorKey Mac Manager → Verify/Repair."); }
void safePath(const std::string& path, bool directory=false) {
    struct stat s{};
    if(lstat(path.c_str(),&s)||s.st_uid!=0||(s.st_mode&0022)||
       (directory?!S_ISDIR(s.st_mode):!S_ISREG(s.st_mode))) fail("Installed file is missing or has unsafe ownership: "+path);
}
NSDictionary* readManifest() {
    safePath("/Library/Application Support/HarvestPictures/CorridorKeyMac",true);
    safePath(manifestPath);
    NSData* data=[NSData dataWithContentsOfFile:@(manifestPath)];
    if(!data||data.length>1024*1024)fail("Invalid installation manifest.");
    id obj=[NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    if(![obj isKindOfClass:[NSDictionary class]]||[obj[@"protocol"] intValue]!=2)fail("Incompatible installation.");
    return obj;
}
std::string str(id value) {
    if(![value isKindOfClass:[NSString class]])fail("Invalid installed path or identity.");
    return [value UTF8String];
}
NSString* userCacheRoot(){
    NSUserDefaults* preferences=[[NSUserDefaults alloc] initWithSuiteName:@"org.harvestpictures.CorridorKeyMac"];
    NSString* chosen=[preferences stringForKey:@"CacheParent"];
    if(!chosen)return [NSSearchPathForDirectoriesInDomains(NSCachesDirectory,NSUserDomainMask,YES).firstObject stringByAppendingPathComponent:@"org.harvestpictures.CorridorKeyMac"];
    NSURL* parent=[NSURL fileURLWithPath:chosen isDirectory:YES];NSString* volume=nil;NSNumber* directory=nil;
    [parent getResourceValue:&volume forKey:NSURLVolumeUUIDStringKey error:nil];[parent getResourceValue:&directory forKey:NSURLIsDirectoryKey error:nil];
    if(!directory.boolValue||!volume||![volume isEqual:[preferences stringForKey:@"CacheVolumeUUID"]]||![[NSFileManager defaultManager] isWritableFileAtPath:chosen])fail("Selected cache volume is unavailable. Open Manager → Choose Cache Folder to reconnect or select another existing folder.");
    return [chosen stringByAppendingPathComponent:[NSString stringWithFormat:@"CorridorKey-hp-Cache-%u",getuid()]];
}
void transfer(int fd, void* bytes, size_t count, bool writing,
              const std::function<bool()>& cancel,int timeoutSeconds=1800) {
    auto end=std::chrono::steady_clock::now()+std::chrono::seconds(timeoutSeconds);
    auto* p=static_cast<unsigned char*>(bytes);
    while(count) {
        if(cancel&&cancel())throw Cancelled();
        if(std::chrono::steady_clock::now()>end)fail("GPU engine request timed out.");
        pollfd f{fd,short(writing?POLLOUT:POLLIN),0};
        int ready=poll(&f,1,100);
        if(ready<0&&errno==EINTR)continue;
        if(ready<0)fail("GPU engine socket poll failed.");
        if(!ready)continue;
        if(!(f.revents&f.events))fail("GPU engine disconnected.");
        ssize_t n=writing?send(fd,p,count,0):recv(fd,p,count,0);
        if(n<0&&(errno==EINTR||errno==EAGAIN))continue;
        if(n<=0)fail("GPU engine disconnected during a request.");
        p+=n;count-=size_t(n);
    }
}
std::string encode(NSDictionary* d) {
    NSData* b=[NSJSONSerialization dataWithJSONObject:d options:0 error:nil];
    if(!b)fail("Could not encode GPU request.");
    return std::string(static_cast<const char*>(b.bytes),b.length);
}
NSDictionary* profile(const Settings& s){return @{@"resolution":@(s.internalResolution),@"window":@(s.temporalWindow),@"memory_limit":@(s.memoryLimit),@"low_memory":@(s.lowMemory),@"internal_hint_quality":@(s.internalHintQuality),@"reference_index":@(s.referenceIndex)};}
void checkImageMetadata(const std::string& text,unsigned width,unsigned height) {
    id d=[NSJSONSerialization JSONObjectWithData:[NSData dataWithBytes:text.data() length:text.size()] options:0 error:nil];
    if(![d[@"width"] isKindOfClass:[NSNumber class]]||![d[@"height"] isKindOfClass:[NSNumber class]]||
       [d[@"width"] unsignedLongLongValue]!=width||[d[@"height"] unsignedLongLongValue]!=height||
       ![d[@"alpha"] isKindOfClass:[NSString class]]||![d[@"alpha"] isEqual:@"straight"])
        fail("Engine returned unexpected image geometry or alpha association.");
}
}
WorkerManager::WorkerManager(std::function<bool()> c,std::uint64_t generation,const std::string& owner):cancelled_(std::move(c)),generation_(generation){@autoreleasepool{session_=owner.empty()?str([NSUUID UUID].UUIDString):owner;}}
void openManager(){@autoreleasepool{if(![[NSWorkspace sharedWorkspace] openURL:[NSURL fileURLWithPath:@"/Applications/CorridorKey Mac Manager.app"]])fail("Cannot open CorridorKey Mac Manager.");}}
void openMaintenance(const std::string& action){@autoreleasepool{
    auto config=[NSWorkspaceOpenConfiguration configuration];config.activates=YES;
    NSURL* url=[NSURL URLWithString:[@"ckmachp://" stringByAppendingString:@(action.c_str())]];
    [[NSWorkspace sharedWorkspace] openURLs:@[url] withApplicationAtURL:[NSURL fileURLWithPath:@"/Applications/CorridorKey Mac Manager.app"] configuration:config completionHandler:^(NSRunningApplication* app,NSError* error){if(error)NSLog(@"Cannot open maintenance: %@",error.localizedDescription);}];
}}
std::string cacheDirectory(){@autoreleasepool{return str(userCacheRoot());}}
void revealCacheDirectory(){@autoreleasepool{
    NSString* root=userCacheRoot();[[NSFileManager defaultManager] createDirectoryAtPath:root withIntermediateDirectories:YES attributes:@{NSFilePosixPermissions:@0700} error:nil];
    if(![[NSWorkspace sharedWorkspace] openURL:[NSURL fileURLWithPath:root]])fail("Cannot open the selected cache folder.");
}}
void chooseCacheDirectory(){@autoreleasepool{
    NSOpenPanel* panel=[NSOpenPanel openPanel];panel.canChooseDirectories=YES;panel.canChooseFiles=NO;panel.canCreateDirectories=YES;
    panel.message=@"Choose an existing local folder for this user's cache. A private product subfolder is created. This applies to all hp beta nodes after the idle engine stops. Existing cached data is retained in its old folder.";
    if([panel runModal]!=NSModalResponseOK)return;
    NSString* volume=nil;[panel.URL getResourceValue:&volume forKey:NSURLVolumeUUIDStringKey error:nil];
    if(!volume||![[NSFileManager defaultManager] isWritableFileAtPath:panel.URL.path])fail("Choose an existing writable local volume.");
    NSDictionary* m=readManifest();std::string endpoint="/private/tmp/ckmac-"+std::to_string(getuid())+"/"+str(m[@"build_id"]).substr(0,32)+".sock";
    if([[NSFileManager defaultManager] fileExistsAtPath:@(endpoint.c_str())]){
        WorkerManager().control("{\"op\":\"release\"}");
        for(int i=0;i<50&&[[NSFileManager defaultManager] fileExistsAtPath:@(endpoint.c_str())];i++)std::this_thread::sleep_for(std::chrono::milliseconds(100));
        if([[NSFileManager defaultManager] fileExistsAtPath:@(endpoint.c_str())])fail("Engine did not finish stopping; cache choice was not changed.");
    }
    NSUserDefaults* preferences=[[NSUserDefaults alloc] initWithSuiteName:@"org.harvestpictures.CorridorKeyMac"];
    [preferences setObject:panel.URL.path forKey:@"CacheParent"];[preferences setObject:volume forKey:@"CacheVolumeUUID"];[preferences synchronize];
}}

std::string WorkerManager::ensure() {
 @autoreleasepool {
    NSDictionary* m=readManifest();
    safePath("/Library/Application Support/HarvestPictures/CorridorKeyMac/maintenance.lock");
    FD barrier;barrier.n=open("/Library/Application Support/HarvestPictures/CorridorKeyMac/maintenance.lock",O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    if(barrier.n<0||flock(barrier.n,LOCK_SH|LOCK_NB))fail("Maintenance is in progress. Retry after Installer completes.");
    build_=str(m[@"build_id"]);
    if(build_.empty()||build_.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-")!=std::string::npos)
        fail("Invalid runtime identity.");
    std::string root="/private/tmp/ckmac-"+std::to_string(getuid());
    if(mkdir(root.c_str(),0700)&&errno!=EEXIST)fail("Cannot create private GPU engine directory.");
    struct stat st{};
    if(lstat(root.c_str(),&st)||!S_ISDIR(st.st_mode)||st.st_uid!=getuid()||(st.st_mode&0077))fail("Unsafe engine directory.");
    endpoint_=root+"/"+build_.substr(0,32)+".sock";
    FD lock;lock.n=open((endpoint_+".startup").c_str(),O_CREAT|O_RDWR|O_NOFOLLOW|O_CLOEXEC,0600);
    if(lock.n<0||fstat(lock.n,&st)||!S_ISREG(st.st_mode)||st.st_uid!=getuid()||(st.st_mode&0077))fail("Unsafe startup lock.");
    auto deadline=std::chrono::steady_clock::now()+std::chrono::minutes(5);
    while(flock(lock.n,LOCK_EX|LOCK_NB)) {
        if(cancelled_&&cancelled_())throw Cancelled();
        if(std::chrono::steady_clock::now()>deadline)fail("Timed out waiting for engine startup.");
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    std::string tokenFile=endpoint_+".token";
    auto readToken=[&] {
        FD t;t.n=open(tokenFile.c_str(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
        if(t.n<0||fstat(t.n,&st)||!S_ISREG(st.st_mode)||st.st_uid!=getuid()||(st.st_mode&0077))return false;
        char b[65]{};if(read(t.n,b,65)!=64)return false;
        token_=std::string(b,64);return true;
    };
    auto alive=[&] {
        if(!readToken())return false;
        try { return !exchange("{\"op\":\"health\"}",nullptr,0).size(); } catch(const Cancelled&){throw;}catch(...){return false;}
    };
    if(alive())return endpoint_;
    FD lifetime;lifetime.n=open((endpoint_+".lock").c_str(),O_RDWR|O_CREAT|O_NOFOLLOW|O_CLOEXEC,0600);
    if(lifetime.n<0||fstat(lifetime.n,&st)||!S_ISREG(st.st_mode)||st.st_uid!=getuid()||(st.st_mode&0077))fail("Unsafe engine lifetime lock.");
    if(flock(lifetime.n,LOCK_EX|LOCK_NB))fail("A compatible engine process is still alive but unresponsive. No duplicate model process was started.");
    // Rate-limit crashes across nodes and host processes, under the startup
    // lock. Idle expiry is ten minutes, longer than this recovery window.
    std::string historyPath=endpoint_+".launches";
    FD history;history.n=open(historyPath.c_str(),O_RDWR|O_CREAT|O_NOFOLLOW|O_CLOEXEC,0600);
    if(history.n<0||fstat(history.n,&st)||!S_ISREG(st.st_mode)||st.st_uid!=getuid()||(st.st_mode&0077)||st.st_size>4096)fail("Unsafe engine recovery record.");
    std::string previous(size_t(st.st_size),'\0');if(!previous.empty()&&read(history.n,previous.data(),previous.size())!=ssize_t(previous.size()))fail("Cannot read engine recovery record.");
    NSArray* old=[NSJSONSerialization JSONObjectWithData:[NSData dataWithBytes:previous.data() length:previous.size()] options:0 error:nil];
    NSMutableArray* launches=[NSMutableArray array];double now=CFAbsoluteTimeGetCurrent();
    bool cleanExit=false;std::string cleanPath=endpoint_+".clean";FD clean;clean.n=open(cleanPath.c_str(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    if(clean.n>=0&&!fstat(clean.n,&st)&&S_ISREG(st.st_mode)&&st.st_uid==getuid()&&!(st.st_mode&0077)&&st.st_size==ssize_t(build_.size())){
        std::string value(build_.size(),'\0');cleanExit=read(clean.n,value.data(),value.size())==ssize_t(value.size())&&value==build_;
        if(cleanExit)unlink(cleanPath.c_str());
    }
    if(!cleanExit&&[old isKindOfClass:[NSArray class]])for(id value in old)if([value isKindOfClass:[NSNumber class]]&&now-[value doubleValue]<300&&now>=[value doubleValue])[launches addObject:value];
    if(launches.count>=3)fail("Repeated engine crashes stopped automatic recovery after two restarts. Verify/Repair the installation; automatic startup is available again after five minutes.");
    for(NSUInteger i=0;i<launches.count*5;i++){if(cancelled_&&cancelled_())throw Cancelled();std::this_thread::sleep_for(std::chrono::milliseconds(100));}
    [launches addObject:@(now)];
    NSData* record=[NSJSONSerialization dataWithJSONObject:launches options:0 error:nil];
    if(ftruncate(history.n,0)||lseek(history.n,0,SEEK_SET)<0||write(history.n,record.bytes,record.length)!=ssize_t(record.length)||fsync(history.n))fail("Cannot record bounded engine recovery.");
    flock(lifetime.n,LOCK_UN);
    // A live but incompatible peer is never replaced. Socket cleanup is done by
    // the worker under its independent lifetime lock.
    std::array<unsigned char,32> random{};
    if(SecRandomCopyBytes(kSecRandomDefault,random.size(),random.data()))fail("Cannot generate engine handshake.");
    static const char hex[]="0123456789abcdef";token_.clear();
    for(auto b:random){token_+=hex[b>>4];token_+=hex[b&15];}
    FD token;token.n=open(tokenFile.c_str(),O_CREAT|O_TRUNC|O_WRONLY|O_NOFOLLOW|O_CLOEXEC,0600);
    if(token.n<0||fstat(token.n,&st)||!S_ISREG(st.st_mode)||st.st_uid!=getuid()||(st.st_mode&0077)||write(token.n,token_.data(),64)!=64)
        fail("Cannot create private engine handshake.");
    std::string python=str(m[@"python"]);
    std::string expected="/Library/Application Support/HarvestPictures/CorridorKeyMac/Runtime/"+build_+"/";
    if(python.rfind(expected,0)!=0||python.find("..")!=std::string::npos)fail("Runtime path escapes the installation.");
    // python3 may be a relative symlink; validate the resolved executable.
    NSString* resolved=[[@(python.c_str()) stringByResolvingSymlinksInPath] stringByStandardizingPath];
    if(![resolved hasPrefix:@(expected.c_str())])fail("Interpreter symlink escapes runtime.");
    safePath(str(resolved));
    NSString* cache=userCacheRoot();
    [[NSFileManager defaultManager] createDirectoryAtPath:cache withIntermediateDirectories:YES attributes:@{NSFilePosixPermissions:@0700} error:nil];
    struct stat cacheStat{};if(lstat([cache fileSystemRepresentation],&cacheStat)||!S_ISDIR(cacheStat.st_mode)||cacheStat.st_uid!=getuid()||(cacheStat.st_mode&0077))fail("Unsafe user cache directory.");
    std::string launcher=expected+"bin/ckmac-engine-launcher";safePath(launcher);
    std::vector<std::string> args{launcher,python,"-I","-B","-m","ckmac.engine","--manifest",manifestPath,"--socket",endpoint_,"--token-file",tokenFile,"--verify-installation"};
    std::vector<std::string> env{"PATH=/usr/bin:/bin","HOME="+str(NSHomeDirectory()),"TMPDIR="+str(NSTemporaryDirectory()),
        "PYTORCH_ENABLE_MPS_FALLBACK=0","HF_HUB_OFFLINE=1","TRANSFORMERS_OFFLINE=1","XFORMERS_DISABLED=1",
        "PYTHONDONTWRITEBYTECODE=1","HF_HOME="+str(cache)+"/huggingface","TORCH_HOME="+str(cache)+"/torch"};
    std::vector<char*> av,ev;for(auto& a:args)av.push_back(a.data());av.push_back(nullptr);
    for(auto& e:env)ev.push_back(e.data());ev.push_back(nullptr);
    posix_spawn_file_actions_t actions;posix_spawn_file_actions_init(&actions);
    std::string log=str(cache)+"/engine.log";
    posix_spawn_file_actions_addopen(&actions,0,"/dev/null",O_RDONLY,0);
    posix_spawn_file_actions_addopen(&actions,1,log.c_str(),O_WRONLY|O_CREAT|O_APPEND,0600);
    posix_spawn_file_actions_adddup2(&actions,1,2);
    posix_spawnattr_t attr;posix_spawnattr_init(&attr);
    posix_spawnattr_setflags(&attr,POSIX_SPAWN_CLOEXEC_DEFAULT);
    pid_t child=0;int rc=posix_spawn(&child,launcher.c_str(),&actions,&attr,av.data(),ev.data());
    posix_spawnattr_destroy(&attr);posix_spawn_file_actions_destroy(&actions);
    if(rc)fail("Cannot launch the installed GPU engine.");
    int status=0;while(waitpid(child,&status,0)<0)if(errno!=EINTR)fail("Cannot reap GPU launcher.");
    if(!WIFEXITED(status)||WEXITSTATUS(status))fail("GPU launcher failed.");
    for(;;) {
        if(cancelled_&&cancelled_())throw Cancelled();
        if(alive())return endpoint_;
        if(std::chrono::steady_clock::now()>deadline)fail("GPU engine startup timed out.");
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
 }
}
std::vector<unsigned char> WorkerManager::exchange(const std::string& json,const void* data,size_t bytes,std::string* metadata) {
 @autoreleasepool {
    if(json.size()>65536||bytes>maxPixels*16)fail("Engine request exceeds bounds.");
    NSMutableDictionary* d=[[NSJSONSerialization JSONObjectWithData:[NSData dataWithBytes:json.data() length:json.size()] options:NSJSONReadingMutableContainers error:nil] mutableCopy];
    if(!d)fail("Invalid control request.");
    d[@"token"]=@(token_.c_str());d[@"build_id"]=@(build_.c_str());d[@"protocol"]=@2;d[@"payload_bytes"]=@(bytes);d[@"client_pid"]=@(getpid());
    d[@"session_id"]=@(session_.c_str());d[@"request_id"]=@(++request_);d[@"effect_generation"]=@(generation_);
    auto header=encode(d);if(header.size()>65536)fail("Control request is too large.");
    struct stat st{};if(lstat(endpoint_.c_str(),&st)||!S_ISSOCK(st.st_mode)||st.st_uid!=getuid()||(st.st_mode&0077))fail("GPU engine is not running.");
    FD fd;fd.n=socket(AF_UNIX,SOCK_STREAM,0);if(fd.n<0)fail("Cannot open engine socket.");
    int one=1;setsockopt(fd.n,SOL_SOCKET,SO_NOSIGPIPE,&one,sizeof(one));
    sockaddr_un address{};address.sun_family=AF_UNIX;
    if(endpoint_.size()>=sizeof(address.sun_path))fail("Engine socket path is too long.");
    strcpy(address.sun_path,endpoint_.c_str());
    fcntl(fd.n,F_SETFL,O_NONBLOCK);fcntl(fd.n,F_SETFD,FD_CLOEXEC);
    int connected=connect(fd.n,reinterpret_cast<sockaddr*>(&address),sizeof(address));
    if(connected&&errno!=EINPROGRESS&&errno!=EAGAIN)fail("Cannot connect to engine.");
    if(connected){
        auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(2);
        for(;;){
            if(cancelled_&&cancelled_())throw Cancelled();
            if(std::chrono::steady_clock::now()>deadline)fail("Engine connection timed out.");
            pollfd wait{fd.n,POLLOUT,0};int result=poll(&wait,1,100);
            if(result<0&&errno==EINTR)continue;
            if(result<0)fail("Engine connection failed.");if(!result)continue;
            int error=0;socklen_t length=sizeof(error);if(getsockopt(fd.n,SOL_SOCKET,SO_ERROR,&error,&length)||error)fail("Cannot connect to engine.");break;
        }
    }
    uid_t uid;gid_t gid;if(getpeereid(fd.n,&uid,&gid)||uid!=getuid())fail("Foreign engine peer.");
    int timeout=[d[@"op"] isEqual:@"health"]?2:1800;
    auto move=[&](void* p,size_t n,bool writing){transfer(fd.n,p,n,writing,cancelled_,timeout);};
    uint32_t size=htonl(uint32_t(header.size()));char magic[4]={'C','K','J','2'};
    move(magic,4,true);move(&size,4,true);
    move(header.data(),header.size(),true);
    if(bytes)move(const_cast<void*>(data),bytes,true);
    move(&size,4,false);size=ntohl(size);if(size>65536)fail("Invalid engine response size.");
    std::string answer(size,'\0');move(answer.data(),size,false);
    id response=[NSJSONSerialization JSONObjectWithData:[NSData dataWithBytes:answer.data() length:size] options:0 error:nil];
    if(![response isKindOfClass:[NSDictionary class]]||[response[@"protocol"] intValue]!=2||str(response[@"build_id"])!=build_)fail("Incompatible engine response.");
    if(![response[@"ok"] boolValue])fail(str(response[@"error"]));
    if(str(response[@"session_id"])!=session_||[response[@"request_id"] unsignedLongLongValue]!=request_||[response[@"effect_generation"] unsignedLongLongValue]!=generation_)fail("Stale or mismatched engine response.");
    auto count=[response[@"payload_bytes"] unsignedLongLongValue];
    if(count>maxPixels*16)fail("Engine image response exceeds bounds.");
    if(metadata)*metadata=answer;
    std::vector<unsigned char> result(count);if(count)move(result.data(),count,false);
    return result;
 }
}
std::string WorkerManager::status(){ensure();return control("{\"op\":\"health\"}");}
std::string WorkerManager::control(const std::string& json){if(endpoint_.empty())ensure();std::string m;exchange(json,nullptr,0,&m);return m;}
void WorkerManager::waitReady() {
 @autoreleasepool {
    auto deadline=std::chrono::steady_clock::now()+std::chrono::minutes(5);
    for(;;) {
        auto report=control("{\"op\":\"health\"}");
        id d=[NSJSONSerialization JSONObjectWithData:[NSData dataWithBytes:report.data() length:report.size()] options:0 error:nil];
        NSString* state=d[@"state"];
        if([state isEqual:@"ready"]||[state isEqual:@"processing"])return;
        if([state isEqual:@"error"])fail(str(d[@"error"]));
        if(cancelled_&&cancelled_())throw Cancelled();
        if(std::chrono::steady_clock::now()>deadline)fail("Model loading/self-check timed out.");
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
 }
}
std::vector<float> WorkerManager::infer(unsigned w,unsigned h,const std::vector<float>& pixels,const Settings& s) {
    if(checkedPayloadSize(w,h)!=pixels.size()*sizeof(float))fail("Invalid frame geometry.");
    ensure();
    @autoreleasepool {
      auto deadline=std::chrono::steady_clock::now()+std::chrono::minutes(5);
      for(;;) {
        auto report=control("{\"op\":\"health\"}");
        id d=[NSJSONSerialization JSONObjectWithData:[NSData dataWithBytes:report.data() length:report.size()] options:0 error:nil];
        NSString* state=d[@"state"];
        if([state isEqual:@"ready"]||[state isEqual:@"processing"])break;
        if([state isEqual:@"error"])fail(str(d[@"error"]));
        if(cancelled_&&cancelled_())throw Cancelled();
        if(std::chrono::steady_clock::now()>deadline)fail("Model loading/self-check timed out.");
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
      }
      auto json=encode(@{@"op":@"frame",@"width":@(w),@"height":@(h),@"input_space":@(s.inputSpace),
          @"hint":@(s.sourceAlphaHint),@"quality":@(s.hintQuality),@"despill":@(s.despillStrength),@"profile":profile(s)});
      std::string metadata;auto bytes=exchange(json,pixels.data(),pixels.size()*sizeof(float),&metadata);
      checkImageMetadata(metadata,w,h);
      if(bytes.size()!=pixels.size()*sizeof(float))fail("Wrong output dimensions.");
      std::vector<float> out(pixels.size());memcpy(out.data(),bytes.data(),bytes.size());
      for(size_t i=0;i<out.size();++i)if(!std::isfinite(out[i])||(i%4==3&&(out[i]<0||out[i]>1)))fail("Invalid engine image.");
      return out;
    }
}
std::string WorkerManager::stage(unsigned w,unsigned h,const std::vector<float>& pixels,bool reuse) {
    if(checkedPayloadSize(w,h)!=pixels.size()*sizeof(float))fail("Invalid temporal input geometry.");
    if(endpoint_.empty())ensure();
    @autoreleasepool {
        CC_SHA256_CTX hash;CC_SHA256_Init(&hash);uint32_t shape[]{htonl(w),htonl(h)};
        CC_SHA256_Update(&hash,shape,sizeof(shape));CC_SHA256_Update(&hash,pixels.data(),CC_LONG(pixels.size()*sizeof(float)));
        unsigned char digest[32];CC_SHA256_Final(digest,&hash);std::string key;const char* hex="0123456789abcdef";
        for(auto b:digest){key+=hex[b>>4];key+=hex[b&15];}
        auto lookup=control(encode(@{@"op":@"input_lookup",@"key":@(key.c_str())}));
        id d=[NSJSONSerialization JSONObjectWithData:[NSData dataWithBytes:lookup.data() length:lookup.size()] options:0 error:nil];
        if(!reuse||![d[@"present"] boolValue])exchange(encode(@{@"op":@"stage",@"key":@(key.c_str()),@"width":@(w),@"height":@(h)}),pixels.data(),pixels.size()*sizeof(float));
        return key;
    }
}
std::vector<float> WorkerManager::inferCaptured(unsigned w,unsigned h,const std::string& key,const Settings& s) {
    if(endpoint_.empty())ensure();waitReady();
    @autoreleasepool {
        auto json=encode(@{@"op":@"frame_cached",@"source_key":@(key.c_str()),@"width":@(w),@"height":@(h),@"input_space":@(s.inputSpace),
            @"hint":@(s.sourceAlphaHint),@"quality":@(s.hintQuality),@"despill":@(s.despillStrength),@"profile":profile(s)});
        std::string metadata;auto bytes=exchange(json,nullptr,0,&metadata);
        checkImageMetadata(metadata,w,h);
        if(bytes.size()!=checkedPayloadSize(w,h))fail("Wrong cached output dimensions.");
        std::vector<float> out(bytes.size()/4);memcpy(out.data(),bytes.data(),bytes.size());
        for(size_t i=0;i<out.size();i++)if(!std::isfinite(out[i])||(i%4==3&&(out[i]<0||out[i]>1)))fail("Invalid cached engine image.");
        return out;
    }
}
std::vector<std::string> WorkerManager::inputsPresent(const std::vector<std::string>& keys) {
    if(endpoint_.empty())ensure();
    @autoreleasepool {
        NSMutableArray* list=[NSMutableArray array];for(auto& k:keys)[list addObject:@(k.c_str())];
        auto response=control(encode(@{@"op":@"inputs_lookup",@"keys":list}));
        id d=[NSJSONSerialization JSONObjectWithData:[NSData dataWithBytes:response.data() length:response.size()] options:0 error:nil];
        if(![d[@"present"] isKindOfClass:[NSArray class]])fail("Invalid cached input response.");
        std::vector<std::string> found;for(NSString* key in d[@"present"])found.push_back(str(key));
        return found;
    }
}
std::vector<float> WorkerManager::temporal(unsigned w,unsigned h,const std::vector<std::string>& keys,unsigned requested,const Settings& s,int revision,bool firstHint,const std::string& provenance) {
    ensure();waitReady();
    @autoreleasepool {
        NSMutableArray* list=[NSMutableArray array];for(auto& k:keys)[list addObject:@(k.c_str())];
        id origin=[NSJSONSerialization JSONObjectWithData:[NSData dataWithBytes:provenance.data() length:provenance.size()] options:0 error:nil];
        if(![origin isKindOfClass:[NSDictionary class]])fail("Invalid temporal provenance.");
        std::string json=encode(@{@"op":@"temporal",@"width":@(w),@"height":@(h),@"keys":list,@"requested":@(requested),@"input_space":@(s.inputSpace),
            @"hint":@(s.sourceAlphaHint),@"quality":@(s.hintQuality),@"despill":@(s.despillStrength),@"revision":@(revision),@"first_hint":@(firstHint),@"provenance":origin,@"profile":profile(s)});
        std::string metadata;auto bytes=exchange(json,nullptr,0,&metadata);
        checkImageMetadata(metadata,w,h);
        if(bytes.size()!=checkedPayloadSize(w,h))fail("Wrong temporal output dimensions.");
        std::vector<float> result(bytes.size()/4);memcpy(result.data(),bytes.data(),bytes.size());
        for(size_t i=0;i<result.size();i++)if(!std::isfinite(result[i])||(i%4==3&&(result[i]<0||result[i]>1)))fail("Invalid temporal output.");
        return result;
    }
}
}
