#include "ckmac/worker_manager.hpp"
#include <atomic>
#include <thread>
#include <fstream>
#include <iostream>
#include <cmath>
#include <exception>
#include <array>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <unistd.h>
#include <cerrno>
#include <chrono>
int main(int argc,char** argv){try{
 int sock=socket(AF_INET,SOCK_STREAM,0);fcntl(sock,F_SETFL,O_NONBLOCK);sockaddr_in address{};address.sin_family=AF_INET;address.sin_port=htons(443);inet_pton(AF_INET,"1.1.1.1",&address.sin_addr);int rc=connect(sock,reinterpret_cast<sockaddr*>(&address),sizeof(address));int netError=errno;close(sock);if(rc==0||(netError!=EPERM&&netError!=EACCES))throw std::runtime_error("OS outbound IP denial was not active");
 if(argc!=2)throw std::runtime_error("Need owned real-footage float fixture");
 std::vector<float> input(256*144*4);std::ifstream f(argv[1],std::ios::binary);f.read(reinterpret_cast<char*>(input.data()),input.size()*sizeof(float));if(!f)throw std::runtime_error("Fixture read failed");
 std::array<std::vector<float>,2> output;std::array<std::string,2> health;std::array<std::exception_ptr,2> errors;
 std::atomic<int> ready{0};std::atomic<bool> go{false};std::array<std::thread,2> threads;
 for(int i=0;i<2;i++)threads[i]=std::thread([&,i]{ready.fetch_add(1);while(!go.load())std::this_thread::yield();try{
  ckmac::WorkerManager c({},i+1,"qualification-cold-client-"+std::to_string(i));ckmac::Settings settings{0,false,.75,0};
  output[i]=c.infer(256,144,input,settings);health[i]=c.status();
 }catch(...){errors[i]=std::current_exception();}});
 while(ready.load()!=2)std::this_thread::yield();go.store(true);for(auto& t:threads)t.join();for(auto e:errors)if(e)std::rethrow_exception(e);
 if(output[0].size()!=input.size()||output[1].size()!=input.size())throw std::runtime_error("Wrong output extent");
 double maximum=0;for(size_t i=0;i<input.size();i++){if(!std::isfinite(output[0][i])||!std::isfinite(output[1][i]))throw std::runtime_error("Non-finite output");maximum=std::max(maximum,double(std::abs(output[0][i]-output[1][i])));}
 if(maximum!=0)throw std::runtime_error("Shared inference results differ");
 ckmac::WorkerManager a({},1,"qualification-cold-client-0"),b({},2,"qualification-cold-client-1");bool cleared=false;for(int attempt=0;attempt<600&&!cleared;attempt++){try{a.control("{\"op\":\"clear_shot\"}");cleared=true;}catch(const std::exception& e){if(std::string(e.what()).find("GPU work is active")==std::string::npos&&std::string(e.what()).find("active processing")==std::string::npos)throw;std::this_thread::sleep_for(std::chrono::milliseconds(100));}}if(!cleared)throw std::runtime_error("Peer work did not become idle");ckmac::Settings settings{0,false,.75,0};auto retained=b.infer(256,144,input,settings);if(retained!=output[1])throw std::runtime_error("Clearing peer destroyed shared result");
 std::cout<<"{\"status\":\"Passed\",\"outbound_ip_denied\":true,\"simultaneous_native_clients\":2,\"maximum_output_error\":"<<maximum<<",\"shared_result_survives_other_owner_clear\":true,\"health\":["<<health[0]<<","<<health[1]<<"],\"after_shared_clear\":"<<b.status()<<"}\n";
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
