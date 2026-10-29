#include "ckmac/creative.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>
namespace ckmac {
namespace {
double decode(double x,int space){double a=std::abs(x);return space==1?x:std::copysign(space==2?std::pow(a,2.4):(a<=.04045?a/12.92:std::pow((a+.055)/1.055,2.4)),x);}
double encode(double x,int space){double a=std::abs(x);return space==1?x:std::copysign(space==2?std::pow(a,1/2.4):(a<=.0031308?12.92*a:1.055*std::pow(a,1/2.4)-.055),x);}
}
std::array<double,3> detectScreen(const std::vector<float>& source,const std::vector<float>& keyed,int inputSpace){
    if(source.size()!=keyed.size()||source.size()%4||inputSpace<0||inputSpace>2)throw std::invalid_argument("Mismatched source/matte or encoding");
    std::array<double,3> sum{};double weight=0;
    for(size_t i=0;i<source.size();i+=4){double w=1-std::clamp(double(keyed[i+3]),0.,1.);w*=w;w*=w;weight+=w;for(int c=0;c<3;c++){double value=source[i+c];if(inputSpace!=0)value=encode(decode(value,inputSpace),0);sum[c]+=std::max(0.,value)*w;}}
    if(weight<1e-8)return {0,1,0};
    double peak=*std::max_element(sum.begin(),sum.end());
    if(peak<1e-8)return {0,1,0};
    for(auto& c:sum)c/=peak;
    return sum;
}
void applyPost(std::vector<float>& keyed,const std::vector<float>& source,const PostSettings& s){
    if(keyed.size()!=source.size()||keyed.size()%4||s.inputSpace<0||s.inputSpace>2||s.screen<0||s.screen>3||s.method<0||s.method>2||!std::isfinite(s.despill)||s.despill<0||s.despill>1||!std::isfinite(s.whitePoint)||s.whitePoint<=0||s.whitePoint>1)throw std::invalid_argument("Invalid output controls");
    // Alpha/detail-only controls need no display/linear round trip. Preserve
    // the original float signal exactly and avoid millions of pow operations.
    if(s.despill==0) {
        for(size_t i=0;i<keyed.size();i+=4) {
            double alpha=std::clamp(double(keyed[i+3]),0.,1.);
            for(int c=0;c<3;c++) {
                double value=s.recoverDetails&&alpha>.95?source[i+c]:keyed[i+c];
                if(s.linearize&&s.inputSpace!=1)value=decode(value,s.inputSpace);
                if(!std::isfinite(value)||std::abs(value)>3.402823466e38)throw std::runtime_error("Output control exceeded finite RGB range");
                keyed[i+c]=float(value);
            }
            keyed[i+3]=float(std::clamp(alpha/s.whitePoint,0.,1.));
        }
        return;
    }
    auto colour=s.screen==0?detectScreen(source,keyed,s.inputSpace):s.screen==1?std::array<double,3>{0,1,0}:s.screen==2?std::array<double,3>{0,0,1}:s.picked;
    for(auto c:colour)if(!std::isfinite(c)||c<0||c>1)throw std::invalid_argument("Invalid despill colour");
    double mean=(colour[0]+colour[1]+colour[2])/3.;std::array<double,3> q{};
    for(int c=0;c<3;c++)q[c]=colour[c]-mean;
    double peak=*std::max_element(q.begin(),q.end());
    if(peak>1e-8)for(auto& c:q)c/=peak;
    int dominant=int(std::max_element(colour.begin(),colour.end())-colour.begin());
    for(size_t i=0;i<keyed.size();i+=4){
        double alpha=std::clamp(double(keyed[i+3]),0.,1.);std::array<double,3> linear{},display{};
        for(int c=0;c<3;c++){
            double f=s.recoverDetails&&alpha>.95?source[i+c]:keyed[i+c];
            linear[c]=decode(f,s.inputSpace);display[c]=encode(linear[c],0);
        }
        if(s.despill>0&&peak>1e-8){
            double amount=0;for(int c=0;c<3;c++)amount+=display[c]*q[c];amount=std::max(0.,amount);
            if(s.method==1){double other=-INFINITY;for(int c=0;c<3;c++)if(c!=dominant)other=std::max(other,display[c]);amount=std::min(amount,std::max(0.,display[dominant]-other));}
            if(s.method==2){double grey=.2126*display[0]+.7152*display[1]+.0722*display[2];double factor=std::clamp(amount/(std::abs(display[dominant])+1e-8),0.,1.)*s.despill;for(auto& c:display)c+=(grey-c)*factor;}
            else for(int c=0;c<3;c++)display[c]-=s.despill*amount*q[c];
            for(int c=0;c<3;c++)linear[c]=decode(display[c],0);
        }
        for(int c=0;c<3;c++){double v=encode(linear[c],s.linearize?1:s.inputSpace);if(!std::isfinite(v)||std::abs(v)>3.402823466e38)throw std::runtime_error("Output control exceeded finite RGB range");keyed[i+c]=float(v);}
        keyed[i+3]=float(std::clamp(alpha/s.whitePoint,0.,1.));
    }
}
}
