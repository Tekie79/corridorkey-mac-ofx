#pragma once
// Compile-time identities. Never select an installed namespace from user environment.
#ifdef CKMAC_QA_PROFILE
#define CKMAC_PROFILE "qa"
#define CKMAC_DOMAIN "org.harvestpictures.CorridorKeyMac.QA"
#define CKMAC_PRODUCT_ROOT "/Library/Application Support/HarvestPictures/CorridorKeyMacQA"
#define CKMAC_PLUGIN_PATH "/Library/OFX/Plugins/CorridorKeyMacQA.ofx.bundle"
#define CKMAC_MANAGER_NAME "CorridorKey Mac QA Manager"
#define CKMAC_SOCKET_PREFIX "ckmac-qa-"
#define CKMAC_URL_SCHEME "ckmachpqa"
#define CKMAC_DISPLAY_NAME "CorridorKey Mac QA"
#define CKMAC_CACHE_CHILD "CorridorKey-QA-Cache-"
#else
#define CKMAC_PROFILE "personal"
#define CKMAC_DOMAIN "org.harvestpictures.CorridorKeyMac"
#define CKMAC_PRODUCT_ROOT "/Library/Application Support/HarvestPictures/CorridorKeyMac"
#define CKMAC_PLUGIN_PATH "/Library/OFX/Plugins/CorridorKeyMac.ofx.bundle"
#define CKMAC_MANAGER_NAME "CorridorKey Mac Manager"
#define CKMAC_SOCKET_PREFIX "ckmac-"
#define CKMAC_URL_SCHEME "ckmachp"
#define CKMAC_DISPLAY_NAME "CorridorKey2.0 hp beta"
#define CKMAC_CACHE_CHILD "CorridorKey-hp-Cache-"
#endif
#define CKMAC_MANAGER_PATH "/Applications/" CKMAC_MANAGER_NAME ".app"
