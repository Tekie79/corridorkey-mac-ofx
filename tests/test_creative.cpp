#include "ckmac/creative.hpp"
#include <cmath>
#include <iostream>
#include <stdexcept>
void near(float x,float y){if(std::abs(x-y)>2e-6)throw std::runtime_error("Incorrect output math");}
int main(){try{
    using namespace ckmac;
    std::vector<float> source{.2F,.8F,.4F,1},raw{.2F,.8F,.4F,.25F};
    PostSettings p;p.screen=1;p.despill=1;
    auto out=raw;applyPost(out,source,p);near(out[0],.45F);near(out[1],.3F);near(out[2],.65F);near(out[3],.25F);
    p.method=1;out=raw;applyPost(out,source,p);near(out[0],.4F);near(out[1],.4F);near(out[2],.6F);
    source={.2F,.4F,.8F,1};raw={.2F,.4F,.8F,.25F};p.screen=2;p.method=0;out=raw;applyPost(out,source,p);near(out[0],.45F);near(out[1],.65F);near(out[2],.3F);
    p.despill=0;p.whitePoint=.5;out=raw;applyPost(out,source,p);near(out[0],raw[0]);near(out[3],.5F);
    p.whitePoint=1;p.inputSpace=1;p.recoverDetails=true;source={-2,16,.5F,1};raw={.1F,.2F,.3F,.96F};out=raw;applyPost(out,source,p);near(out[0],-2);near(out[1],16);near(out[3],.96F);
    p.recoverDetails=false;p.inputSpace=0;p.linearize=true;source=raw={.04045F,.5F,1.F,.5F};out=raw;applyPost(out,source,p);near(out[0],.0031308F);near(out[1],.21404114F);near(out[2],1);near(out[3],.5F);
    auto colour=detectScreen({0,0,1,1, 1,0,0,1},{0,0,0,0, 0,0,0,1});near(colour[2],1);near(colour[0],0);
    auto linearColour=detectScreen({.01F,.25F,.04F,1},{0,0,0,0},1);
    auto displayColour=detectScreen({.0998528227F,.5370987305F,.2209163625F,1},{0,0,0,0},0);
    for(int c=0;c<3;c++)near(float(linearColour[c]),float(displayColour[c]));
    std::cout<<"creative: green/blue despill, light transfer, HDR recovery and alpha association passed\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
