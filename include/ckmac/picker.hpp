#pragma once
#include <string>

namespace ckmac {
enum class PickerKind { BakeFolder, BakeManifest };
// Manager owns AppKit's modal event loop; the OFX host receives only a path.
std::string chooseNativePath(PickerKind kind);
std::string parsePickerResponse(const std::string& response);
}
