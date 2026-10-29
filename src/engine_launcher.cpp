// The short-lived native launcher is reaped synchronously by its caller.
// The idle-bounded same-user engine is adopted/reaped by launchd on exit.
#include <cerrno>
#include <cstdio>
#include <sys/wait.h>
#include <unistd.h>
extern char** environ;
int main(int argc,char** argv){
    if(argc<3||getuid()==0||argv[1][0]!='/')return 64;
    pid_t first=fork();if(first<0)return 71;
    if(first==0){
        if(setsid()<0)_exit(71);
        pid_t worker=fork();if(worker<0)_exit(71);
        if(worker>0)_exit(0);
        execve(argv[1],argv+1,environ);_exit(72);
    }
    int status=0;while(waitpid(first,&status,0)<0){if(errno!=EINTR)return 71;}
    return WIFEXITED(status)?WEXITSTATUS(status):71;
}
