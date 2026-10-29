#define main ckmac_original_main
#include "../src/installer_tool.mm"
#undef main
int main(int argc,char** argv){@autoreleasepool{try{
 check(getuid()==0,"Use macOS Installer authorization");
 check(argc==2,"Expected a scoped qualification action");
 int barrier=open((root/"maintenance.lock").c_str(),O_RDWR|O_NOFOLLOW|O_CLOEXEC);
 struct stat st{};check(barrier>=0&&!fstat(barrier,&st)&&st.st_uid==0&&!(st.st_mode&0022),"Unsafe maintenance barrier");
 check(!flock(barrier,LOCK_EX|LOCK_NB),"Another maintenance action is active");
 drain();recover();
 NSDictionary* active=readJSON(root/"active.json");
 std::string build=[active[@"build_id"] UTF8String];
 check(build=="0.9.7-b1.027347b5a7e5","Qualification target generation changed");
 NSDictionary* manifest=readJSON(root/"install-manifest.json");
 verify(fs::path("/"),manifest[@"inventory"]);
 std::string operation=argv[1];
 if(operation=="break-doc"){
   auto target=root/"Maintenance/PERFORMANCE.md",backup=root/"Maintenance/PERFORMANCE.md.qa-original";
   check(fs::is_regular_file(target)&&!fs::is_symlink(target)&&!fs::exists(backup),"Unsafe or already changed repair fixture");
   auto transactionBackup=root/"Transactions/qa-interrupted-Maintenance";
   check(!fs::exists(transactionBackup),"Qualification recovery backup already exists");
   fs::create_directories(transactionBackup);
   fs::copy(root/"Maintenance",transactionBackup/"0",fs::copy_options::recursive|fs::copy_options::copy_symlinks);
   syncTree(transactionBackup);
   writeJSON(root/"transaction.json",@{@"state":@"backed_up",@"backup":@(transactionBackup.c_str()),@"destinations":@[@((root/"Maintenance").c_str())]});
   fs::rename(target,backup);syncPath(target.parent_path());
   puts("Prepared a real interrupted Maintenance-component transaction after a complete durable backup; only PERFORMANCE.md is missing. The next normal installer must recover the complete prior Maintenance component before activation.");
 }else if(operation=="cleanup-history"){
   for(const auto& item:fs::directory_iterator(root/"Runtime")){
     auto name=item.path().filename().string();
     if(name==build||name.rfind("0.9.",0)!=0)continue;
     struct stat child{};check(!lstat(item.path().c_str(),&child)&&child.st_uid==0&&S_ISDIR(child.st_mode)&&!(child.st_mode&0022),"Unsafe historical generation");
     fs::remove_all(item.path());
   }
   fs::remove_all(root/"Transactions");
   puts("Removed only inactive personal-beta runtimes and committed test rollback history; active runtime and models retained.");
 }else throw std::runtime_error("Unsupported qualification action");
 return 0;
 }catch(const std::exception& e){fprintf(stderr,"Qualification maintenance: %s\n",e.what());return 1;}}}
