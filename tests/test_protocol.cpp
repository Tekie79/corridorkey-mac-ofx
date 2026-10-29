#include "ckmac/protocol.hpp"
#include <array>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <cstring>
#include <functional>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <thread>
#include <unistd.h>

namespace {
void check(bool ok, const char* why) { if (!ok) throw std::runtime_error(why); }
void put32(unsigned char* p, std::uint32_t x) { p[0]=x>>24; p[1]=x>>16; p[2]=x>>8; p[3]=x; }
std::uint32_t get32(const unsigned char* p) { return (std::uint32_t(p[0])<<24)|(std::uint32_t(p[1])<<16)|(std::uint32_t(p[2])<<8)|p[3]; }
void readAll(int fd, unsigned char* p, std::size_t n) {
    while (n) { auto done=::recv(fd,p,n,0); if(done<=0) throw std::runtime_error("Mock read failed"); p+=done; n-=done; }
}
void sendAll(int fd, const unsigned char* p, std::size_t n) {
    while (n) {
#ifdef MSG_NOSIGNAL
        auto done=::send(fd,p,std::min<std::size_t>(7,n),MSG_NOSIGNAL);
#else
        auto done=::send(fd,p,std::min<std::size_t>(7,n),0);
#endif
        if(done<=0) throw std::runtime_error("Mock send failed"); p+=done; n-=done;
    }
}
struct Mock {
    std::string dir, path;
    int listener=-1;
    std::thread thread;
    std::exception_ptr failure;
    explicit Mock(std::function<void(int,const std::array<unsigned char,40>&,const std::vector<unsigned char>&)> respond) {
        char buffer[]="/tmp/ckmac-test-XXXXXX";
        auto made=::mkdtemp(buffer); check(made,"mkdtemp failed"); dir=made; path=dir+"/worker.sock";
        listener=::socket(AF_UNIX,SOCK_STREAM,0); check(listener>=0,"socket failed");
        sockaddr_un address{}; address.sun_family=AF_UNIX; std::memcpy(address.sun_path,path.c_str(),path.size()+1);
        check(::bind(listener,reinterpret_cast<sockaddr*>(&address),sizeof(address))==0,"bind failed");
        ::chmod(path.c_str(),0600); check(::listen(listener,1)==0,"listen failed");
        thread=std::thread([this,respond] {
            int fd=::accept(listener,nullptr,nullptr);
            try {
                check(fd>=0,"accept failed");
#ifdef SO_NOSIGPIPE
                int flag=1; ::setsockopt(fd,SOL_SOCKET,SO_NOSIGPIPE,&flag,sizeof(flag));
#endif
                std::array<unsigned char,40> header{}; readAll(fd,header.data(),header.size());
                check(!std::memcmp(header.data(),"CKM1",4) && get32(header.data()+4)==1,"Wrong request magic/version");
                auto size=get32(header.data()+20); check(size<1024,"Unexpected test payload length");
                std::vector<unsigned char> body(size); if(size) readAll(fd,body.data(),size);
                respond(fd,header,body);
            } catch (...) { failure=std::current_exception(); }
            if(fd>=0) ::close(fd);
        });
    }
    void finish() { if(thread.joinable()) thread.join(); if(failure) std::rethrow_exception(failure); }
    ~Mock() { if(thread.joinable()) thread.join(); if(listener>=0) ::close(listener); ::unlink(path.c_str()); ::rmdir(dir.c_str()); }
};
void reply(int fd, std::uint32_t status, std::uint32_t width, std::uint32_t height,
           const unsigned char* body, std::uint32_t size) {
    std::array<unsigned char,32> header{}; std::memcpy(header.data(),"CKR1",4);
    put32(header.data()+4,1); put32(header.data()+8,status); put32(header.data()+12,width);
    put32(header.data()+16,height); put32(header.data()+20,size);
    sendAll(fd,header.data(),header.size()); if(body&&size) sendAll(fd,body,size);
}
template<class F> void rejects(F function, const char* text) {
    try { function(); } catch(const std::runtime_error& error) {
        check(std::string(error.what()).find(text)!=std::string::npos,"Wrong diagnostic for rejected response"); return;
    } throw std::runtime_error("Expected failure");
}
}
int main() {
    try {
        std::vector<float> pixel{0.4F,0.2F,0.1F,0.5F};
        {
            Mock server([](int fd,const auto& h,const auto& body) {
                check(get32(h.data()+8)==1 && get32(h.data()+12)==1 && get32(h.data()+16)==1,"Request dimensions/op mismatch");
                check(get32(h.data()+24)==6 && get32(h.data()+28)==750 && get32(h.data()+32)==125 && get32(h.data()+36)==0,"Settings wire mismatch");
                reply(fd,0,1,1,body.data(),static_cast<std::uint32_t>(body.size()));
            });
            auto out=ckmac::Client(server.path).infer(1,1,pixel,{2,true,0.75,0.125});
            check(out==pixel,"Pixel payload changed in transport"); server.finish();
        }
        {
            Mock server([](int fd,const auto& h,const auto& body) {
                check(get32(h.data()+8)==2 && body.empty(),"Wrong health request");
                for(int offset=12;offset<40;offset+=4) check(get32(h.data()+offset)==0,"Health reserved fields are not zero");
                const std::string info="{\"device\":\"mps\"}";
                reply(fd,0,0,0,reinterpret_cast<const unsigned char*>(info.data()),info.size());
            });
            check(ckmac::Client(server.path).health()=="{\"device\":\"mps\"}","Health response changed"); server.finish();
        }
        {
            Mock server([](int fd,const auto&,const auto&) {
                const std::string message="MPS unavailable";
                reply(fd,4,0,0,reinterpret_cast<const unsigned char*>(message.data()),message.size());
            });
            rejects([&]{ckmac::Client(server.path).infer(1,1,pixel,{});},"MPS unavailable"); server.finish();
        }
        {
            Mock server([](int fd,const auto&,const auto&) { reply(fd,0,8192,8192,nullptr,0xffffffffU); });
            rejects([&]{ckmac::Client(server.path).infer(1,1,pixel,{});},"incorrect dimensions"); server.finish();
        }
        {
            Mock server([](int fd,const auto&,const auto& body) {
                auto bytes=body; float invalid=std::numeric_limits<float>::quiet_NaN(); std::memcpy(bytes.data(),&invalid,4);
                reply(fd,0,1,1,bytes.data(),bytes.size());
            });
            rejects([&]{ckmac::Client(server.path).infer(1,1,pixel,{});},"non-finite"); server.finish();
        }
        rejects([]{ckmac::checkedPayloadSize(8192,8192);},"Unsupported frame dimensions");
        rejects([&]{ckmac::Client("/not/running.sock").infer(1,1,pixel,{});},"worker is not running");
        std::cout << "protocol: fragmented I/O, settings, health, model errors, hostile sizes and non-finite results passed\n";
        return 0;
    } catch(const std::exception& error) { std::cerr<<error.what()<<'\n'; return 1; }
}
