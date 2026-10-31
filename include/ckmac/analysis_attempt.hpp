#pragma once
#include <chrono>
#include <cstdint>
#include <mutex>
#include <stdexcept>
#include <string>

namespace ckmac {
// Host-driven, transient intent: only source confirmation can survive a Render.
// No images, saved parameters, timers or host calls are retained here.
class AnalysisAttempt {
public:
    using Clock=std::chrono::steady_clock;
    enum class Phase { Idle, Requested, Capturing, AwaitingConfirmation, Verifying, Analyzing };
    class Render {
        friend class AnalysisAttempt;
        AnalysisAttempt* owner_;
        std::uint64_t id_;
        Render(AnalysisAttempt* owner,std::uint64_t id):owner_(owner),id_(id){}
    public:
        Render(const Render&)=delete;
        Render& operator=(const Render&)=delete;
        ~Render(){if(owner_)owner_->finish(id_);}
        explicit operator bool() const {return owner_!=nullptr;}
        void verifySource(const std::string& generation) {
            if(!owner_)return;
            std::lock_guard<std::mutex> lock(owner_->mutex_);
            owner_->check(id_);
            if(owner_->phase_==Phase::Verifying&&owner_->source_!=generation)
                throw std::runtime_error("Source or analysis settings changed during capture confirmation. The previous bake is preserved; retry Analyze/Resume with upstream settings unchanged.");
        }
        void awaitConfirmation(const std::string& generation,Clock::time_point now=Clock::now()) {
            if(!owner_)return;
            std::lock_guard<std::mutex> lock(owner_->mutex_);
            owner_->check(id_);
            if(owner_->phase_!=Phase::Capturing)
                throw std::runtime_error("Source confirmation failed. The previous bake is preserved; retry Analyze/Resume.");
            owner_->source_=generation;owner_->phase_=Phase::AwaitingConfirmation;
            owner_->until_=now+std::chrono::seconds(30);
            owner_=nullptr; // Explicit handoff only; exceptions always finish.
        }
        void analyzing() {
            if(!owner_)return;
            std::lock_guard<std::mutex> lock(owner_->mutex_);
            owner_->check(id_);owner_->phase_=Phase::Analyzing;
        }
    };
    void arm(std::uint64_t generation,Clock::time_point now=Clock::now()) {
        std::lock_guard<std::mutex> lock(mutex_);
        ++id_;generation_=generation;source_.clear();phase_=Phase::Requested;
        until_=now+std::chrono::seconds(30);
    }
    Render begin(std::uint64_t generation,Clock::time_point now=Clock::now()) {
        std::lock_guard<std::mutex> lock(mutex_);
        if(phase_!=Phase::Requested&&phase_!=Phase::AwaitingConfirmation)return Render(nullptr,0);
        if(generation_!=generation||now>=until_){phase_=Phase::Idle;source_.clear();return Render(nullptr,0);}
        phase_=phase_==Phase::Requested?Phase::Capturing:Phase::Verifying;
        return Render(this,id_);
    }
    bool pending(Clock::time_point now=Clock::now()) const {
        std::lock_guard<std::mutex> lock(mutex_);
        return (phase_==Phase::Requested||phase_==Phase::AwaitingConfirmation)&&now<until_;
    }
    void cancel(){std::lock_guard<std::mutex> lock(mutex_);++id_;phase_=Phase::Idle;source_.clear();}
private:
    void check(std::uint64_t id) const {
        if(id!=id_||phase_==Phase::Idle)throw std::runtime_error("Analysis attempt canceled or superseded. The previous bake is preserved.");
    }
    void finish(std::uint64_t id) {
        std::lock_guard<std::mutex> lock(mutex_);
        if(id==id_){phase_=Phase::Idle;source_.clear();}
    }
    mutable std::mutex mutex_;
    Phase phase_=Phase::Idle;
    std::uint64_t id_=0,generation_=0;
    Clock::time_point until_{};
    std::string source_;
};
}
