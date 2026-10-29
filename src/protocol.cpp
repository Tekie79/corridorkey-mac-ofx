#include "ckmac/protocol.hpp"

#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <poll.h>
#include <pwd.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/un.h>
#include <unistd.h>

namespace ckmac {
namespace {
using Clock = std::chrono::steady_clock;
struct Socket {
    int fd = -1;
    ~Socket() { if (fd >= 0) ::close(fd); }
};
void put32(unsigned char* p, std::uint32_t x) {
    p[0] = static_cast<unsigned char>(x >> 24);
    p[1] = static_cast<unsigned char>(x >> 16);
    p[2] = static_cast<unsigned char>(x >> 8);
    p[3] = static_cast<unsigned char>(x);
}
std::uint32_t get32(const unsigned char* p) {
    return (std::uint32_t(p[0]) << 24) | (std::uint32_t(p[1]) << 16)
         | (std::uint32_t(p[2]) << 8) | std::uint32_t(p[3]);
}
bool littleEndian() {
    std::uint16_t one = 1;
    return *reinterpret_cast<const unsigned char*>(&one) == 1;
}
void waitFor(int fd, short events, Clock::time_point deadline,
             const std::function<bool()>& cancelled) {
    while (true) {
        if (cancelled && cancelled()) throw Cancelled();
        auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(deadline - Clock::now()).count();
        if (remaining <= 0) throw std::runtime_error("CorridorKey worker timed out. Inspect the worker terminal and retry.");
        struct pollfd pfd{fd, events, 0};
        int result = ::poll(&pfd, 1, static_cast<int>(std::min<std::int64_t>(100, remaining)));
        if (result < 0 && errno == EINTR) continue;
        if (result < 0) throw std::runtime_error("Could not poll the CorridorKey worker socket.");
        if (!result) continue;
        // POLLIN may coexist with HUP when the peer closes after sending its reply.
        if (pfd.revents & events) return;
        if (pfd.revents & (POLLERR | POLLHUP | POLLNVAL))
            throw std::runtime_error("CorridorKey worker disconnected. Inspect its terminal for an inference error.");
    }
}
void transfer(int fd, unsigned char* buffer, std::size_t size, bool writing,
              Clock::time_point deadline, const std::function<bool()>& cancelled) {
    std::size_t offset = 0;
    while (offset < size) {
        waitFor(fd, writing ? POLLOUT : POLLIN, deadline, cancelled);
        ssize_t n;
        if (writing) {
#ifdef MSG_NOSIGNAL
            n = ::send(fd, buffer + offset, size - offset, MSG_NOSIGNAL);
#else
            n = ::send(fd, buffer + offset, size - offset, 0);
#endif
        } else {
            n = ::recv(fd, buffer + offset, size - offset, 0);
        }
        if (n < 0 && (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK)) continue;
        if (n <= 0) throw std::runtime_error("CorridorKey worker disconnected before completing a frame.");
        offset += static_cast<std::size_t>(n);
    }
}
std::uint32_t milli(double value) {
    if (!std::isfinite(value) || value < 0 || value > 1)
        throw std::runtime_error("Hint quality and despill must be between zero and one.");
    return static_cast<std::uint32_t>(std::lround(value * 1000.0));
}
}  // namespace

std::string defaultSocketPath() {
    // Resolve is commonly launched from Finder, so shell environment variables
    // are not a dependable source of the current account's home directory.
    const struct passwd* entry = ::getpwuid(::getuid());
    if (entry && entry->pw_dir && *entry->pw_dir)
        return std::string(entry->pw_dir) + "/Library/Caches/CorridorKeyMac/worker.sock";
    throw std::runtime_error("Cannot determine the current user's home directory.");
}

std::uint32_t checkedPayloadSize(std::uint32_t width, std::uint32_t height) {
    if (!width || !height || width > maxDimension || height > maxDimension
        || std::uint64_t(width) * height > maxPixels)
        throw std::runtime_error("Unsupported frame dimensions (maximum 8192 per side and 33,554,432 pixels).");
    return static_cast<std::uint32_t>(std::uint64_t(width) * height * 16);
}

Client::Client(std::string socketPath, std::function<bool()> cancelled, double timeoutSeconds)
    : path_(std::move(socketPath)), cancelled_(std::move(cancelled)), timeout_(timeoutSeconds) {
    if (!std::isfinite(timeout_) || timeout_ <= 0 || timeout_ > 3600)
        throw std::runtime_error("Invalid worker timeout.");
}

std::vector<unsigned char> Client::transact(std::uint32_t operation,
                                           std::uint32_t width, std::uint32_t height,
                                           const std::vector<float>& pixels,
                                           const Settings& settings) const {
    static_assert(sizeof(float) == 4 && std::numeric_limits<float>::is_iec559,
                  "The worker requires IEEE-754 float32 pixels");
    if (!littleEndian()) throw std::runtime_error("This build supports little-endian hosts only.");
    if (path_.empty() || path_[0] != '/' || path_.find('\0') != std::string::npos)
        throw std::runtime_error("Worker socket path must be an absolute local path.");
    struct sockaddr_un address{};
    if (path_.size() >= sizeof(address.sun_path))
        throw std::runtime_error("Worker socket path is too long for a Unix socket. Use a shorter absolute path.");
    if (operation != 1 && operation != 2) throw std::runtime_error("Invalid worker operation.");
    std::uint32_t size = operation == 1 ? checkedPayloadSize(width, height) : 0;
    if (pixels.size() * sizeof(float) != size)
        throw std::runtime_error("The frame payload size does not match its dimensions.");
    if (settings.inputSpace > 2) throw std::runtime_error("Invalid input color encoding.");
    std::uint32_t quality = milli(settings.hintQuality), despill = milli(settings.despillStrength);

    struct stat info{};
    if (::lstat(path_.c_str(), &info) != 0)
        throw std::runtime_error("CorridorKey worker is not running. Run bash scripts/start_worker.sh, then retry.");
    if (!S_ISSOCK(info.st_mode) || info.st_uid != ::getuid() || (info.st_mode & 0077))
        throw std::runtime_error("Unsafe worker socket: it must be a socket owned by your account with mode 0600.");

    Socket socket;
    socket.fd = ::socket(AF_UNIX, SOCK_STREAM, 0);
    if (socket.fd < 0) throw std::runtime_error("Cannot create a local worker socket.");
    if (::fcntl(socket.fd, F_SETFL, O_NONBLOCK) < 0
        || ::fcntl(socket.fd, F_SETFD, FD_CLOEXEC) < 0)
        throw std::runtime_error("Cannot configure the local worker socket.");
#ifdef SO_NOSIGPIPE
    int noSigpipe = 1;
    if (::setsockopt(socket.fd, SOL_SOCKET, SO_NOSIGPIPE, &noSigpipe, sizeof(noSigpipe)) != 0)
        throw std::runtime_error("Cannot protect Resolve from broken-pipe signals.");
#endif
    address.sun_family = AF_UNIX;
    std::memcpy(address.sun_path, path_.c_str(), path_.size() + 1);
    auto deadline = Clock::now() + std::chrono::duration_cast<Clock::duration>(std::chrono::duration<double>(timeout_));
    if (::connect(socket.fd, reinterpret_cast<struct sockaddr*>(&address), sizeof(address)) < 0) {
        if (errno != EINPROGRESS && errno != EAGAIN)
            throw std::runtime_error("Cannot connect to CorridorKey worker. Run bash scripts/start_worker.sh.");
        auto connectDeadline = std::min(deadline, Clock::now() + std::chrono::seconds(5));
        waitFor(socket.fd, POLLOUT, connectDeadline, cancelled_);
        int error = 0;
        socklen_t length = sizeof(error);
        if (::getsockopt(socket.fd, SOL_SOCKET, SO_ERROR, &error, &length) || error)
            throw std::runtime_error("Cannot connect to CorridorKey worker.");
    }
#ifdef __APPLE__
    uid_t peerUid;
    gid_t peerGid;
    if (::getpeereid(socket.fd, &peerUid, &peerGid) || peerUid != ::getuid())
        throw std::runtime_error("Worker is not owned by your account.");
#elif defined(__linux__)
    struct ucred credentials{};
    socklen_t length = sizeof(credentials);
    if (::getsockopt(socket.fd, SOL_SOCKET, SO_PEERCRED, &credentials, &length)
        || credentials.uid != ::getuid())
        throw std::runtime_error("Worker is not owned by your account.");
#endif
    std::array<unsigned char, requestHeaderBytes> header{};
    std::memcpy(header.data(), "CKM1", 4);
    put32(header.data() + 4, protocolVersion);
    put32(header.data() + 8, operation);
    put32(header.data() + 12, width);
    put32(header.data() + 16, height);
    put32(header.data() + 20, size);
    put32(header.data() + 24, operation == 1 ? settings.inputSpace | (settings.sourceAlphaHint ? 4U : 0U) : 0);
    put32(header.data() + 28, operation == 1 ? quality : 0);
    put32(header.data() + 32, operation == 1 ? despill : 0);
    // Final reserved field is zero, as required by protocol v1.
    transfer(socket.fd, header.data(), header.size(), true, deadline, cancelled_);
    if (size) transfer(socket.fd, reinterpret_cast<unsigned char*>(const_cast<float*>(pixels.data())),
                       size, true, deadline, cancelled_);

    std::array<unsigned char, responseHeaderBytes> response{};
    transfer(socket.fd, response.data(), response.size(), false, deadline, cancelled_);
    if (std::memcmp(response.data(), "CKR1", 4) || get32(response.data() + 4) != protocolVersion
        || get32(response.data() + 24) || get32(response.data() + 28))
        throw std::runtime_error("Invalid CorridorKey worker response header.");
    std::uint32_t status = get32(response.data() + 8);
    std::uint32_t returnedWidth = get32(response.data() + 12), returnedHeight = get32(response.data() + 16);
    std::uint32_t returnedSize = get32(response.data() + 20);
    if (status) {
        if (returnedWidth || returnedHeight || returnedSize > 65536)
            throw std::runtime_error("Invalid worker error response.");
    } else if (operation == 1) {
        if (returnedWidth != width || returnedHeight != height || returnedSize != size)
            throw std::runtime_error("Worker returned a frame with incorrect dimensions.");
    } else if (returnedWidth || returnedHeight || returnedSize > 65536) {
        throw std::runtime_error("Invalid worker health response.");
    }
    std::vector<unsigned char> result(returnedSize);
    if (returnedSize) transfer(socket.fd, result.data(), result.size(), false, deadline, cancelled_);
    if (status) throw std::runtime_error("CorridorKey: " + std::string(result.begin(), result.end()));
    return result;
}

std::vector<float> Client::infer(std::uint32_t width, std::uint32_t height,
                                const std::vector<float>& pixels, const Settings& settings) const {
    auto bytes = transact(1, width, height, pixels, settings);
    std::vector<float> output(bytes.size() / sizeof(float));
    std::memcpy(output.data(), bytes.data(), bytes.size());
    for (float value : output)
        if (!std::isfinite(value)) throw std::runtime_error("Worker returned non-finite pixels; render stopped.");
    return output;
}

std::string Client::health() const {
    auto bytes = transact(2, 0, 0, {}, Settings{});
    return {bytes.begin(), bytes.end()};
}
}  // namespace ckmac
