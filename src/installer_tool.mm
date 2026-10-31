#import <Foundation/Foundation.h>
#import <CommonCrypto/CommonDigest.h>
#include "ckmac/installation.hpp"
#include <filesystem>
#include <fstream>
#include <sys/socket.h>
#include <sys/un.h>
#include <sys/stat.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <thread>
#include <chrono>
#include <sys/file.h>
#include <fcntl.h>
#include <signal.h>
namespace fs=std::filesystem;
#ifdef CKMAC_INSTALLER_SELF_TEST
static fs::path root,plugin,app;
#else
static const fs::path root=CKMAC_PRODUCT_ROOT;
static const fs::path plugin=CKMAC_PLUGIN_PATH;
static const fs::path app=CKMAC_MANAGER_PATH;
#endif
void check(bool b,const std::string& s){if(!b)throw std::runtime_error(s);}
std::string hashFile(const fs::path& p){
    CC_SHA256_CTX c;CC_SHA256_Init(&c);std::ifstream f(p,std::ios::binary);check(bool(f),"Cannot read "+p.string());
    char buf[1024*1024];while(f){f.read(buf,sizeof(buf));CC_SHA256_Update(&c,buf,CC_LONG(f.gcount()));}
    unsigned char digest[32];CC_SHA256_Final(digest,&c);std::string out;
    const char* hex="0123456789abcdef";for(auto b:digest){out+=hex[b>>4];out+=hex[b&15];}return out;
}
id readJSON(const fs::path& p){NSData* b=[NSData dataWithContentsOfFile:@(p.c_str())];id d=b?[NSJSONSerialization JSONObjectWithData:b options:NSJSONReadingMutableContainers error:nil]:nil;check(d!=nil,"Invalid JSON: "+p.string());return d;}
void syncPath(const fs::path& p){int fd=open(p.c_str(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC);check(fd>=0,"Cannot open for durability: "+p.string());int status=fsync(fd);close(fd);check(!status,"Cannot flush: "+p.string());}
void writeJSON(const fs::path& p,id obj){NSData* b=[NSJSONSerialization dataWithJSONObject:obj options:NSJSONWritingPrettyPrinted error:nil];check(b&&[b writeToFile:@(p.c_str()) options:NSDataWritingAtomic error:nil],"Cannot journal "+p.string());syncPath(p);syncPath(p.parent_path());}
void syncTree(const fs::path& p){
    if(fs::is_symlink(p))return;
    if(fs::is_directory(p)){for(const auto& item:fs::directory_iterator(p))syncTree(item.path());}
    syncPath(p);
}
void verify(const fs::path& tree,NSArray* files){
    for(NSDictionary* r in files){std::string rel=[r[@"path"] UTF8String];check(rel.size()&&rel[0]!='/'&&rel.find("..") == std::string::npos,"Unsafe staged path");fs::path p=tree/rel;
        if(r[@"symlink"]){check(fs::is_symlink(p)&&fs::read_symlink(p).string()==[r[@"symlink"] UTF8String],"Symlink mismatch: "+rel);}
        else check(fs::is_regular_file(p)&&!fs::is_symlink(p)&&fs::file_size(p)==[r[@"size"] unsignedLongLongValue]&&hashFile(p)==[r[@"sha256"] UTF8String],"Inventory mismatch: "+rel);
    }
}
void sendAll(int fd,const void* data,size_t n){auto p=static_cast<const char*>(data);while(n){auto r=send(fd,p,n,0);check(r>0,"Worker drain request failed");p+=r;n-=r;}}
void receiveAll(int fd,void* data,size_t n){auto p=static_cast<char*>(data);while(n){auto r=recv(fd,p,n,0);check(r>0,"Worker drain response failed");p+=r;n-=r;}}
bool engineDirectoryName(const std::string& name){const std::string prefix=CKMAC_SOCKET_PREFIX;return name.size()>prefix.size()&&name.rfind(prefix,0)==0&&name.find_first_not_of("0123456789",prefix.size())==std::string::npos;}
void drain(){
    for(const auto& dir:fs::directory_iterator("/private/tmp")){
        if(!dir.is_directory()||dir.is_symlink()||!engineDirectoryName(dir.path().filename().string()))continue;
        struct stat ds{};check(!lstat(dir.path().c_str(),&ds)&&!(ds.st_mode&0077),"Unsafe affected engine directory");
        check(dir.path().filename().string()==std::string(CKMAC_SOCKET_PREFIX)+std::to_string(ds.st_uid),"Engine owner mismatch");
        for(const auto& file:fs::directory_iterator(dir.path())){
            if(file.path().extension()!=".sock"||!fs::is_socket(file.symlink_status()))continue;
            struct stat ts{};auto tokenPath=file.path().string()+".token";
            check(!lstat(tokenPath.c_str(),&ts)&&S_ISREG(ts.st_mode)&&ts.st_uid==ds.st_uid&&!(ts.st_mode&0077)&&ts.st_size==64,"Unsafe engine authentication file; maintenance blocked");
            int token=open(tokenPath.c_str(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC);check(token>=0,"Cannot read engine authentication");char secretBytes[64];auto readCount=read(token,secretBytes,64);close(token);check(readCount==64,"Cannot authenticate affected worker; maintenance blocked");std::string secret(secretBytes,64);
            // Identity is the exact generation endpoint name, never a process-name kill.
            std::string build=file.path().stem();NSDictionary* req=@{@"op":@"release",@"protocol":@2,@"build_id":@(build.c_str()),@"token":@(secret.c_str()),@"payload_bytes":@0};
            NSData* b=[NSJSONSerialization dataWithJSONObject:req options:0 error:nil];
            int fd=socket(AF_UNIX,SOCK_STREAM,0);check(fd>=0,"Cannot contact worker");
            sockaddr_un a{};a.sun_family=AF_UNIX;strncpy(a.sun_path,file.path().c_str(),sizeof(a.sun_path)-1);
            timeval timeout{5,0};setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));int one=1;setsockopt(fd,SOL_SOCKET,SO_NOSIGPIPE,&one,sizeof(one));
            if(connect(fd,reinterpret_cast<sockaddr*>(&a),sizeof(a))){close(fd);check(errno==ECONNREFUSED,"Worker cannot be safely drained");continue;}
            uid_t peer;gid_t group;check(!getpeereid(fd,&peer,&group)&&peer==ds.st_uid,"Foreign engine peer; maintenance blocked");
            uint32_t n=htonl(uint32_t(b.length));sendAll(fd,"CKJ2",4);sendAll(fd,&n,4);sendAll(fd,b.bytes,b.length);
            receiveAll(fd,&n,4);n=ntohl(n);check(n>0&&n<=65536,"Invalid engine drain response");std::string reply(n,'\0');receiveAll(fd,reply.data(),n);close(fd);
            NSDictionary* response=[NSJSONSerialization JSONObjectWithData:[NSData dataWithBytes:reply.data() length:reply.size()] options:0 error:nil];
            check(response&&[response[@"ok"] boolValue]&&[response[@"state"] isEqual:@"stopping"],"Worker is active; maintenance blocked without changing installed files");
            pid_t pid=[response[@"pid"] intValue];check(pid>1,"Invalid affected worker identity");
            for(int i=0;i<100&&(fs::exists(file.path())||kill(pid,0)==0);i++)std::this_thread::sleep_for(std::chrono::milliseconds(100));
            check(!fs::exists(file.path())&&kill(pid,0)!=0&&errno==ESRCH,"Affected worker has not exited; maintenance blocked");
        }
    }
}
bool allowed(const fs::path& p){return p==plugin||p==app||p==root/"active.json"||p==root/"install-manifest.json"||p==root/"repair-policy.json"||p==root/"Maintenance"||p.parent_path()==root/"Runtime"||p.parent_path()==root/"Models";}
void recover(){
    fs::path j=root/"transaction.json";if(!fs::exists(j))return;
    NSDictionary* state=readJSON(j);if([state[@"state"] isEqual:@"committed"]||[state[@"state"] isEqual:@"rolled_back"])return;
    fs::path backup=[state[@"backup"] UTF8String];check(backup.parent_path()==root/"Transactions","Unsafe rollback path");
    if([state[@"state"] isEqual:@"preparing"]){
        // No live component has changed yet. A power loss can leave a partial
        // backup: it must NEVER replace the still-complete live generation.
        fs::remove_all(backup);
        writeJSON(j,@{@"state":@"rolled_back",@"backup":@(backup.c_str()),@"destinations":@[]});return;
    }
    check([state[@"state"] isEqual:@"backed_up"],"Unrecognized transaction state; leave installed files intact");
    NSArray* destinations=state[@"destinations"];
    check([destinations isKindOfClass:[NSArray class]],"Invalid rollback destinations");
    for(NSUInteger i=0;i<destinations.count;i++){
        fs::path live=[destinations[i] UTF8String];check(allowed(live),"Unsafe rollback destination");
        fs::path saved=backup/std::to_string(i),absent=backup/(std::to_string(i)+".absent");
        check(fs::exists(saved)||fs::is_regular_file(absent),"Incomplete committed backup; leave installed files intact");
    }
    for(NSUInteger i=0;i<destinations.count;i++){
        fs::path live=[destinations[i] UTF8String];check(allowed(live),"Unsafe rollback destination");
        fs::path saved=backup/std::to_string(i);
        if(fs::exists(saved)){fs::remove_all(live);fs::create_directories(live.parent_path());fs::copy(saved,live,fs::copy_options::recursive|fs::copy_options::copy_symlinks);syncTree(live);syncPath(live.parent_path());}
        else if(fs::exists(backup/(std::to_string(i)+".absent")))fs::remove_all(live);
    }
    writeJSON(j,@{@"state":@"rolled_back",@"backup":@(backup.c_str()),@"destinations":@[]});
}
#ifndef CKMAC_INSTALLER_SELF_TEST
int main(int argc,char** argv){@autoreleasepool{try{
    check(getuid()==0,"Use macOS Installer authorization for maintenance");
    check(argc>=3&&std::string(argv[2])=="/","Only the startup volume is supported");
    // Host state is checked again by package preflight before this tool runs.
    fs::create_directories(root);
    int barrier=open((root/"maintenance.lock").c_str(),O_RDWR|O_CREAT|O_NOFOLLOW|O_CLOEXEC,0644);struct stat bs{};
    check(barrier>=0&&!fstat(barrier,&bs)&&bs.st_uid==0&&S_ISREG(bs.st_mode)&&!(bs.st_mode&0022),"Unsafe maintenance lock");
    check(!flock(barrier,LOCK_EX|LOCK_NB),"Engine startup is in progress; retry maintenance shortly");
    drain();recover();
    std::string op=argv[1];
    if(op=="activate"){
        check(argc==4,"Missing staged generation");fs::path incoming=argv[3];check(incoming.parent_path()==root/"Incoming","Unsafe stage root");
        NSDictionary* manifest=readJSON(incoming/"install-manifest.json");
        check([(manifest[@"installation_profile"]?:@"personal") isEqual:@CKMAC_PROFILE],"Wrong installation profile");
        verify(incoming/"tree",manifest[@"inventory"]);
        NSString* build=manifest[@"build_id"];NSString* models=manifest[@"model_set_id"];
        NSArray* paths=@[@((root/"Runtime"/[build UTF8String]).c_str()),@((root/"Models"/[models UTF8String]).c_str()),@(plugin.c_str()),@(app.c_str()),@((root/"Maintenance").c_str()),@((root/"active.json").c_str()),@((root/"install-manifest.json").c_str()),@((root/"repair-policy.json").c_str())];
        fs::path backup=root/"Transactions"/[[NSUUID UUID].UUIDString UTF8String];fs::create_directories(backup);
        writeJSON(root/"transaction.json",@{@"state":@"preparing",@"backup":@(backup.c_str()),@"destinations":paths});
        try{
            // Every live replacement has a completed backup before any activation.
            for(NSUInteger i=0;i<paths.count;i++){
                fs::path live=[paths[i] UTF8String];check(allowed(live),"Unsafe activation path");
                if(fs::exists(live))fs::copy(live,backup/std::to_string(i),fs::copy_options::recursive|fs::copy_options::copy_symlinks);
                else std::ofstream(backup/(std::to_string(i)+".absent"));
            }
            syncTree(backup);
            writeJSON(root/"transaction.json",@{@"state":@"backed_up",@"backup":@(backup.c_str()),@"destinations":paths});
            for(NSUInteger i=0;i<paths.count;i++){
                fs::path live=[paths[i] UTF8String];fs::path staged=incoming/"tree"/live.relative_path();
                check(fs::exists(staged),"Staged component missing: "+staged.string());
                fs::remove_all(live);fs::create_directories(live.parent_path());fs::rename(staged,live);
                syncPath(live.parent_path());
            }
            writeJSON(root/"transaction.json",@{@"state":@"committed",@"backup":@(backup.c_str()),@"destinations":paths});
            fs::remove_all(incoming);
        }catch(...){recover();throw;}
    }else if(op=="uninstall-keep"||op=="uninstall-all"){
        fs::remove_all(plugin);fs::remove_all(app);
        fs::remove_all(root/"Runtime");fs::remove_all(root/"Incoming");fs::remove_all(root/"Transactions");
        fs::remove(root/"active.json");fs::remove(root/"install-manifest.json");fs::remove(root/"repair-policy.json");fs::remove(root/"transaction.json");
        fs::remove_all(root/"Maintenance");if(op=="uninstall-all")fs::remove_all(root/"Models");
    }else throw std::runtime_error("Unknown maintenance operation");
    return 0;
}catch(const std::exception& e){fprintf(stderr,"CorridorKey Mac: %s\n",e.what());return 1;}}}
#else
// Same production recovery functions, native filesystem fixtures, no root or
// live product paths. This executable is never put in the installer.
int main(){@autoreleasepool{fs::path base;try{
    check(engineDirectoryName(CKMAC_SOCKET_PREFIX "501")&&engineDirectoryName(CKMAC_SOCKET_PREFIX "123456")&&!engineDirectoryName("ckmac-native-qualification")&&!engineDirectoryName(CKMAC_SOCKET_PREFIX)&&!engineDirectoryName(CKMAC_SOCKET_PREFIX "501-extra"),"Affected engine directory matching is too broad");
#ifdef CKMAC_QA_PROFILE
    check(!engineDirectoryName("ckmac-501"),"QA maintenance must never drain production workers");
#else
    check(!engineDirectoryName("ckmac-qa-501"),"Production maintenance must never drain QA workers");
#endif
    char temp[]="/private/tmp/ckmac-transaction-test-XXXXXX";check(mkdtemp(temp),"Cannot make transaction fixture");base=temp;
    root=base/"Product";plugin=base/"OFX/Personal.ofx.bundle";app=base/"Applications/Personal.app";
    auto write=[](const fs::path& path,const std::string& text){fs::create_directories(path.parent_path());std::ofstream file(path);file<<text;file.close();};
    auto contents=[](const fs::path& path){std::ifstream file(path);return std::string(std::istreambuf_iterator<char>(file),{});};
    fs::path runtime=root/"Runtime/old",backup=root/"Transactions/test";
    fs::create_directories(backup);write(plugin/"payload","old-plugin");write(app/"payload","old-app");write(runtime/"payload","old-runtime");
    NSArray* destinations=@[@(plugin.c_str()),@(app.c_str()),@(runtime.c_str())];
    auto journal=[&](NSString* state,NSArray* paths){writeJSON(root/"transaction.json",@{@"state":state,@"backup":@(backup.c_str()),@"destinations":paths});};
    write(backup/"0/payload","partial-backup");journal(@"preparing",destinations);recover();
    check(contents(plugin/"payload")=="old-plugin"&&contents(app/"payload")=="old-app"&&contents(runtime/"payload")=="old-runtime","Partial backup replaced a live component");
    fs::create_directories(backup);fs::copy(plugin,backup/"0",fs::copy_options::recursive);fs::copy(app,backup/"1",fs::copy_options::recursive);fs::copy(runtime,backup/"2",fs::copy_options::recursive);
    journal(@"backed_up",destinations);write(plugin/"payload","new-plugin");fs::remove_all(app);write(runtime/"payload","new-runtime");recover();
    check(contents(plugin/"payload")=="old-plugin"&&contents(app/"payload")=="old-app"&&contents(runtime/"payload")=="old-runtime","Incomplete activation did not restore all components");
    check(fs::exists(backup/"0/payload")&&fs::exists(backup/"1/payload"),"Recovery consumed its own crash-recovery data");
    journal(@"backed_up",destinations);fs::remove_all(plugin);fs::create_directories(plugin);write(plugin/"partial","interrupted-restore");recover();
    check(contents(plugin/"payload")=="old-plugin"&&!fs::exists(plugin/"partial"),"Interrupted recovery was not repeatable");
    auto fresh=root/"Runtime/new";write(backup/"3.absent","");write(fresh/"payload","new-only");
    NSArray* withFresh=@[@(plugin.c_str()),@(app.c_str()),@(runtime.c_str()),@(fresh.c_str())];journal(@"backed_up",withFresh);recover();check(!fs::exists(fresh),"Originally absent generation was not removed");
    write(plugin/"payload","committed-new");journal(@"committed",destinations);recover();check(contents(plugin/"payload")=="committed-new","Committed activation was reverted");
    journal(@"backed_up",@[@(plugin.c_str()),@((base/"unrelated").c_str())]);bool rejected=false;try{recover();}catch(...){rejected=true;}check(rejected&&contents(plugin/"payload")=="committed-new","Unsafe journal caused partial restoration");
    fs::remove_all(base);puts("installer_transactions: partial backups, partial activation, repeated recovery, absent components, committed state and scope guards passed");return 0;
}catch(const std::exception& e){if(!base.empty())fs::remove_all(base);fprintf(stderr,"transaction test: %s\n",e.what());return 1;}}}
#endif
