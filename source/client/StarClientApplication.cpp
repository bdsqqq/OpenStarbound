#include "StarClientApplication.hpp"
#include "StarClientCommandProcessor.hpp"
#ifdef STAR_USE_RUST_SHELL
#include "StarRustShell.h"
#endif
#include <cmath>
#include <functional>
#include <thread>
#include "StarBehaviorLab.hpp"
#ifdef STAR_USE_RUST_UUID
#include "StarRustUuid.h"
#endif
#ifdef STAR_USE_RUST_ORDERED_SET
#include "StarRustOrderedSet.h"
#endif
#ifdef STAR_USE_RUST_SET
#include "StarRustSet.h"
#endif
#ifdef STAR_USE_RUST_NET_FIELD
#include "StarRustNetFloat.h"
#endif
#ifdef STAR_USE_RUST_NET_FIELD
#include "StarRustNetScalar.h"
#endif
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetSync.h"
#endif
#ifdef STAR_USE_RUST_NET_DYNAMIC
#include "StarRustNetDynamic.h"
#endif
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetRules.h"
#endif
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetCompat.h"
#endif
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetVersion.h"
#endif
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetOverride.h"
#endif
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetMap.h"
#endif
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetTop.h"
#endif
#ifdef STAR_USE_RUST_NET_GROUP
#include "StarRustNetGroup.h"
#endif
#ifdef STAR_USE_RUST_NET_FIELD
#include "StarRustNetField.h"
#endif
#ifdef STAR_USE_RUST_NET_SIGNAL
#include "StarRustNetSignal.h"
#endif
#ifdef STAR_USE_RUST_TIME
#include "StarRustTime.h"
#endif
#ifdef STAR_USE_RUST_WORKER_POOL
#include "StarRustWorkerPool.h"
#endif
#ifdef STAR_USE_RUST_PERIODIC
#include "StarRustPeriodic.h"
#endif
#ifdef STAR_USE_RUST_MAP
#include "StarRustMap.h"
#endif
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
#include "StarRustFlatHashTable.h"
#endif
#ifdef STAR_USE_RUST_BIMAP
#include "StarRustBiMap.h"
#endif
#include "StarTileSectorArrayObserver.hpp"
#include "StarTextProcessLab.hpp"
#include "StarStringViewLab.hpp"
#include "StarAssetPath.hpp"
#ifdef STAR_USE_RUST_TEXT_SCAN
#include "StarRustTextScan.h"
#endif
#include "StarSha256Lab.hpp"
#include "StarVlqLab.hpp"
#include "StarBytesLab.hpp"
#include "StarUnicodeLab.hpp"
#include "StarJsonPathLab.hpp"
#include "StarJsonPatchLab.hpp"
#include "StarAssetPathLab.hpp"
#include "StarRandomMwcLab.hpp"
#include "StarCompressionLab.hpp"
#include "StarZstdLab.hpp"
#include "StarPathEmbedLab.hpp"
#include "StarLruCacheLab.hpp"
#include "StarTtlCacheLab.hpp"
#ifdef STAR_USE_RUST_WEIGHTED_POOL
#include "StarRustWeightedPool.h"
#endif
#include "StarTenantDatabase.hpp"
#include "StarLua.hpp"
#include "StarRootLuaBindings.hpp"
#include "StarHostAddressLab.hpp"
#include "StarDataStreamLab.hpp"
#include "StarBufferLab.hpp"
#include "StarFileLab.hpp"
#include "StarIODeviceLab.hpp"
#include "StarByteArrayLab.hpp"
#include "StarBTreeLab.hpp"
#include <sstream>
#include "StarOptionParserLab.hpp"
#include "StarRootLuaBindings.hpp"
#include "StarNetPacketSocket.hpp"
#ifdef STAR_USE_RUST_BYTES
#include "StarRustBytes.h"
#endif
#include "StarVlqEncoding.hpp"
#include "StarVersioningDatabase.hpp"
#include "StarNetPackets.hpp"
#include "StarDataStreamDevices.hpp"
#include <array>
#include "StarBTreeDatabase.hpp"
#include "StarBuffer.hpp"
#ifdef STAR_USE_RUST_SHA256
#include "StarRustSha256.h"
#endif
#include "StarObjectDatabase.hpp"
#include "StarObject.hpp"
#include "StarMaterialDatabase.hpp"
#include "StarActorMovementController.hpp"
#include "StarWorldServer.hpp"
#include "StarWorldGeneration.hpp"
#include <filesystem>
#include <cstring>
#include "StarImageProcessing.hpp"
#ifdef STAR_USE_RUST_ENCODE
#include "StarRustEncode.h"
#endif
#ifdef STAR_USE_RUST_LIGHTING
#include "StarRustLighting.h"
#endif
#ifdef STAR_USE_RUST_BLOCKS_ALONG_LINE
#include "StarRustTraversal.h"
#endif
#include "StarConfiguration.hpp"
#include "StarJsonExtra.hpp"
#include "StarFile.hpp"
#include "StarEncode.hpp"
#include "StarLogging.hpp"
#include "StarJsonExtra.hpp"
#include "StarRoot.hpp"
#include "StarVersionOptionParser.hpp"
#include "StarPlayer.hpp"
#include "StarStatusController.hpp"
#include "StarStatusControllerLuaBindings.hpp"
#ifdef STAR_USE_RUST_ID_MAP
#include "StarRustIdMap.h"
#endif
#include "StarPlayerStorage.hpp"
#include "StarPlayerLog.hpp"
#include "StarAssets.hpp"
#include "StarWorldTemplate.hpp"
#include "StarWorldClient.hpp"
#include "StarRootLoader.hpp"
#include "StarInput.hpp"
#include "StarVoice.hpp"
#include "StarCurve25519.hpp"
#include "StarInterpolation.hpp"

#include "StarUniverseClientLuaBindings.hpp"
#include "StarCameraLuaBindings.hpp"
#include "StarCelestialLuaBindings.hpp"
#include "StarClipboardLuaBindings.hpp"
#include "StarInputLuaBindings.hpp"
#include "StarInterfaceLuaBindings.hpp"
#include "StarRenderingLuaBindings.hpp"
#include "StarTeamClientLuaBindings.hpp"
#include "StarLuaHttpBindings.hpp"
#include "StarVoiceLuaBindings.hpp"
#include "StarHttpTrustDialog.hpp"
#include "StarMainInterfaceTypes.hpp"

#include "imgui.h"
#include "imgui_freetype.h"

#if defined STAR_SYSTEM_WINDOWS
#include <windows.h>
// graphics driver is told by these exports to default to the dedicated GPU
extern "C" __declspec(dllexport) DWORD NvOptimusEnablement = 1;
extern "C" __declspec(dllexport) DWORD AmdPowerXpressRequestHighPerformance = 1;

// https://docs.kicad.org/doxygen/windows_2app_8cpp_source.html L45
extern "C" __declspec(dllexport) void NoHotPatch() { return; }
#endif 

namespace Star {

Json const AdditionalAssetsSettings = Json::parseJson(R"JSON(
    {
      "missingImage" : "/assetmissing.png",
      "missingAudio" : "/assetmissing.wav"
    }
  )JSON");

Json const AdditionalDefaultConfiguration = Json::parseJson(R"JSON(
    {
      "configurationVersion" : {
        "client" : 8
      },

      "allowAssetsMismatch" : false,
      "vsync" : true,
      "limitTextureAtlasSize" : false,
      "useMultiTexturing" : true,
      "audioChannelSeparation" : [-25, 25],

      "sfxVol" : 100,
      "instrumentVol" : 100,
      "musicVol" : 70,
      "hardwareCursor" : true,
      "windowedResolution" : [1000, 600],
      "fullscreenResolution" : [1920, 1080],
      "fullscreen" : false,
      "borderless" : false,
      "maximized" : true,
      "antiAliasing" : false,
      "hdr": true,
      "zoomLevel" : 3.0,
      "cameraSpeedFactor" : 1.0,
      "interfaceScale" : 0,
      "speechBubbles" : true,

      "title" : {
        "multiPlayerAddress" : "",
        "multiPlayerPort" : "",
        "multiPlayerAccount" : "",
        "multiPlayerForceLegacy" : false
      },

      "bindings" : {
        "PlayerUp" :  [ { "type" : "key", "value" : "W", "mods" : [] } ],
        "PlayerDown" :  [ { "type" : "key", "value" : "S", "mods" : [] } ],
        "PlayerLeft" :  [ { "type" : "key", "value" : "A", "mods" : [] } ],
        "PlayerRight" :  [ { "type" : "key", "value" : "D", "mods" : [] } ],
        "PlayerJump" :  [ { "type" : "key", "value" : "Space", "mods" : [] } ],
        "PlayerDropItem" :  [ { "type" : "key", "value" : "Q", "mods" : [] } ],
        "PlayerInteract" :  [ { "type" : "key", "value" : "E", "mods" : [] } ],
        "PlayerShifting" :  [ { "type" : "key", "value" : "RShift", "mods" : [] }, { "type" : "key", "value" : "LShift", "mods" : [] } ],
        "PlayerTechAction1" :  [ { "type" : "key", "value" : "F", "mods" : [] } ],
        "PlayerTechAction2" :  [],
        "PlayerTechAction3" :  [],
        "EmoteBlabbering" :  [ { "type" : "key", "value" : "Right", "mods" : ["LCtrl", "LShift"] } ],
        "EmoteShouting" :  [ { "type" : "key", "value" : "Up", "mods" : ["LCtrl", "LAlt"] } ],
        "EmoteHappy" :  [ { "type" : "key", "value" : "Up", "mods" : [] } ],
        "EmoteSad" :  [ { "type" : "key", "value" : "Down", "mods" : [] } ],
        "EmoteNeutral" :  [ { "type" : "key", "value" : "Left", "mods" : [] } ],
        "EmoteLaugh" :  [ { "type" : "key", "value" : "Left", "mods" : [ "LCtrl" ] } ],
        "EmoteAnnoyed" :  [ { "type" : "key", "value" : "Right", "mods" : [] } ],
        "EmoteOh" :  [ { "type" : "key", "value" : "Right", "mods" : [ "LCtrl" ] } ],
        "EmoteOooh" :  [ { "type" : "key", "value" : "Down", "mods" : [ "LCtrl" ] } ],
        "EmoteBlink" :  [ { "type" : "key", "value" : "Up", "mods" : [ "LCtrl" ] } ],
        "EmoteWink" :  [ { "type" : "key", "value" : "Up", "mods" : ["LCtrl", "LShift"] } ],
        "EmoteEat" :  [ { "type" : "key", "value" : "Down", "mods" : ["LCtrl", "LShift"] } ],
        "EmoteSleep" :  [ { "type" : "key", "value" : "Left", "mods" : ["LCtrl", "LShift"] } ],
        "ShowLabels" :  [ { "type" : "key", "value" : "RAlt", "mods" : [] }, { "type" : "key", "value" : "LAlt", "mods" : [] } ],
        "CameraShift" :  [ { "type" : "key", "value" : "RCtrl", "mods" : [] }, { "type" : "key", "value" : "LCtrl", "mods" : [] } ],
        "TitleBack" :  [ { "type" : "key", "value" : "Esc", "mods" : [] } ],
        "CinematicSkip" :  [ { "type" : "key", "value" : "Esc", "mods" : [] } ],
        "CinematicNext" :  [ { "type" : "key", "value" : "Right", "mods" : [] }, { "type" : "key", "value" : "Return", "mods" : [] } ],
        "GuiClose" :  [ { "type" : "key", "value" : "Esc", "mods" : [] } ],
        "GuiShifting" :  [ { "type" : "key", "value" : "RShift", "mods" : [] }, { "type" : "key", "value" : "LShift", "mods" : [] } ],
        "KeybindingCancel" :  [ { "type" : "key", "value" : "Esc", "mods" : [] } ],
        "KeybindingClear" :  [ { "type" : "key", "value" : "Del", "mods" : [] }, { "type" : "key", "value" : "Backspace", "mods" : [] } ],
        "ChatPageUp" :  [ { "type" : "key", "value" : "PageUp", "mods" : [] } ],
        "ChatPageDown" :  [ { "type" : "key", "value" : "PageDown", "mods" : [] } ],
        "ChatPreviousLine" :  [ { "type" : "key", "value" : "Up", "mods" : [] } ],
        "ChatNextLine" :  [ { "type" : "key", "value" : "Down", "mods" : [] } ],
        "ChatSendLine" :  [ { "type" : "key", "value" : "Return", "mods" : [] } ],
        "ChatBegin" :  [ { "type" : "key", "value" : "Return", "mods" : [] } ],
        "ChatBeginCommand" :  [ { "type" : "key", "value" : "/", "mods" : [] } ],
        "ChatStop" :  [ { "type" : "key", "value" : "Esc", "mods" : [] } ],
        "InterfaceHideHud" :  [ { "type" : "key", "value" : "F1", "mods" : [] } ],
        "InterfaceChangeBarGroup" :  [ { "type" : "key", "value" : "X", "mods" : [] } ],
        "InterfaceDeselectHands" :  [ { "type" : "key", "value" : "Z", "mods" : [] } ],
        "InterfaceBar1" :  [ { "type" : "key", "value" : "1", "mods" : [] } ],
        "InterfaceBar2" :  [ { "type" : "key", "value" : "2", "mods" : [] } ],
        "InterfaceBar3" :  [ { "type" : "key", "value" : "3", "mods" : [] } ],
        "InterfaceBar4" :  [ { "type" : "key", "value" : "4", "mods" : [] } ],
        "InterfaceBar5" :  [ { "type" : "key", "value" : "5", "mods" : [] } ],
        "InterfaceBar6" :  [ { "type" : "key", "value" : "6", "mods" : [] } ],
        "InterfaceBar7" :  [],
        "InterfaceBar8" :  [],
        "InterfaceBar9" :  [],
        "InterfaceBar10" :  [],
        "EssentialBar1" :  [ { "type" : "key", "value" : "R", "mods" : [] } ],
        "EssentialBar2" :  [ { "type" : "key", "value" : "T", "mods" : [] } ],
        "EssentialBar3" :  [ { "type" : "key", "value" : "Y", "mods" : [] } ],
        "EssentialBar4" :  [ { "type" : "key", "value" : "N", "mods" : [] } ],
        "InterfaceRepeatCommand" :  [ { "type" : "key", "value" : "P", "mods" : [] } ],
        "InterfaceToggleFullscreen" :  [ { "type" : "key", "value" : "F11", "mods" : [] } ],
        "InterfaceReload" :  [],
        "InterfaceEscapeMenu" :  [ { "type" : "key", "value" : "Esc", "mods" : [] } ],
        "InterfaceInventory" :  [ { "type" : "key", "value" : "I", "mods" : [] } ],
        "InterfaceCodex" :  [ { "type" : "key", "value" : "L", "mods" : [] } ],
        "InterfaceQuest" :  [ { "type" : "key", "value" : "J", "mods" : [] } ],
        "InterfaceCrafting" :  [ { "type" : "key", "value" : "C", "mods" : [] } ]
      }
    }
  )JSON");

void ClientApplication::startup(StringList const& cmdLineArgs) {
  RootLoader rootLoader({AdditionalAssetsSettings, AdditionalDefaultConfiguration, String("starbound.log"), LogLevel::Info, false, String("starbound.config")});
  rootLoader.setVersionName("Client");  
  m_root = rootLoader.initOrDie(cmdLineArgs).first;
  if (BehaviorLab::enabled()) {
    validateBehaviorStorage();
    auto config = m_root->configuration();
    config->set("clientIPJoinable", false);
    config->set("clientP2PJoinable", false);
    config->set("includeUGC", false);
    config->set("zoomLevel", 2.0);
    config->set("windowedResolution", JsonArray{1000, 600});
    config->set("fullscreen", false);
    config->set("borderless", false);
    config->set("maximized", false);
  }
  Logger::info("{}", rootLoader.getVersionString());
  #ifdef __clang__
  Logger::info("Compiled with Clang {}", __clang_version__);
  #endif
}

void ClientApplication::shutdown() {
  if (BehaviorLab::staticVectorScene())
    BehaviorLab::restoreStaticVectorScene(m_universeServer.get(), m_universeClient ? m_universeClient->worldClient().get() : nullptr, false);
  if (BehaviorLab::idMapScene()) BehaviorLab::restoreIdMapStatus();
  // Clear HTTP trust request callback
  LuaBindings::clearHttpTrustRequestCallback();

  m_mainInterface.reset();

  if (m_universeClient)
    m_universeClient->disconnect();

  if (m_universeServer) {
    m_universeServer->stop();
    m_universeServer->join();
    m_universeServer.reset();
  }

  if (m_statistics) {
    m_statistics->writeStatistics();
    m_statistics.reset();
  }

  m_universeClient.reset();
  m_statistics.reset();
}

void ClientApplication::applicationInit(ApplicationControllerPtr appController) {
  Application::applicationInit(appController);
  m_behaviorMainThread = std::this_thread::get_id();

  appController->setCursorVisible(true);

  auto configuration = m_root->configuration();
  bool vsync = configuration->get("vsync").toBool();
  Vec2U windowedSize = jsonToVec2U(configuration->get("windowedResolution"));
  Vec2U fullscreenSize = jsonToVec2U(configuration->get("fullscreenResolution"));
  bool fullscreen = configuration->get("fullscreen").toBool();
  bool borderless = configuration->get("borderless").toBool();
  bool maximized = configuration->get("maximized").toBool();
  m_controllerInput = configuration->get("controllerInput").optBool().value();
  
  #ifdef STAR_SYSTEM_WINDOWS
    appController->setBorderlessWorkaround(configuration->get("borderlessWorkaround", true).toBool());
  #endif

  if (fullscreen)
    appController->setFullscreenWindow(fullscreenSize);
  else if (borderless)
    appController->setBorderlessWindow();
  else if (maximized)
    appController->setMaximizedWindow();
  else
    appController->setNormalWindow(windowedSize);

  float updateRate = 1.0f / GlobalTimestep;
  if (auto jUpdateRate = configuration->get("updateRate")) {
    updateRate = jUpdateRate.toFloat();
    GlobalTimestep = 1.0f / updateRate;
  }

  if (auto jServerUpdateRate = configuration->get("serverUpdateRate"))
    ServerGlobalTimestep = 1.0f / jServerUpdateRate.toFloat();

  appController->setTargetUpdateRate(updateRate);
  appController->setVSyncEnabled(vsync);
  appController->setCursorHardware(configuration->get("hardwareCursor").optBool().value(true));

  // Must be called before anything that can invoke an asset load.
  loadMods();
  
  AudioFormat audioFormat = appController->enableAudio();
  m_mainMixer = make_shared<MainMixer>(audioFormat.sampleRate, audioFormat.channels);
  m_mainMixer->setVolume(0.5);
  
  m_worldPainter = make_shared<WorldPainter>();
  m_guiContext = make_shared<GuiContext>(m_mainMixer->mixer(), appController);
  m_input = make_shared<Input>();
  m_voice = make_shared<Voice>(appController);  

  auto assets = m_root->assets();

  {
    auto& io = ImGui::GetIO();
    io.ConfigFlags |= ImGuiConfigFlags_NoMouseCursorChange;
    m_immediateFont = *assets->bytes("/hobo.ttf");
    ImFontConfig config{};
    config.FontDataOwnedByAtlas = false;
    config.FontLoaderFlags = ImGuiFreeTypeLoaderFlags_ForceAutoHint;
    io.Fonts->AddFontFromMemoryTTF(m_immediateFont.ptr(), m_immediateFont.size(),
      16, &config, io.Fonts->GetGlyphRangesDefault());
  }

  m_minInterfaceScale = assets->json("/interface.config:minInterfaceScale").toFloat();
  m_maxInterfaceScale = assets->json("/interface.config:maxInterfaceScale").toFloat();
  m_crossoverRes = jsonToVec2F(assets->json("/interface.config:interfaceCrossoverRes"));
  
  appController->setApplicationTitle(assets->json("/client.config:windowTitle").toString());
  appController->setMaxFrameSkip(assets->json("/client.config:maxFrameSkip").toUInt());
  appController->setUpdateTrackWindow(assets->json("/client.config:updateTrackWindow").toFloat());
  
  if (auto jVoice = configuration->get("voice"))
    m_voice->loadJson(jVoice.toObject(), true);

  m_voice->init();
  m_voice->setLocalSpeaker(0);
}

void ClientApplication::renderInit(RendererPtr renderer) {
  Application::renderInit(renderer);
  renderReload();
  m_root->registerReloadListener(m_reloadListener = make_shared<CallbackListener>([this]() { renderReload(); }));

  if (m_root->configuration()->get("limitTextureAtlasSize").optBool().value(false))
    renderer->setSizeLimitEnabled(true);

  renderer->setMultiTexturingEnabled(m_root->configuration()->get("useMultiTexturing").optBool().value(true));

  m_guiContext->renderInit(renderer);

  m_cinematicOverlay = make_shared<Cinematic>();
  m_errorScreen = make_shared<ErrorScreen>();

  if (m_titleScreen)
    m_titleScreen->renderInit(renderer);
  if (m_worldPainter)
    m_worldPainter->renderInit(renderer);

  #ifdef STAR_ENABLE_STEAM_INTEGRATION
  #ifdef STAR_SYSTEM_LINUX
  if (g_steamIsFlatpak && !BehaviorLab::enabled()) {
    auto config = m_root->configuration();
    if (!config->get("steamFlatpakWarningShown").optBool().value()) {
      config->set("steamFlatpakWarningShown", true);
      m_errorScreen->setMessage(m_root->assets()->json("/interface.config:steamFlatpakWarning").toString());
      changeState(MainAppState::SteamFlatpakWarning);
      return;
    }
  }
  #endif
  #endif

  changeState(MainAppState::Mods);
}

void ClientApplication::windowChanged(WindowMode windowMode, Vec2U screenSize) {
  auto config = m_root->configuration();
  if (windowMode == WindowMode::Fullscreen) {
    config->set("fullscreenResolution", jsonFromVec2U(screenSize));
    config->set("fullscreen", true);
    config->set("borderless", false);
  } else if (windowMode == WindowMode::Borderless) {
    config->set("borderless", true);
    config->set("fullscreen", false);
  } else if (windowMode == WindowMode::Maximized) {
    config->set("maximized", true);
    config->set("fullscreen", false);
    config->set("borderless", false);
  } else {
    config->set("maximized", false);
    config->set("fullscreen", false);
    config->set("borderless", false);
    config->set("windowedResolution", jsonFromVec2U(screenSize));
  }
}

void ClientApplication::processInput(InputEvent const& event) {
  if (BehaviorLab::enabled())
    return;
  if (auto keyDown = event.ptr<KeyDownEvent>()) {
    m_heldKeyEvents.append(*keyDown);
    m_edgeKeyEvents.append(*keyDown);
  } else if (auto keyUp = event.ptr<KeyUpEvent>()) {
    eraseWhere(m_heldKeyEvents, [&](auto& keyEvent) {
      return keyEvent.key == keyUp->key;
    });

    Maybe<KeyMod> modKey = KeyModNames.maybeLeft(KeyNames.getRight(keyUp->key));
    if (modKey)
      m_heldKeyEvents.transform([&](auto& keyEvent) {
        return KeyDownEvent{keyEvent.key, keyEvent.mods & ~*modKey};
      });
  }
  else if (auto cAxis = event.ptr<ControllerAxisEvent>()) {
    if (cAxis->controllerAxis == ControllerAxis::LeftX)
      m_controllerLeftStick[0] = cAxis->controllerAxisValue;
    else if (cAxis->controllerAxis == ControllerAxis::LeftY)
      m_controllerLeftStick[1] = cAxis->controllerAxisValue;
    else if (cAxis->controllerAxis == ControllerAxis::RightX)
      m_controllerRightStick[0] = cAxis->controllerAxisValue;
    else if (cAxis->controllerAxis == ControllerAxis::RightY)
      m_controllerRightStick[1] = cAxis->controllerAxisValue;
  }

  bool processed = !m_errorScreen->accepted() && m_errorScreen->handleInputEvent(event);

  if (!processed) {
    if (m_state == MainAppState::Splash) {
      processed = m_cinematicOverlay->handleInputEvent(event);
    } else if (m_state == MainAppState::Title) {
      if (!(processed = m_cinematicOverlay->handleInputEvent(event)))
        processed = m_titleScreen->handleInputEvent(event);

    } else if (m_state == MainAppState::SinglePlayer || m_state == MainAppState::MultiPlayer) {
      if (!(processed = m_cinematicOverlay->handleInputEvent(event)))
        processed = m_mainInterface->handleInputEvent(event);
    }
  }

  m_input->handleInput(event, processed);
}

void ClientApplication::update() try {
  float dt = GlobalTimestep * GlobalTimescale;
  auto& app = appController();
  if (BehaviorLab::enabled()) {
    auto maxFrames = BehaviorLab::configuration().getUInt("maxFrames", 1800);
    if (++m_behaviorFrames > maxFrames) {
      Logger::error("BehaviorLab: scenario timed out at phase {} stage {}", m_behaviorPhase, m_behaviorStage);
      if (BehaviorLab::staticVectorScene())
        BehaviorLab::restoreStaticVectorScene(m_universeServer.get(), m_universeClient ? m_universeClient->worldClient().get() : nullptr, false);
      app->quit();
      return;
    }
  }
  if (m_state >= MainAppState::Title) {
    if (auto p2pNetworkingService = app->p2pNetworkingService()) {
      if (auto join = p2pNetworkingService->pullPendingJoin()) {
        m_pendingMultiPlayerConnection = PendingMultiPlayerConnection{join.takeValue(), {}, {}, false};
        changeState(MainAppState::Title);
      }
      
      if (auto req = p2pNetworkingService->pullJoinRequest())
        m_mainInterface->queueJoinRequest(*req);

      p2pNetworkingService->update();
    }
  }

  if (!m_errorScreen->accepted())
    m_errorScreen->update(dt);

  // This warning is only applicable to Linux systems so no need to process it otherwise.
  #ifdef STAR_ENABLE_STEAM_INTEGRATION
  #ifdef STAR_SYSTEM_LINUX
  if (m_state == MainAppState::SteamFlatpakWarning)
    updateSteamFlatpakWarning(dt);
  else
  #endif
  #endif

  if (m_state == MainAppState::Mods)
    updateMods(dt);
  else if (m_state == MainAppState::ModsWarning)
    updateModsWarning(dt);

  if (m_state == MainAppState::Splash)
    updateSplash(dt);
  else if (m_state == MainAppState::Error)
    updateError(dt);
  else if (m_state == MainAppState::Title)
    updateTitle(dt);
  else if (m_state > MainAppState::Title)
    updateRunning(dt);
  
  // Swallow leftover encoded voice data if we aren't in-game to allow mic read to continue for settings.
  if (m_state <= MainAppState::Title) {
    DataStreamBuffer ext;
    m_voice->send(ext);
  } // TODO: directly disable encoding at menu so we don't have to do this

  if (BehaviorLab::enabled() && m_state == MainAppState::SinglePlayer)
    updateBehaviorScenario();

  m_guiContext->cleanup();
  m_edgeKeyEvents.clear();
  m_input->update();
  ++m_framesSkipped;
}

catch (...) {
  try {
    if (BehaviorLab::staticVectorScene())
      BehaviorLab::restoreStaticVectorScene(m_universeServer.get(), m_universeClient ? m_universeClient->worldClient().get() : nullptr, false);
  } catch (...) {
    // Diagnostic cleanup must not replace the original update failure.
  }
  throw;
}

void ClientApplication::render() try {
  m_framesSkipped = 0;
  auto config = m_root->configuration();
  auto assets = m_root->assets();
  auto& renderer = Application::renderer();

  renderer->setMultiSampling(config->get("antiAliasing").optBool().value(false) ? 4 : 0);
  renderer->setMainHDR(config->get("hdr").optBool().value(true));
  renderer->switchEffectConfig("interface");

  if (auto interfaceScale = config->get("interfaceScale").optFloat().value(); interfaceScale != 0)
    m_guiContext->setInterfaceScale(interfaceScale);
  else if (m_guiContext->windowWidth() >= m_crossoverRes[0] && m_guiContext->windowHeight() >= m_crossoverRes[1])
    m_guiContext->setInterfaceScale(m_maxInterfaceScale);
  else
    m_guiContext->setInterfaceScale(m_minInterfaceScale);

  if (m_state == MainAppState::Mods || m_state == MainAppState::Splash) {
    m_cinematicOverlay->render();

  } else if (m_state == MainAppState::Title) {
    m_titleScreen->render();
    m_cinematicOverlay->render();

  } else if (m_state > MainAppState::Title) {
    WorldClientPtr worldClient = m_universeClient->worldClient();
    if (worldClient) {
      auto totalStart = Time::monotonicMicroseconds();
      renderer->switchEffectConfig("world");
      auto clientStart = totalStart;
      {
        TileSectorArrayObserver::Frame frame(BehaviorLab::staticVectorScene(),
            m_behaviorReady && !BehaviorLab::hasPendingFrame());
        worldClient->render(m_renderData, TilePainter::BorderTileSize);
      }
      if (BehaviorLab::staticVectorScene() && m_behaviorReady
          && !BehaviorLab::hasPendingFrame() && !m_renderData.isFullbright)
        BehaviorLab::prepareStaticVectorFrame(m_renderData, m_behaviorStage, worldClient.get(), m_behaviorMaterial);
      LogMap::set("client_render_world_client", strf(u8"{:05d}\u00b5s", Time::monotonicMicroseconds() - clientStart));

      if (BehaviorLab::enabled() && m_behaviorRaycastRoom)
        prepareBehaviorRaycastFrame();
      if (BehaviorLab::enabled() && m_behaviorEncodingRoom)
        prepareBehaviorEncodingFrame();
      if (BehaviorLab::enabled() && m_behaviorSha256Room)
        prepareBehaviorSha256Frame();
      if (BehaviorLab::enabled() && m_behaviorVlqRoom)
        prepareBehaviorVlqFrame();
      if (BehaviorLab::enabled() && m_behaviorBytesRoom)
        prepareBehaviorBytesFrame();
      if (BehaviorLab::enabled() && m_behaviorUnicodeRoom)
        prepareBehaviorUnicodeFrame();
      if (BehaviorLab::enabled() && m_behaviorShellRoom)
        prepareBehaviorShellFrame();
      if (BehaviorLab::enabled() && m_behaviorJsonPatchRoom)
        prepareBehaviorJsonPatchFrame();
      if (BehaviorLab::enabled() && m_behaviorJsonPathRoom)
        prepareBehaviorJsonPathFrame();
      if (BehaviorLab::enabled() && m_behaviorAssetPathRoom)
        prepareBehaviorAssetPathFrame();
      if (BehaviorLab::enabled() && m_behaviorRandomMwcRoom)
        prepareBehaviorRandomMwcFrame();
      if (BehaviorLab::enabled() && m_behaviorCompressionRoom)
        prepareBehaviorCompressionFrame();
      if (BehaviorLab::enabled() && m_behaviorOptionParserRoom)
        prepareBehaviorOptionParserFrame();
      if (BehaviorLab::enabled() && m_behaviorZstdRoom)
        prepareBehaviorZstdFrame();
      if (BehaviorLab::enabled() && m_behaviorPathEmbedRoom)
        prepareBehaviorPathEmbedFrame();
      if (BehaviorLab::enabled() && m_behaviorBufferRoom)
        prepareBehaviorBufferFrame();
      if (BehaviorLab::enabled() && m_behaviorDataStreamRoom)
        prepareBehaviorDataStreamFrame();
      if (BehaviorLab::enabled() && m_behaviorHostAddressRoom)
        prepareBehaviorHostAddressFrame();
      if (BehaviorLab::enabled() && m_behaviorLruRoom && m_behaviorReady
          && !BehaviorLab::hasPendingFrame() && !m_renderData.isFullbright)
        BehaviorLab::prepareLruFrame(m_renderData, m_behaviorStage);
      if (BehaviorLab::enabled() && BehaviorLab::ttlScene() && m_behaviorReady
          && !BehaviorLab::hasPendingFrame() && !m_renderData.isFullbright
          && BehaviorLab::ttlReady(m_behaviorStage))
        BehaviorLab::prepareTtlFrame(m_renderData, m_behaviorStage);

      if (BehaviorLab::idMapScene() && m_behaviorReady
          && !BehaviorLab::hasPendingFrame() && !m_renderData.isFullbright)
        BehaviorLab::prepareIdMapFrame(m_renderData, m_behaviorStage, m_universeClient->mainPlayer());
      if (BehaviorLab::weightedPoolScene() && m_behaviorReady
          && !BehaviorLab::hasPendingFrame() && !m_renderData.isFullbright)
        BehaviorLab::prepareWeightedPoolFrame(m_renderData, m_behaviorStage);

      if (BehaviorLab::enabled() && m_behaviorStringViewRoom && m_behaviorReady
          && !BehaviorLab::hasPendingFrame() && !m_renderData.isFullbright) {
        // The immutable overlay PNG follows the ordinary world image path.
        auto drawable = Drawable::makeImage("/behaviorlab/string-view.png?setcolor=123456",
            16.0f / TilePixels, true, Vec2F(64, 48));
        drawable.fullbright = true;
        m_renderData.foregroundOverlays.append(std::move(drawable));
      }

      auto paintStart = Time::monotonicMicroseconds();
      m_worldPainter->render(m_renderData, [&]() -> bool {
        m_behaviorLightingCompleted = worldClient->waitForLighting(&m_renderData);
        return m_behaviorLightingCompleted;
      });
      if (BehaviorLab::staticVectorScene()) BehaviorLab::staticVectorPainterSubmitted();
      LogMap::set("client_render_world_painter", strf(u8"{:05d}\u00b5s", Time::monotonicMicroseconds() - paintStart));
      LogMap::set("client_render_world_total", strf(u8"{:05d}\u00b5s", Time::monotonicMicroseconds() - totalStart));
      
      auto size = Vec2F(renderer->screenSize());
      auto quad = renderFlatRect(RectF::withSize(size / -2, size), Vec4B::filled(0), 0.0f);
      for (auto& layer : m_postProcessLayers) {
        if (layer.group ? layer.group->enabled : true) {
          for (unsigned i = 0; i < layer.passes; i++) {
            for (auto& effect : layer.effects) {
              renderer->switchEffectConfig(effect);
              renderer->render(quad);
            }
          }
        }
      }
    }
    renderer->switchEffectConfig("interface");
    auto start = Time::monotonicMicroseconds();
    if (!BehaviorLab::enabled()) {
      m_mainInterface->renderInWorldElements();
      m_mainInterface->render();
      m_cinematicOverlay->render();
    } else {
      if ((m_behaviorUnicodeRoom && !m_behaviorUnicodeProof.isNull())
          || (m_behaviorShellRoom && !m_behaviorShellProof.isNull())
          || (m_behaviorJsonPatchRoom && !m_behaviorJsonPatchProof.isNull())
          || (m_behaviorJsonPathRoom && !m_behaviorJsonPathProof.isNull())
          || (m_behaviorAssetPathRoom && !m_behaviorAssetPathProof.isNull())
          || (m_behaviorRandomMwcRoom && !m_behaviorRandomMwcProof.isNull())
          || (m_behaviorCompressionRoom && !m_behaviorCompressionProof.isNull())
          || (m_behaviorZstdRoom && !m_behaviorZstdProof.isNull())
          || (m_behaviorPathEmbedRoom && !m_behaviorPathEmbedProof.isNull())
          || (m_behaviorBufferRoom && !m_behaviorBufferProof.isNull())
          || (m_behaviorDataStreamRoom && !m_behaviorDataStreamProof.isNull())
          || (m_behaviorHostAddressRoom && !m_behaviorHostAddressProof.isNull())
          || (m_behaviorOptionParserRoom && !m_behaviorOptionParserProof.isNull())) {
        // Normal Font -> TextPainter -> GPU glyph path; only ASCII coverage is
        // claimed. Screen-space coordinates avoid the 64px world-image area.
        m_guiContext->clearTextStyle();
        m_guiContext->setDefaultFont();
        m_guiContext->setFontSize((m_behaviorPathEmbedRoom || m_behaviorBufferRoom || m_behaviorZstdRoom || m_behaviorHostAddressRoom || m_behaviorDataStreamRoom) ? 8 : 16, 1.0f);
        m_guiContext->setFontColor(Vec4B(255, 255, 255, 255));
        m_guiContext->setFontMode(FontMode::Normal);
        m_guiContext->setFontProcessingDirectives("");
        m_guiContext->renderText(m_behaviorPathEmbedRoom ? m_behaviorPathEmbedProof.get("visual").getString("label")
            : m_behaviorBufferRoom ? m_behaviorBufferProof.get("visual").getString("label")
            : m_behaviorDataStreamRoom ? m_behaviorDataStreamProof.get("visual").getString("label")
            : m_behaviorHostAddressRoom ? m_behaviorHostAddressProof.get("visual").getString("label")
            : m_behaviorOptionParserRoom ? m_behaviorOptionParserProof.get("visual").getString("label")
            : m_behaviorJsonPatchRoom ? m_behaviorJsonPatchProof.get("visual").getString("label")
            : m_behaviorZstdRoom ? m_behaviorZstdProof.get("visual").getString("label")
            : m_behaviorCompressionRoom ? m_behaviorCompressionProof.get("visual").getString("label")
            : m_behaviorRandomMwcRoom ? m_behaviorRandomMwcProof.get("visual").getString("label")
            : m_behaviorAssetPathRoom ? m_behaviorAssetPathProof.get("visual").getString("label")
            : m_behaviorJsonPathRoom ? m_behaviorJsonPathProof.get("visual").getString("label")
            : m_behaviorShellRoom ? m_behaviorShellProof.get("visual").getString("label")
            : m_behaviorUnicodeProof.get("assets").getString("label"),
            TextPositioning(Vec2F(m_guiContext->windowSize()) * 0.5f + Vec2F(m_behaviorShellRoom ? -25 : -35, 70)));
        m_guiContext->clearTextStyle();
      }
      if (m_behaviorLruRoom && m_behaviorReady && !BehaviorLab::hasPendingFrame()
          && !m_renderData.isFullbright)
        BehaviorLab::renderLruLabel(*m_guiContext);
      if (BehaviorLab::enabled() && BehaviorLab::ttlScene() && m_behaviorReady
          && !BehaviorLab::hasPendingFrame() && !m_renderData.isFullbright
          && BehaviorLab::ttlFramePrepared(m_behaviorStage))
        BehaviorLab::renderTtlLabel(*m_guiContext);
      if (BehaviorLab::weightedPoolScene() && m_behaviorReady
          && !BehaviorLab::hasPendingFrame() && !m_renderData.isFullbright
          && BehaviorLab::weightedPoolFramePrepared(m_behaviorStage))
        BehaviorLab::renderWeightedPoolLabel(*m_guiContext);
      if (BehaviorLab::idMapScene() && m_behaviorReady
          && !BehaviorLab::hasPendingFrame() && !m_renderData.isFullbright)
        BehaviorLab::renderIdMapLabel(*m_guiContext);
      if (m_behaviorTextScanRoom)
        renderBehaviorTextScanFrame();
      if (m_behaviorStringViewRoom)
        renderBehaviorStringViewFrame();
      renderBehaviorScenario();
    }
    LogMap::set("client_render_interface", strf(u8"{:05d}\u00b5s", Time::monotonicMicroseconds() - start));
  }

  if (!m_errorScreen->accepted())
    m_errorScreen->render();
}

catch (...) {
  try {
    if (BehaviorLab::staticVectorScene())
      BehaviorLab::restoreStaticVectorScene(m_universeServer.get(), m_universeClient ? m_universeClient->worldClient().get() : nullptr, false);
  } catch (...) {
    // Diagnostic cleanup must not replace the original render failure.
  }
  throw;
}

void ClientApplication::getAudioData(int16_t* sampleData, size_t frameCount) {
  if (m_mainMixer) {
    m_mainMixer->read(sampleData, frameCount, [&](int16_t* buffer, size_t frames, unsigned channels) {
      if (m_voice)
        m_voice->mix(buffer, frames, channels);
    });
  }
}

auto postProcessGroupsRoot = "postProcessGroups";

void ClientApplication::renderReload() {
  auto assets = m_root->assets();
  auto renderer = Application::renderer();

  auto loadEffectConfig = [&](String const& name) {
    String path = strf("/rendering/effects/{}.config", name);
    if (assets->assetExists(path)) {
      StringMap<String> shaders;
      auto config = assets->json(path);
      auto shaderConfig = config.getObject("effectShaders");
      for (auto& entry : shaderConfig) {
        if (entry.second.isType(Json::Type::String)) {
          String shader = entry.second.toString();
          if (!shader.hasChar('\n')) {
            auto shaderBytes = assets->bytes(AssetPath::relativeTo(path, shader),true);
            shader = std::string(shaderBytes->ptr(), shaderBytes->size());
          }
          shaders[entry.first] = shader;
        }
      }

      renderer->loadEffectConfig(name, config, shaders);
    } else
      Logger::warn("No rendering config found for renderer with id '{}'", renderer->rendererId());
  };

  renderer->loadConfig(assets->json("/rendering/opengl.config"));
  
  loadEffectConfig("world");
  
  // define post process groups and set them to be enabled/disabled based on config
  
  auto config = m_root->configuration();
  if (!config->get(postProcessGroupsRoot).isType(Json::Type::Object))
    config->set(postProcessGroupsRoot, JsonObject());
  auto groupsConfig = config->get(postProcessGroupsRoot);
  
  m_postProcessGroups.clear();
  auto postProcessGroups = assets->json("/client.config:postProcessGroups").toObject();
  for (auto& pair : postProcessGroups) {
    auto name = pair.first;
    auto groupConfig = groupsConfig.opt(name);
    auto def = pair.second.getBool("enabledDefault",true);
    if (!groupConfig)
      config->setPath(strf("{}.{}", postProcessGroupsRoot, name),JsonObject());
    m_postProcessGroups.add(name,PostProcessGroup{ groupConfig ? groupConfig.value().getBool("enabled", def) : def });
  }
  
  // define post process layers and optionally assign them to groups
  m_postProcessLayers.clear();
  m_labelledPostProcessLayers.clear();
  auto postProcessLayers = assets->json("/client.config:postProcessLayers").toArray();
  for (auto& layer : postProcessLayers) {
    auto effects = jsonToStringList(layer.getArray("effects"));
    for (auto& effect : effects)
      loadEffectConfig(effect);
    PostProcessGroup* group = nullptr;
    auto gname = layer.optString("group");
    if (gname) {
      group = &m_postProcessGroups.get(gname.value());
    }
    // I'd think a string map for all of these would be better, but the order does matter here, and does make sense to depend on mod priority, so...
    // guess a string map of indices works
    // I tried pointers but for whatever reason the behaviour was highly inconsistent and only worked after reload...
    auto label = layer.optString("name");
    if (label) {
      m_labelledPostProcessLayers.add(label.value(),m_postProcessLayers.count());
    }
    m_postProcessLayers.append(PostProcessLayer{ std::move(effects), (unsigned)layer.getUInt("passes", 1), group });
  }

  loadEffectConfig("interface");
}

void ClientApplication::setPostProcessLayerPasses(String const& layer, unsigned const& passes) {
  m_postProcessLayers.at(m_labelledPostProcessLayers.get(layer)).passes = passes;
}
void ClientApplication::setPostProcessGroupEnabled(String const& group, bool const& enabled, Maybe<bool> const& save) {
  m_postProcessGroups.get(group).enabled = enabled;
  if (save && save.value())
    m_root->configuration()->setPath(strf("{}.{}.enabled", postProcessGroupsRoot, group),enabled);
}
bool ClientApplication::postProcessGroupEnabled(String const& group) {
  return m_postProcessGroups.get(group).enabled;
}

Json ClientApplication::postProcessGroups() {
  return m_root->assets()->json("/client.config:postProcessGroups");
}

unsigned ClientApplication::framesSkipped() const {
  return m_framesSkipped;
}

void ClientApplication::changeState(MainAppState newState) {
  MainAppState oldState = m_state;
  m_state = newState;
  auto& app = appController();

  if (m_state == MainAppState::Quit)
    app->quit();

  if (newState == MainAppState::Mods)
    m_cinematicOverlay->load(m_root->assets()->json("/cinematics/mods/modloading.cinematic"));

  if (newState == MainAppState::Splash) {
    m_cinematicOverlay->load(m_root->assets()->json("/cinematics/splash.cinematic"));
    m_rootLoader = Thread::invoke("Async root loader", [this]() {
        m_root->fullyLoad();
      });
  }

  if (oldState > MainAppState::Title && m_state <= MainAppState::Title) {
    if (BehaviorLab::idMapScene()) BehaviorLab::restoreIdMapStatus();
    if (m_universeClient)
      m_universeClient->disconnect();

    if (m_universeServer) {
      m_universeServer->stop();
      m_universeServer->join();
      m_universeServer.reset();
    }
    m_cinematicOverlay->stop();

    // Clear HTTP trust request callback
    LuaBindings::clearHttpTrustRequestCallback();

    m_mainInterface.reset();

    m_voice->clearSpeakers();

    if (auto p2pNetworkingService = app->p2pNetworkingService()) {
      p2pNetworkingService->setJoinUnavailable();
      p2pNetworkingService->setAcceptingP2PConnections(false);
    }
  }

  if (oldState > MainAppState::Title && m_state == MainAppState::Title) {
    m_titleScreen->resetState();
    m_mainMixer->setUniverseClient({});
  }
  if (oldState >= MainAppState::Title && m_state < MainAppState::Title) {
    m_playerStorage.reset();

    if (m_statistics) {
      m_statistics->writeStatistics();
      m_statistics.reset();
    }

    m_universeClient.reset();
    m_mainMixer->setUniverseClient({});
    m_titleScreen.reset();
  }

  if (oldState < MainAppState::Title && m_state >= MainAppState::Title) {
    if (m_rootLoader)
      m_rootLoader.finish();

    m_cinematicOverlay->stop();

    m_playerStorage = make_shared<PlayerStorage>(m_root->toStoragePath("player"));
    m_statistics = make_shared<Statistics>(m_root->toStoragePath("player"), app->statisticsService());
    m_universeClient = make_shared<UniverseClient>(m_playerStorage, m_statistics, m_root->toStoragePath("universeclient"));

    m_universeClient->setLuaCallbacks("universe", LuaBindings::makeUniverseClientCallbacks(m_universeClient.get()));
    m_universeClient->setLuaCallbacks("input", LuaBindings::makeInputCallbacks());
    m_universeClient->setLuaCallbacks("voice", LuaBindings::makeVoiceCallbacks());
    m_universeClient->setLuaCallbacks("camera", LuaBindings::makeCameraCallbacks(&m_worldPainter->camera()));
    m_universeClient->setLuaCallbacks("renderer", LuaBindings::makeRenderingCallbacks(this));

    Json alwaysAllow = m_root->configuration()->getPath("safe.alwaysAllowClipboard");
    m_universeClient->setLuaCallbacks("clipboard", LuaBindings::makeClipboardCallbacks(app, alwaysAllow && alwaysAllow.toBool()));

    auto heldScriptPanes = make_shared<List<MainInterface::ScriptPaneInfo>>();

    m_universeClient->playerReloadPreCallback() = [&, heldScriptPanes](bool resetInterface) {
      if (!resetInterface)
        return;

      m_mainInterface->takeScriptPanes(*heldScriptPanes);
    };

    m_universeClient->playerReloadCallback() = [&, heldScriptPanes](bool resetInterface) {
      auto paneManager = m_mainInterface->paneManager();
      if (auto inventory = paneManager->registeredPane<InventoryPane>(MainInterfacePanes::Inventory))
        inventory->clearChangedSlots();

      if (resetInterface) {
        m_mainInterface->reviveScriptPanes(*heldScriptPanes);
        heldScriptPanes->clear();
      }
    };

    m_mainMixer->setUniverseClient(m_universeClient);
    m_titleScreen = make_shared<TitleScreen>(m_playerStorage, m_mainMixer->mixer(), m_universeClient);
    if (auto renderer = Application::renderer())
      m_titleScreen->renderInit(renderer);
  }

  if (m_state == MainAppState::Title) {
    auto configuration = m_root->configuration();

    if (m_pendingMultiPlayerConnection) {
      if (auto address = m_pendingMultiPlayerConnection->server.ptr<HostAddressWithPort>()) {
        m_titleScreen->setMultiPlayerAddress(toString(address->address()));
        m_titleScreen->setMultiPlayerPort(toString(address->port()));
        m_titleScreen->setMultiPlayerAccount(configuration->getPath("title.multiPlayerAccount").toString());
        m_titleScreen->setMultiPlayerForceLegacy(configuration->getPath("title.multiPlayerForceLegacy").optBool().value(false));
        m_titleScreen->goToMultiPlayerSelectCharacter(false);
      } else {
        m_titleScreen->goToMultiPlayerSelectCharacter(true);
      }
    } else {
      m_titleScreen->setMultiPlayerAddress(configuration->getPath("title.multiPlayerAddress").toString());
      m_titleScreen->setMultiPlayerPort(configuration->getPath("title.multiPlayerPort").toString());
      m_titleScreen->setMultiPlayerAccount(configuration->getPath("title.multiPlayerAccount").toString());
      m_titleScreen->setMultiPlayerForceLegacy(configuration->getPath("title.multiPlayerForceLegacy").optBool().value(false));
    }
  }

  if (m_state > MainAppState::Title) {
    if (BehaviorLab::enabled()) {
      // Factory defaults, a fixed identity/UUID and isolated PlayerStorage avoid
      // selecting or mutating any existing character.
      auto factory = m_root->playerFactory();
      auto character = factory->create()->diskStore().set("uuid", "00000000000000000000000000000042");
      m_player = factory->diskLoadPlayer(character);
      m_player->setName("Behavior Lab");
      m_player->setAdmin(true);
      m_player->log()->setIntroComplete(true);
      m_playerStorage->savePlayer(m_player);
    } else if (m_titleScreen->currentlySelectedPlayer()) {
      m_player = m_titleScreen->currentlySelectedPlayer();
    } else {
      if (auto uuid = m_playerStorage->playerUuidAt(0))
        m_player = m_playerStorage->loadPlayer(*uuid);

      if (!m_player) {
        setError("Error loading player!");
        return;
      }
    }

    m_mainMixer->setUniverseClient(m_universeClient);
    m_universeClient->setMainPlayer(m_player);
    m_cinematicOverlay->setPlayer(m_player);
    m_timeSinceJoin = (int64_t)Time::millisecondsSinceEpoch() / 1000;

    auto assets = m_root->assets();
    String loadingCinematic = assets->json("/client.config:loadingCinematic").toString();
    m_cinematicOverlay->load(assets->json(loadingCinematic));
    if (!m_player->log()->introComplete()) {
      String introCinematic = assets->json("/client.config:introCinematic").toString();
      introCinematic = introCinematic.replaceTags(StringMap<String>{{"species", m_player->species()}});
      m_player->setPendingCinematic(Json(introCinematic));
    } else {
      m_player->setPendingCinematic(Json());
    }

    if (m_state == MainAppState::MultiPlayer) {
      PacketSocketUPtr packetSocket;

      auto multiPlayerConnection = m_pendingMultiPlayerConnection.take();

      if (auto address = multiPlayerConnection.server.ptr<HostAddressWithPort>()) {
        try {
          packetSocket = TcpPacketSocket::open(TcpSocket::connectTo(*address));
        } catch (StarException const& e) {
          setError(strf("Join failed! Error connecting to '{}'", *address), e);
          return;
        }

      } else {
        auto p2pPeerId = multiPlayerConnection.server.ptr<P2PNetworkingPeerId>();

        if (auto p2pNetworkingService = app->p2pNetworkingService()) {
          auto result = p2pNetworkingService->connectToPeer(*p2pPeerId);
          if (result.isLeft()) {
            setError(strf("Cannot join peer: {}", result.left()));
            return;
          } else {
            packetSocket = P2PPacketSocket::open(std::move(result.right()));
          }
        } else {
          setError("Internal error, no p2p networking service when joining p2p networking peer");
          return;
        }
      }

      bool allowAssetsMismatch = m_root->configuration()->get("allowAssetsMismatch").toBool();
      if (auto errorMessage = m_universeClient->connect(UniverseConnection(std::move(packetSocket)), allowAssetsMismatch,
            multiPlayerConnection.account, multiPlayerConnection.password, multiPlayerConnection.forceLegacy)) {
        setError(*errorMessage);
        return;
      }

      if (auto address = multiPlayerConnection.server.ptr<HostAddressWithPort>())
        m_currentRemoteJoin = *address;
      else
        m_currentRemoteJoin.reset();

    } else {
      if (!m_universeServer) {
        try {
          m_universeServer = make_shared<UniverseServer>(m_root->toStoragePath("universe"),true);
          m_universeServer->start();
        } catch (StarException const& e) {
          setError("Unable to start local server", e);
          return;
        }
      }

      if (auto errorMessage = m_universeClient->connect(m_universeServer->addLocalClient(), "", "")) {
        setError(strf("Error connecting locally: {}", *errorMessage));
        return;
      }
    }

    m_titleScreen->stopMusic();

    m_universeClient->restartLua();
    m_mainInterface = make_shared<MainInterface>(m_universeClient, m_worldPainter, m_cinematicOverlay);
    m_universeClient->setLuaCallbacks("interface", LuaBindings::makeInterfaceCallbacks(m_mainInterface.get()));
    m_universeClient->setLuaCallbacks("chat", LuaBindings::makeChatCallbacks(m_mainInterface.get(), m_universeClient.get()));
    m_universeClient->setLuaCallbacks("celestial", LuaBindings::makeCelestialCallbacks(m_universeClient.get()));
    m_universeClient->setLuaCallbacks("team", LuaBindings::makeTeamClientCallbacks(m_universeClient->teamClient().get()));
    m_universeClient->setLuaCallbacks("world", LuaBindings::makeWorldCallbacks(m_universeClient->worldClient().get()));

    LuaBindings::setHttpTrustRequestCallback([mainInterface = m_mainInterface.get(), universeClient = m_universeClient.get()](String domain) {
      universeClient->executeActionLater([mainInterface,domain](Universe*) {
        const auto paneManager = mainInterface->paneManager();
        const auto httpTrustDialog = paneManager->registeredPane<HttpTrustDialog>(MainInterfacePanes::HttpTrustDialog);

        httpTrustDialog->displayRequest(domain, [domain](const HttpTrustReply reply, bool /*remember*/) {
          const bool allowed = (reply == HttpTrustReply::Allow);
          LuaBindings::handleHttpTrustReply(domain, allowed);
        });
        paneManager->displayRegisteredPane(MainInterfacePanes::HttpTrustDialog);
      });
    });


    m_mainInterface->displayDefaultPanes();
    m_universeClient->startLuaScripts();

    m_mainMixer->setWorldPainter(m_worldPainter);

    if (auto renderer = Application::renderer()) {
      m_worldPainter->renderInit(renderer);
    }
  }
}

void ClientApplication::setError(String const& error) {
  Logger::error(error.utf8Ptr());
  m_errorScreen->setMessage(error);
  m_titleScreen->resetState();
  changeState(MainAppState::Title);
}

void ClientApplication::setError(String const& error, std::exception const& e) {
  Logger::error("{}\n{}", error, outputException(e, true));
  m_errorScreen->setMessage(strf("{}\n{}", error, outputException(e, false)));
  m_titleScreen->resetState();
  changeState(MainAppState::Title);
}

void ClientApplication::loadMods() {
  auto ugcService = appController()->userGeneratedContentService();
  auto configuration = m_root->configuration();
  bool includeUGC = configuration->get("includeUGC", m_root->settings().includeUGC).toBool();
  if (ugcService && includeUGC) {
    StringList modDirectories;
    Logger::info("Checking for user generated content...");
    for (auto& contentId : ugcService->subscribedContentIds()) {
      if (auto contentDirectory = ugcService->contentDownloadDirectory(contentId)) {
        Logger::info("Loading mods from user generated content with id '{}' from directory '{}'", contentId, *contentDirectory);
        modDirectories.append(*contentDirectory);
      } else {
        Logger::warn("User generated content with id '{}' is not available", contentId);
      }
    }

    if (modDirectories.empty()) {
      Logger::info("No subscribed user generated content");
    } else {
      Root::singleton().loadMods(modDirectories, false);
      auto assets = m_root->assets();
    }
  }
}

void ClientApplication::updateSteamFlatpakWarning(float) {
  if (m_errorScreen->accepted())
    changeState(MainAppState::Mods);
}

void ClientApplication::updateMods(float dt) {
  m_cinematicOverlay->update(dt);
  auto ugcService = appController()->userGeneratedContentService();
  auto configuration = m_root->configuration();
  bool includeUGC = configuration->get("includeUGC", m_root->settings().includeUGC).toBool();
  if (ugcService && includeUGC) {
    // Prevent unnecessary log spam when UGC needs to be downloaded
    if (!m_loggedUGCCheck) {
      Logger::info("Checking for user generated content updates...");
      m_loggedUGCCheck = true;
    }
    
    if (ugcService->triggerContentDownload() == UserGeneratedContentService::UGCState::NoDownload) {
      changeState(MainAppState::Splash);
    } else {
      if (ugcService->triggerContentDownload() == UserGeneratedContentService::UGCState::Finished) {
        Logger::info("Loading updated user generated content...");
        StringList modDirectories;
        for (auto& contentId : ugcService->subscribedContentIds()) {
          if (auto contentDirectory = ugcService->contentDownloadDirectory(contentId)) {
            Logger::info("Loading mods from user generated content with id '{}' from directory '{}'", contentId, *contentDirectory);
            modDirectories.append(*contentDirectory);
          } else {
            Logger::warn("User generated content with id '{}' is not available", contentId);
          }
        }

        if (modDirectories.empty()) {
          changeState(MainAppState::Splash);
        } else {
          Logger::info("Reloading to include updated user generated content");
          Root::singleton().loadMods(modDirectories);

          // We've just reloaded, so make sure to grab our config again!
          // If we don't do this, we'll be able to read modsWarningShown
          // just fine, but we won't be able to write it back to the file.
          configuration = m_root->configuration();
        }

        auto assets = m_root->assets();

        if (configuration->get("modsWarningShown").optBool().value()) {
          changeState(MainAppState::Splash);
        } else {
          configuration->set("modsWarningShown", true);
          m_errorScreen->setMessage(assets->json("/interface.config:modsWarningMessage").toString());
          changeState(MainAppState::ModsWarning);
        }
      }
    }
  } else {
    changeState(MainAppState::Splash);
  }
}

void ClientApplication::updateModsWarning(float) {
  if (m_errorScreen->accepted())
    changeState(MainAppState::Splash);
}

void ClientApplication::updateSplash(float dt) {
  m_cinematicOverlay->update(dt);
  if (!m_rootLoader.isRunning() && (BehaviorLab::enabled() || m_cinematicOverlay->completable() || m_cinematicOverlay->completed()))
    changeState(MainAppState::Title);
}

void ClientApplication::updateError(float) {
  if (m_errorScreen->accepted())
    changeState(MainAppState::Title);
}

void ClientApplication::updateTitle(float dt) {
  if (BehaviorLab::enabled()) {
    changeState(MainAppState::SinglePlayer);
    return;
  }
  m_cinematicOverlay->update(dt);

  m_titleScreen->update(dt);
  m_mainMixer->update(dt);
  m_mainMixer->setSpeed(GlobalTimescale);

  auto& app = appController();
  bool inputActive = m_titleScreen->textInputActive();
  m_input->setTextInputActive(inputActive);
  if (inputActive)
    app->setTextArea(m_titleScreen->paneManager()->keyboardCapturedWidget()->keyboardCaptureArea());
  else
    app->setTextArea();
  app->setAcceptingTextInput(inputActive);

  auto p2pNetworkingService = app->p2pNetworkingService();
  if (p2pNetworkingService) {
    auto getStateString = [](TitleState state) -> const char* {
      switch (state) {
        case TitleState::Main:
          return "In Main Menu";
        case TitleState::Options:
          return "In Options";
        case TitleState::Mods:
          return "In Mods";
        case TitleState::SinglePlayerSelectCharacter:
          return "Selecting a character for singleplayer";
        case TitleState::SinglePlayerCreateCharacter:
          return "Creating a character for singleplayer";
        case TitleState::MultiPlayerSelectCharacter:
          return "Selecting a character for multiplayer";
        case TitleState::MultiPlayerCreateCharacter:
          return "Creating a character for multiplayer";
        case TitleState::MultiPlayerConnect:
          return "Awaiting multiplayer connection info";
        case TitleState::StartSinglePlayer:
          return "Loading Singleplayer";
        case TitleState::StartMultiPlayer:
          return "Connecting to Multiplayer";
        default:
          return "";
      }
    };

    p2pNetworkingService->setActivityData("Not In Game", getStateString(m_titleScreen->currentState()), 0, {});
  }

  if (m_titleScreen->currentState() == TitleState::StartSinglePlayer) {
    changeState(MainAppState::SinglePlayer);

  } else if (m_titleScreen->currentState() == TitleState::StartMultiPlayer) {
    if (!m_pendingMultiPlayerConnection || m_pendingMultiPlayerConnection->server.is<HostAddressWithPort>()) {
      auto addressString = m_titleScreen->multiPlayerAddress().trim();
      auto portString = m_titleScreen->multiPlayerPort().trim();
      portString = portString.empty() ? toString(m_root->configuration()->get("gameServerPort").toUInt()) : portString;
      if (auto port = maybeLexicalCast<uint16_t>(portString)) {
        auto address = HostAddressWithPort::lookup(addressString, *port);
        if (address.isLeft()) {
          setError(address.left());
        } else {
          m_pendingMultiPlayerConnection = PendingMultiPlayerConnection{
            address.right(),
            m_titleScreen->multiPlayerAccount(),
            m_titleScreen->multiPlayerPassword(),
            m_titleScreen->multiPlayerForceLegacy()
          };

          auto configuration = m_root->configuration();
          configuration->setPath("title.multiPlayerAddress", m_titleScreen->multiPlayerAddress());
          configuration->setPath("title.multiPlayerPort", m_titleScreen->multiPlayerPort());
          configuration->setPath("title.multiPlayerAccount", m_titleScreen->multiPlayerAccount());
          configuration->setPath("title.multiPlayerForceLegacy", m_titleScreen->multiPlayerForceLegacy());

          changeState(MainAppState::MultiPlayer);
        }
      } else {
        setError(strf("invalid port: {}", portString));
      }
    } else {
      changeState(MainAppState::MultiPlayer);
    }

  } else if (m_titleScreen->currentState() == TitleState::Quit) {
    changeState(MainAppState::Quit);
  }
}

void ClientApplication::updateRunning(float dt) {
  try {
    auto& app = appController();
    auto worldClient = m_universeClient->worldClient();
    auto p2pNetworkingService = app->p2pNetworkingService();
    bool clientIPJoinable = m_root->configuration()->get("clientIPJoinable").toBool();
    bool clientP2PJoinable = m_root->configuration()->get("clientP2PJoinable").toBool();
    Maybe<pair<uint16_t, uint16_t>> party = make_pair(m_universeClient->players(), m_universeClient->maxPlayers());

    if (m_state == MainAppState::MultiPlayer) {
      if (p2pNetworkingService) {
        p2pNetworkingService->setAcceptingP2PConnections(false);
        if (clientP2PJoinable && m_currentRemoteJoin)
          p2pNetworkingService->setJoinRemote(*m_currentRemoteJoin);
        else
          p2pNetworkingService->setJoinUnavailable();
      }
    } else {
      m_universeServer->setListeningTcp(clientIPJoinable);
      if (p2pNetworkingService) {
        p2pNetworkingService->setAcceptingP2PConnections(clientP2PJoinable);
        if (clientP2PJoinable) {
          p2pNetworkingService->setJoinLocal(m_universeServer->maxClients());
        } else {
          p2pNetworkingService->setJoinUnavailable();
          party = {};
        }
      }
    }
    
    if (p2pNetworkingService) {
      auto getActivityDetail = [&](String const& tag) -> String {
        if (tag == "playerName")
          return Text::stripEscapeCodes(m_player->name());
        if (tag == "playerHealth")
          return toString(m_player->health());
        if (tag == "playerMaxHealth")
          return toString(m_player->maxHealth());
        if (tag == "playerEnergy")
          return toString(m_player->energy());
        if (tag == "playerMaxEnergy")
          return toString(m_player->maxEnergy());
        if (tag == "playerBreath")
          return toString(m_player->breath());
        if (tag == "playerMaxBreath")
          return toString(m_player->maxBreath());
        if (tag == "playerXPos")
          return toString(round(m_player->position().x()));
        if (tag == "playerYPos")
          return toString(round(m_player->position().y()));
        if (tag == "worldName") {
          if (m_universeClient->clientContext()->playerWorldId().is<ClientShipWorldId>())
            return "Player Ship";
          else if (WorldTemplate const* worldTemplate = worldClient ? worldClient->currentTemplate().get() : nullptr) {
            auto worldName = worldTemplate->worldName();
            if (worldName.empty())
              return "In World";
            else
              return Text::stripEscapeCodes(worldName);
          }
          else
            return "Nowhere";
        }
        return "";
      };

      String finalDetails = "";
      Json activityDetails = m_root->configuration()->getPath("discord.activityDetails");
      if (activityDetails.isType(Json::Type::Array)) {
        StringList detailsList;
        for (auto& detail : activityDetails.iterateArray())
          detailsList.append(getActivityDetail(*detail.stringPtr()));
        finalDetails = detailsList.join("\n");
      } else if (activityDetails.isType(Json::Type::String))
        finalDetails = activityDetails.toString().lookupTags(getActivityDetail);

      p2pNetworkingService->setActivityData("In Game", finalDetails.utf8Ptr(), m_timeSinceJoin, party);
    }

    if (!m_mainInterface->inputFocus() && !m_cinematicOverlay->suppressInput()) {
      m_player->setShifting(isActionTaken(InterfaceAction::PlayerShifting));

      if (isActionTaken(InterfaceAction::PlayerRight))
        m_player->moveRight();
      if (isActionTaken(InterfaceAction::PlayerLeft))
        m_player->moveLeft();
      if (isActionTaken(InterfaceAction::PlayerUp))
        m_player->moveUp();
      if (isActionTaken(InterfaceAction::PlayerDown))
        m_player->moveDown();
      if (isActionTaken(InterfaceAction::PlayerJump))
        m_player->jump();

      if (isActionTaken(InterfaceAction::PlayerTechAction1))
        m_player->special(1);
      if (isActionTaken(InterfaceAction::PlayerTechAction2))
        m_player->special(2);
      if (isActionTaken(InterfaceAction::PlayerTechAction3))
        m_player->special(3);

      if (isActionTakenEdge(InterfaceAction::PlayerInteract))
        m_player->beginTrigger();
      else if (!isActionTaken(InterfaceAction::PlayerInteract))
        m_player->endTrigger();

      if (isActionTakenEdge(InterfaceAction::PlayerDropItem))
        m_player->dropItem();

      if (isActionTakenEdge(InterfaceAction::EmoteBlabbering))
        m_player->addEmote(HumanoidEmote::Blabbering);
      if (isActionTakenEdge(InterfaceAction::EmoteShouting))
        m_player->addEmote(HumanoidEmote::Shouting);
      if (isActionTakenEdge(InterfaceAction::EmoteHappy))
        m_player->addEmote(HumanoidEmote::Happy);
      if (isActionTakenEdge(InterfaceAction::EmoteSad))
        m_player->addEmote(HumanoidEmote::Sad);
      if (isActionTakenEdge(InterfaceAction::EmoteNeutral))
        m_player->addEmote(HumanoidEmote::NEUTRAL);
      if (isActionTakenEdge(InterfaceAction::EmoteLaugh))
        m_player->addEmote(HumanoidEmote::Laugh);
      if (isActionTakenEdge(InterfaceAction::EmoteAnnoyed))
        m_player->addEmote(HumanoidEmote::Annoyed);
      if (isActionTakenEdge(InterfaceAction::EmoteOh))
        m_player->addEmote(HumanoidEmote::Oh);
      if (isActionTakenEdge(InterfaceAction::EmoteOooh))
        m_player->addEmote(HumanoidEmote::OOOH);
      if (isActionTakenEdge(InterfaceAction::EmoteBlink))
        m_player->addEmote(HumanoidEmote::Blink);
      if (isActionTakenEdge(InterfaceAction::EmoteWink))
        m_player->addEmote(HumanoidEmote::Wink);
      if (isActionTakenEdge(InterfaceAction::EmoteEat))
        m_player->addEmote(HumanoidEmote::Eat);
      if (isActionTakenEdge(InterfaceAction::EmoteSleep))
        m_player->addEmote(HumanoidEmote::Sleep);

      if (int newZoomDirection = (int)m_input->bindHeld("opensb", "zoomIn") - (int)m_input->bindHeld("opensb", "zoomOut"))
        m_cameraZoomDirection = newZoomDirection;
    }
    if (m_cameraZoomDirection != 0) {
      const float threshold = 0.01f;
      bool goingIn = m_cameraZoomDirection == 1;
      auto config = m_root->configuration();
      float curZoom = config->get("zoomLevel").toFloat(),
            newZoom = max(1.f, curZoom * powf(1.f + (float)m_cameraZoomDirection * 0.5f, min(1.f, dt * 5.f))),
            intZoom = max(1.f, (goingIn ? floor(curZoom) : ceil(curZoom)) + m_cameraZoomDirection);
      bool pastInt = goingIn ? newZoom + threshold > intZoom
                             : newZoom - threshold < intZoom;
      if (pastInt) {
        float intNewZoom = goingIn ? ceil(newZoom) : floor(newZoom);
        newZoom = lerp(clamp(abs(intZoom - newZoom) - 1.f, 0.f, 1.f), intZoom, intNewZoom);
        m_cameraZoomDirection = 0;
      }
      config->set("zoomLevel", min(1000000.f, newZoom));
    }

    if (m_controllerInput && m_controllerLeftStick.magnitudeSquared() > 0.01f)
      m_player->setMoveVector(m_controllerLeftStick);
    else
      m_player->setMoveVector(Vec2F());

    m_voice->setInput(m_input->bindHeld("opensb", "pushToTalk"));
    DataStreamBuffer voiceData;
    voiceData.setByteOrder(ByteOrder::LittleEndian);
    //voiceData.writeBytes(VoiceBroadcastPrefix.utf8Bytes()); transmitting with SE compat for now
    bool needstoSendVoice = m_voice->send(voiceData, 5000);

    auto checkDisconnection = [this]() {
      if (!m_universeClient->isConnected()) {
        m_cinematicOverlay->stop();
        String errMessage;
        if (auto disconnectReason = m_universeClient->disconnectReason())
          errMessage = strf("You were disconnected from the server for the following reason:\n{}", *disconnectReason);
        else
          errMessage = "Client-server connection no longer valid!";
        setError(errMessage);
        changeState(MainAppState::Title);
        return true;
      }

      return false;
    };

    if (checkDisconnection())
      return;

    m_mainInterface->preUpdate(dt);
    m_universeClient->update(dt);

    if (checkDisconnection())
      return;

    if (worldClient) {
      m_worldPainter->update(dt);
      auto& broadcastCallback = worldClient->broadcastCallback();
      if (!broadcastCallback) {
        broadcastCallback = [&](PlayerPtr player, StringView broadcast) -> bool {
          auto& view = broadcast.utf8();
          if (view.rfind(VoiceBroadcastPrefix.utf8(), 0) != NPos) {
            auto entityId = player->entityId();
            auto speaker = m_voice->speaker(connectionForEntity(entityId));
            speaker->entityId = entityId;
            speaker->name = player->name();
            speaker->position = player->mouthPosition();
            m_voice->receive(speaker, view.substr(VoiceBroadcastPrefix.utf8Size()));
          }
          return true;
        };
      }

      if (worldClient->inWorld()) {
        if (needstoSendVoice) {
          auto signature = Curve25519::sign(voiceData.ptr(), voiceData.size());
          std::string_view signatureView((char*)signature.data(), signature.size());
          std::string_view audioDataView(voiceData.ptr(), voiceData.size());
          auto broadcast = strf("data\0voice\0{}{}"s, signatureView, audioDataView);
          worldClient->sendSecretBroadcast(broadcast, true, false); // Already compressed by Opus.
        }
        if (auto mainPlayer = m_universeClient->mainPlayer()) {
          auto localSpeaker = m_voice->localSpeaker();
          localSpeaker->position = mainPlayer->position();
          localSpeaker->entityId = mainPlayer->entityId();
          localSpeaker->name = mainPlayer->name();
        }
        m_voice->setLocalSpeaker(worldClient->connection());
      }
      worldClient->setInteractiveHighlightMode(isActionTaken(InterfaceAction::ShowLabels));
    }
    updateCamera(dt);

    m_cinematicOverlay->update(dt);
    m_mainInterface->update(dt);
    m_mainMixer->update(dt, m_cinematicOverlay->muteSfx(), m_cinematicOverlay->muteMusic());
    m_mainMixer->setSpeed(GlobalTimescale);

    bool inputActive = m_mainInterface->textInputActive();
    m_input->setTextInputActive(inputActive);
    if (inputActive)
      app->setTextArea(m_mainInterface->paneManager()->keyboardCapturedWidget()->keyboardCaptureArea());
    else
      app->setTextArea();
    app->setAcceptingTextInput(inputActive);

    for (auto const& interactAction : m_player->pullInteractActions())
      m_mainInterface->handleInteractAction(interactAction);

    if (m_universeServer) {
      if (auto p2pNetworkingService = app->p2pNetworkingService()) {
        for (auto& p2pClient : p2pNetworkingService->acceptP2PConnections())
          m_universeServer->addClient(UniverseConnection(P2PPacketSocket::open(std::move(p2pClient))));
      }

      m_universeServer->setPause(m_mainInterface->escapeDialogOpen());
    }

    Vec2F aimPosition = m_player->aimPosition();
    float fps = app->renderFps();
    LogMap::set("client_render_rate", strf("{:4.2f} FPS ({:4.2f}ms)", fps, (1.0f / app->renderFps()) * 1000.0f));
    LogMap::set("client_update_rate", strf("{:4.2f}Hz", app->updateRate()));
    LogMap::set("player_pos", strf("[ ^#f45;{:4.2f}^reset;, ^#49f;{:4.2f}^reset; ]", m_player->position()[0], m_player->position()[1]));
    LogMap::set("player_vel", strf("[ ^#f45;{:4.2f}^reset;, ^#49f;{:4.2f}^reset; ]", m_player->velocity()[0], m_player->velocity()[1]));
    LogMap::set("player_aim", strf("[ ^#f45;{:4.2f}^reset;, ^#49f;{:4.2f}^reset; ]", aimPosition[0], aimPosition[1]));
    if (auto world = m_universeClient->worldClient()) {
      auto aim = Vec2I::floor(aimPosition);
      LogMap::set("tile_liquid_level", toString(world->liquidLevel(aim).level));
      LogMap::set("tile_dungeon_id", world->isTileProtected(aim) ? strf("^red;{}", world->dungeonId(aim)) : toString(world->dungeonId(aim)));
    }

    if (m_mainInterface->currentState() == MainInterface::ReturnToTitle)
      changeState(MainAppState::Title);

  } catch (std::exception& e) {
    setError("Exception caught in client main-loop", e);
  }
}

bool ClientApplication::isActionTaken(InterfaceAction action) const {
  for (auto keyEvent : m_heldKeyEvents) {
    if (m_guiContext->actions(keyEvent).contains(action))
      return true;
  }

  return false;
}

bool ClientApplication::isActionTakenEdge(InterfaceAction action) const {
  for (auto keyEvent : m_edgeKeyEvents) {
    if (m_guiContext->actions(keyEvent).contains(action))
      return true;
  }

  return false;
}

// Client integration owns game-dependent consumers; the application library
// deliberately has no dependency on game/base or their Lua bindings.
namespace {
void lruRequire(bool condition, char const* message) {
  if (!condition) throw StarException(message);
}
struct LruConsumer {
  int stage = -1;
  Json proof;
  JsonArray events;
};
LruConsumer& lruConsumer() {
  static LruConsumer consumer;
  return consumer;
}
}

void BehaviorLab::prepareLruFrame(WorldRenderData& renderData, unsigned stage) {
  lruRequire(enabled() && configuration().getString("scenario") == "lru-room",
      "BehaviorLab: LRU consumer outside its issue-scoped scene");
  lruRequire(stage < 3 && !renderData.isFullbright, "BehaviorLab: invalid LRU render stage");
  auto& consumer = lruConsumer();
  if (int(stage) != consumer.stage) {
    lruRequire(int(stage) == consumer.stage + 1, "BehaviorLab: skipped/repeated LRU phase");
    auto assets = Root::singleton().assets();
    auto engine = LuaEngine::create();
    auto context = engine->createContext();
    context.setCallbacks("root", LuaBindings::makeRootCallbacks());
    context.load(*assets->bytes("/behaviorlab/lru-consumer.lua"), "/behaviorlab/lru-consumer.lua");
    LruCacheLab::begin();
    Json visual;
    try {
      visual = context.invokePath<Json>("proof", stage);
    } catch (...) {
      LruCacheLab::cancel();
      throw;
    }
    auto observed = LruCacheLab::finish();
    for (auto event : observed.iterateArray())
      consumer.events.append(event.set("index", consumer.events.size()).set("phase", stage));
    lruRequire(consumer.events.size() == (stage == 0 ? 22 : stage == 1 ? 25 : 27),
        "BehaviorLab: normal Lua LRU call count differs");
    auto color = visual.getArray("color");
    lruRequire(color.size() == 4, "BehaviorLab: LRU visual color missing");
    auto image = assets->image(visual.getString("imagePath"));
    lruRequire(image->size() == Vec2U(16, 16), "BehaviorLab: LRU Assets image dimensions differ");
    Vec4B expected(color[0].toUInt(), color[1].toUInt(), color[2].toUInt(), color[3].toUInt());
    for (unsigned y = 0; y < 16; ++y)
      for (unsigned x = 0; x < 16; ++x)
        lruRequire(image->get(x, y) == expected, "BehaviorLab: LRU normal Assets image color differs");
    consumer.proof = JsonObject{{"version", 1}, {"backend", LruCacheLab::backend()},
        {"selector", "STAR_USE_RUST_LRU_CACHE"}, {"scopeThread", "lua-calling-thread"},
        {"phase", stage}, {"events", consumer.events}, {"visual", visual},
        {"consumer", "normal-root.dungeonMetadata-Assets-DungeonDefinition"},
        {"imageConsumer", "normal-Assets-WorldPainter"}, {"labelConsumer", "normal-Font-TextPainter"}};
    consumer.stage = int(stage);
  }
  auto drawable = Drawable::makeImage(consumer.proof.get("visual").getString("imagePath"),
      2.0f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  renderData.foregroundOverlays.append(std::move(drawable));
}

void BehaviorLab::renderLruLabel(GuiContext& gui) {
  auto& consumer = lruConsumer();
  lruRequire(enabled() && !consumer.proof.isNull(), "BehaviorLab: missing LRU Font consumer");
  gui.clearTextStyle();
  gui.setDefaultFont();
  gui.setFontSize(8, 1.0f);
  gui.setFontColor(Vec4B(255, 255, 255, 255));
  gui.setFontMode(FontMode::Normal);
  gui.setFontProcessingDirectives("");
  gui.renderText(consumer.proof.get("visual").getString("label"),
      TextPositioning(Vec2F(gui.windowSize()) * 0.5f + Vec2F(-35, 70)));
  gui.clearTextStyle();
}

Json BehaviorLab::lruProof() {
  lruRequire(enabled() && !lruConsumer().proof.isNull(), "BehaviorLab: missing LRU phase receipt");
  return lruConsumer().proof;
}

namespace {
struct TtlConsumer {
  int stage = -1;
  int64_t deadline = 0;
  Json proof;
};
TtlConsumer& ttlConsumer() { static TtlConsumer value; return value; }
}
bool BehaviorLab::ttlScene() {
  return enabled() && configuration().getString("scenario", "") == "ttl-room";
}
bool BehaviorLab::ttlReady(unsigned stage) {
  return stage != 1 || Time::monotonicMilliseconds() >= ttlConsumer().deadline;
}
bool BehaviorLab::ttlFramePrepared(unsigned stage) {
  return ttlConsumer().stage == int(stage);
}
void BehaviorLab::prepareTtlFrame(WorldRenderData& renderData, unsigned stage) {
  lruRequire(ttlScene() && stage < 3 && !renderData.isFullbright, "BehaviorLab: invalid TTL scene");
  auto& consumer = ttlConsumer();
  if (consumer.stage != int(stage)) {
    lruRequire(int(stage) == consumer.stage + 1 && ttlReady(stage), "BehaviorLab: TTL phase/readiness");
    if (stage == 0) TtlCacheLab::begin();
    TtlCacheLab::setPhase(stage);
    if (stage == 1)
      const_cast<TenantDatabase&>(*Root::singleton().tenantDatabase()).cleanup();
    auto assets = Root::singleton().assets();
    auto engine = LuaEngine::create();
    auto context = engine->createContext();
    context.setCallbacks("root", LuaBindings::makeRootCallbacks());
    context.load(*assets->bytes("/behaviorlab/ttl-consumer.lua"), "/behaviorlab/ttl-consumer.lua");
    Json visual = context.invokePath<Json>("proof", stage);
    auto events = Root::singleton().tenantDatabase()->ttlLabHistory(stage == 2);
    if (stage == 0) {
      Json last;
      for (auto const& event : events.toArray())
        if (event.getBool("foreground") && event.getString("operation") == "get") last = event;
      lruRequire(!last.isNull(), "BehaviorLab: missing actual TTL get");
      for (auto const& entry : last.get("after").getArray("entries"))
        if (entry.getString("keyHex") == hexEncode("behavior-ttl-a", 14))
          consumer.deadline = entry.getInt("stamp") + last.get("after").getInt("ttl") + 1;
      lruRequire(consumer.deadline > 0, "BehaviorLab: missing actual TTL deadline");
    }
    consumer.proof = JsonObject{{"version", 1}, {"backend", TtlCacheLab::backend()},
        {"selector", "STAR_USE_RUST_TTL_CACHE"}, {"phase", stage},
        {"events", events}, {"visual", visual}, {"deadline", consumer.deadline},
        {"consumer", "normal-root.tenantConfig-TenantDatabase-Assets-Tenant"},
        {"imageConsumer", "normal-Assets-WorldPainter"}, {"labelConsumer", "normal-Font-TextPainter"},
        {"configuration", configuration()}};
    consumer.stage = int(stage);
  }
  auto drawable = Drawable::makeImage(consumer.proof.get("visual").getString("imagePath"),
      2.0f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  renderData.foregroundOverlays.append(std::move(drawable));
}
void BehaviorLab::renderTtlLabel(GuiContext& gui) {
  auto const& proof = ttlConsumer().proof;
  lruRequire(!proof.isNull(), "BehaviorLab: missing TTL Font proof");
  gui.clearTextStyle(); gui.setDefaultFont(); gui.setFontSize(8, 1.0f);
  gui.setFontColor(Vec4B(255, 255, 255, 255)); gui.setFontMode(FontMode::Normal);
  gui.setFontProcessingDirectives("");
  gui.renderText(proof.get("visual").getString("label"),
      TextPositioning(Vec2F(gui.windowSize()) * 0.5f + Vec2F(-35, 70)));
  gui.clearTextStyle();
}
Json BehaviorLab::ttlProof() {
  lruRequire(!ttlConsumer().proof.isNull(), "BehaviorLab: missing TTL proof");
  return ttlConsumer().proof;
}

namespace {
struct WeightedPoolConsumer {
  int stage = -1;
  Json proof;
};
WeightedPoolConsumer& weightedPoolConsumer() { static WeightedPoolConsumer value; return value; }
uint64_t weightedPoolCounter(unsigned mode, unsigned stage) {
#ifdef STAR_USE_RUST_WEIGHTED_POOL
  return sb_wp_count(mode, stage);
#else
  return 0;
#endif
}
Json weightedPoolCounters() {
  JsonArray modes;
  for (unsigned mode = 0; mode < 19; ++mode) {
    JsonArray stages;
    for (unsigned stage = 0; stage < 4; ++stage)
      stages.append(strf("{:016x}", weightedPoolCounter(mode, stage)));
    modes.append(std::move(stages));
  }
  return modes;
}
}
bool BehaviorLab::weightedPoolScene() {
  return enabled() && configuration().getString("scenario", "") == "weighted-pool-room";
}
bool BehaviorLab::weightedPoolFramePrepared(unsigned stage) {
  return weightedPoolConsumer().stage == int(stage);
}
void BehaviorLab::prepareWeightedPoolFrame(WorldRenderData& renderData, unsigned stage) {
  lruRequire(weightedPoolScene() && stage < 3 && !renderData.isFullbright,
      "BehaviorLab: invalid WeightedPool scene");
  auto& consumer = weightedPoolConsumer();
  if (!weightedPoolFramePrepared(stage)) {
    lruRequire(int(stage) == consumer.stage + 1, "BehaviorLab: skipped WeightedPool stage");
    auto assets = Root::singleton().assets();
    auto engine = LuaEngine::create();
    auto context = engine->createContext();
    context.setCallbacks("root", LuaBindings::makeRootCallbacks());
    context.load(*assets->bytes("/behaviorlab/weighted-consumer.lua"), "/behaviorlab/weighted-consumer.lua");
    // Warm lazy Root databases before the bracket: constructor/add observations
    // are startup work, NOT phase coverage. Do not sample treasure here.
    Root::singleton().treasureDatabase();
    Root::singleton().itemDatabase();
    // Main Lua-calling-thread ABI counters bracket ONLY the real callback run.
    auto before = weightedPoolCounters();
    Json visual = context.invokePath<Json>("proof", stage);
    auto after = weightedPoolCounters();
#ifdef STAR_USE_RUST_WEIGHTED_POOL
    char const* backend = "rust";
    unsigned nonfiltered = stage == 1 ? 2 : 3;
    for (unsigned mode : {9u, 12u, 17u, 18u}) {
      auto lo = std::stoull(before.get(mode).getString(0).utf8(), nullptr, 16);
      auto hi = std::stoull(after.get(mode).getString(0).utf8(), nullptr, 16);
      lruRequire(uint64_t(hi - lo) >= (mode == 9 ? nonfiltered + 1 : 3 * nonfiltered),
          "BehaviorLab: normal treasure WeightedPool root minimum missing");
    }
#else
    char const* backend = "native";
#endif
    auto color = visual.getArray("color");
    lruRequire(color.size() == 4, "BehaviorLab: missing WeightedPool color");
    auto image = assets->image(visual.getString("imagePath"));
    lruRequire(image->size() == Vec2U(16, 16), "BehaviorLab: WeightedPool image dimensions");
    Vec4B expected(color[0].toUInt(), color[1].toUInt(), color[2].toUInt(), color[3].toUInt());
    for (unsigned y = 0; y < 16; ++y)
      for (unsigned x = 0; x < 16; ++x)
        lruRequire(image->get(x, y) == expected, "BehaviorLab: WeightedPool Assets color differs");
    consumer.proof = JsonObject{{"version", 1}, {"backend", backend},
        {"selector", "STAR_USE_RUST_WEIGHTED_POOL"}, {"scopeThread", "lua-calling-thread"},
        {"phase", stage}, {"countersBefore", before}, {"countersAfter", after}, {"visual", visual},
        {"consumer", "normal-root.createTreasure-TreasureDatabase-WeightedPool-ItemDatabase"},
        {"imageConsumer", "normal-Assets-WorldPainter"}, {"labelConsumer", "normal-Font-TextPainter"},
        {"configuration", configuration()}};
    consumer.stage = int(stage);
  }
  lruRequire(weightedPoolFramePrepared(stage), "BehaviorLab: WeightedPool overlay not prepared");
  auto drawable = Drawable::makeImage(consumer.proof.get("visual").getString("imagePath"),
      2.0f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  renderData.foregroundOverlays.append(std::move(drawable));
}
void BehaviorLab::renderWeightedPoolLabel(GuiContext& gui) {
  auto const& proof = weightedPoolConsumer().proof;
  lruRequire(weightedPoolScene() && !proof.isNull(), "BehaviorLab: missing WeightedPool Font proof");
  gui.clearTextStyle(); gui.setDefaultFont(); gui.setFontSize(8, 1.0f);
  gui.setFontColor(Vec4B(255, 255, 255, 255)); gui.setFontMode(FontMode::Normal);
  gui.setFontProcessingDirectives("");
  gui.renderText(proof.get("visual").getString("label"),
      TextPositioning(Vec2F(gui.windowSize()) * 0.5f + Vec2F(-35, 70)));
  gui.clearTextStyle();
}
Json BehaviorLab::weightedPoolProof() {
  lruRequire(weightedPoolScene() && !weightedPoolConsumer().proof.isNull(),
      "BehaviorLab: missing WeightedPool proof");
  return weightedPoolConsumer().proof;
}

#include "../lab/behavior/id_map_scene.hpp"
#include "../lab/behavior/static_vector_scene.hpp"
#include "../lab/behavior/bimap_scene.hpp"

void ClientApplication::validateBehaviorStorage() {
  auto const& config = BehaviorLab::configuration();
  auto scenario = config.getString("scenario", "lighting-room");
  if (scenario != "lighting-room" && scenario != "raycast-room" && scenario != "encoding-room"
      && scenario != "sha256-room" && scenario != "vlq-room" && scenario != "bytes-room"
      && scenario != "unicode-room" && scenario != "shell-room" && scenario != "jsonpath-room" && scenario != "assetpath-room"
      && scenario != "random-room" && scenario != "jsonpatch-room" && scenario != "text-room"
      && scenario != "compression-room" && scenario != "zstd-room" && scenario != "option-parser-room"
      && scenario != "host-address-room" && scenario != "datastream-room" && scenario != "buffer-room" && scenario != "stringview-room" && scenario != "path-embed-room" && scenario != "lru-room" && scenario != "ttl-room" && scenario != "weighted-pool-room" && scenario != "id-map-room" && scenario != "static-vector-room")
    throw StarException("BehaviorLab: unsupported scenario");
  m_behaviorRaycastRoom = scenario == "raycast-room";
  m_behaviorEncodingRoom = scenario == "encoding-room";
  m_behaviorSha256Room = scenario == "sha256-room";
  m_behaviorVlqRoom = scenario == "vlq-room";
  m_behaviorBytesRoom = scenario == "bytes-room";
  m_behaviorUnicodeRoom = scenario == "unicode-room";
  m_behaviorShellRoom = scenario == "shell-room";
  m_behaviorJsonPathRoom = scenario == "jsonpath-room";
  m_behaviorJsonPatchRoom = scenario == "jsonpatch-room";
  m_behaviorTextScanRoom = scenario == "text-room";
  m_behaviorAssetPathRoom = scenario == "assetpath-room";
  m_behaviorRandomMwcRoom = scenario == "random-room";
  m_behaviorCompressionRoom = scenario == "compression-room";
  m_behaviorOptionParserRoom = scenario == "option-parser-room";
  m_behaviorZstdRoom = scenario == "zstd-room";
  m_behaviorPathEmbedRoom = scenario == "path-embed-room";
  m_behaviorLruRoom = scenario == "lru-room";
  m_behaviorHostAddressRoom = scenario == "host-address-room";
  m_behaviorDataStreamRoom = scenario == "datastream-room";
  m_behaviorBufferRoom = scenario == "buffer-room";
  m_behaviorStringViewRoom = scenario == "stringview-room";
  if (config.getUInt("maxFrames", 1800) == 0 || config.getUInt("maxFrames", 1800) > 18000)
    throw StarException("BehaviorLab: maxFrames must be in [1, 18000]");

  // canonical component comparison rejects sibling prefixes and symlink escapes.
  // The capture host independently requires its output-directory sentinel.
  namespace fs = std::filesystem;
  auto output = fs::canonical(fs::path(config.getString("outputDirectory").utf8()));
  auto storage = fs::weakly_canonical(fs::path(m_root->toStoragePath("").utf8()));
  auto declaredStorage = fs::weakly_canonical(fs::path(config.getString("storageDirectory").utf8()));
  if (storage != declaredStorage)
    throw StarException("BehaviorLab: bootconfig storageDirectory does not match declared lab storage");
  auto o = output.begin();
  auto s = storage.begin();
  for (; o != output.end() && s != storage.end() && *o == *s; ++o, ++s) {}
  if (o != output.end() || s == storage.end())
    throw StarException("BehaviorLab: storageDirectory must be a strict canonical descendant of outputDirectory");
}

void ClientApplication::updateBehaviorScenario() {
  auto world = m_universeClient->worldClient();
  if (!world || !world->inWorld())
    return;
  world->setAsyncLighting(false);
  world->setFullBright(false);
  bool const staticVector = BehaviorLab::staticVectorScene();
  auto fixtureX = [staticVector](int x) { return staticVector ? pmod(x - 64, 128) : x; };
  CustomWorldId fixtureId(staticVector ? "behavior-static-vector-room" : m_behaviorRaycastRoom ? "behavior-raycast-room" : "behavior-lighting-room");
  if (m_behaviorPhase == 0) {
    // The blank-world constructor normally chooses a random seed. Round-trip
    // its ordinary persisted template to freeze that input.
    auto blank = make_shared<WorldTemplate>(Vec2U(128, 96));
    SkyParameters sky;
    sky.seed = BehaviorLab::configuration().getUInt("seed", 42);
    sky.horizonClouds = false;
    sky.settings = JsonObject{
        {"stars", JsonObject{{"frames", 0}, {"list", JsonArray()}, {"hyperlist", JsonArray()}}},
        {"spaceDebrisFields", JsonArray()}
    };
    blank->setSkyParameters(sky);
    auto data = blank->store().set("seed", BehaviorLab::configuration().getUInt("seed", 42));
    auto fixture = make_shared<WorldTemplate>(data);
    m_universeServer->createCustomWorld(fixtureId, fixture);
    m_universeClient->warpPlayer(WarpToWorld(fixtureId, SpawnTargetPosition(Vec2F(12, 4))), false);
    m_behaviorPhase = 1;
    return;
  }
  if (m_universeClient->clientContext()->playerWorldId() != WorldId(fixtureId))
    return;

  m_cinematicOverlay->stop();
  m_player->setPendingCinematic(Json());
  // Keep the actual player alive but outside the fixed camera: blink, breath,
  // equipment and idle humanoid animation are not part of this lighting slice.
  m_player->movementController()->setPosition(Vec2F(12, 4));
  m_player->movementController()->setVelocity(Vec2F());

  if (m_behaviorPhase == 1) {
    bool populated = false;
    m_universeServer->executeForClient(world->connection(), [&](WorldServer* server, PlayerPtr) {
      if (server->worldId() != printWorldId(fixtureId))
        return;
      if (staticVector) {
        server->generateRegion(RectI(0, 0, 40, 66));
        server->generateRegion(RectI(96, 0, 128, 66));
      } else {
        server->generateRegion(RectI(6, 0, 90, 66));
      }
      m_behaviorMaterial = m_root->materialDatabase()->materialId("smoothmetal");
      // Use the same authoritative tile writer as dungeon generation. Normal
      // player placement requires adjacent terrain and cannot seed an empty world.
      DungeonGeneratorWorld writer(server, false);
      for (int x = 40; x <= 88; ++x) {
        for (int y = 32; y <= 64; ++y) {
          writer.setBackgroundMaterial(Vec2I(fixtureX(x), y), m_behaviorMaterial, 0, DefaultMaterialColorVariant);
          if (x == 40 || x == 88 || y == 32 || y == 64)
            writer.setForegroundMaterial(Vec2I(fixtureX(x), y), m_behaviorMaterial, 0, DefaultMaterialColorVariant);
        }
      }
      for (int x = 8; x <= 18; ++x)
        writer.setForegroundMaterial(Vec2I(x, 0), m_behaviorMaterial, 0, DefaultMaterialColorVariant);
      // A small platform makes the lighting scene include horizontal geometry.
      for (int x = 68; x <= 80; ++x) {
        // Both ray columns start empty, including where the platform crosses 70.
        if (m_behaviorRaycastRoom && x == 70)
          continue;
        writer.setForegroundMaterial(Vec2I(fixtureX(x), 40), m_behaviorMaterial, 0, DefaultMaterialColorVariant);
      }
      server->setSpawningEnabled(false);

      auto objects = m_root->objectDatabase();
      // Only the lab bootconfig loads this overlay. A single occupied tile at
      // (52,33) anchors to the room floor at (52,32), without vanilla-lamp
      // heuristics or bypassing ObjectDatabase placement/replication.
      String const name = "behaviorlabconstantlight";
      if (!objects->isObject(name))
        throw StarException("BehaviorLab: required constant-light fixture overlay is missing");
      auto objectConfig = objects->getConfig(name);
      if (objectConfig->lightFlickering || objectConfig->lightColors.empty() || objectConfig->animationConfig
          || !objectConfig->scripts.empty() || !objectConfig->animationScripts.empty()
          || !objectConfig->soundEffect.empty())
        throw StarException("BehaviorLab: constant-light fixture has dynamic behavior");
      for (auto const& orientation : objectConfig->orientations) {
        if (orientation->frames != 1 || !orientation->particleEmitters.empty())
          throw StarException("BehaviorLab: constant-light fixture has animation or particles");
      }
      auto lamp = objects->createForPlacement(server, name, Vec2I(fixtureX(52), 33), Direction::Right);
      if (!lamp)
        throw StarException("BehaviorLab: constant-light fixture cannot anchor at (52,33)");
      if (biMapUniqueIdProbe()) lamp->setUniqueId(biMapLampId(0));
      server->addEntity(lamp);
      if (lamp->lightSources().size() != 1)
        throw StarException("BehaviorLab: constant-light fixture must emit exactly one light");
      m_behaviorLightId = lamp->entityId();
      m_behaviorLightObject = name;
      populated = true;
    });
    if (populated) {
      m_behaviorPhase = 2;
      m_behaviorSettledFrames = 0;
    }
    return;
  }

  if (m_behaviorPhase == 4) {
    if (!BehaviorLab::frameCaptured(m_behaviorCapture))
      return;
    if (m_behaviorStage == 2) {
      if (staticVector) BehaviorLab::restoreStaticVectorScene(m_universeServer.get(), world.get(), true);
      if (BehaviorLab::idMapScene()) BehaviorLab::restoreIdMapStatus();
      Logger::info("BehaviorLab: {} completed (three acknowledged world frames)",
          staticVector ? "static-vector-room" : BehaviorLab::idMapScene() ? "id-map-room" : BehaviorLab::weightedPoolScene() ? "weighted-pool-room" : BehaviorLab::ttlScene() ? "ttl-room" : m_behaviorLruRoom ? "lru-room" : m_behaviorPathEmbedRoom ? "path-embed-room" : m_behaviorStringViewRoom ? "stringview-room" : m_behaviorBufferRoom ? "buffer-room" : m_behaviorDataStreamRoom ? "datastream-room" : m_behaviorHostAddressRoom ? "host-address-room" : m_behaviorOptionParserRoom ? "option-parser-room" : m_behaviorZstdRoom ? "zstd-room" : m_behaviorCompressionRoom ? "compression-room" : m_behaviorTextScanRoom ? "text-room" : m_behaviorJsonPatchRoom ? "jsonpatch-room" : m_behaviorRandomMwcRoom ? "random-room" : m_behaviorAssetPathRoom ? "assetpath-room" : m_behaviorJsonPathRoom ? "jsonpath-room" : m_behaviorShellRoom ? "shell-room" : m_behaviorUnicodeRoom ? "unicode-room" : m_behaviorBytesRoom ? "bytes-room" : m_behaviorVlqRoom ? "vlq-room" : m_behaviorSha256Room ? "sha256-room" : m_behaviorEncodingRoom ? "encoding-room" : m_behaviorRaycastRoom ? "raycast-room" : "lighting-room");
      m_behaviorPhase = 5;
      appController()->quit();
      return;
    }
    ++m_behaviorStage;
    if (staticVector) staticVectorSceneState().owned = true;
    auto material = m_behaviorStage == 1 ? m_behaviorMaterial : EmptyMaterialId;
    bool changed = false;
    m_universeServer->executeForClient(world->connection(), [&](WorldServer* server, PlayerPtr player) {
      if (server->worldId() != printWorldId(fixtureId))
        return;
      DungeonGeneratorWorld writer(server, false);
      for (int x : {62, 70}) {
        if (x == 70 && !m_behaviorRaycastRoom && !staticVector)
          continue;
        int column = staticVector ? (x == 62 ? 126 : 2) : x;
        for (int y = 33; y <= 59; ++y)
          writer.setForegroundMaterial(Vec2I(column, y), material, 0, DefaultMaterialColorVariant);
      }
      renameBiMapLamp(server, player, m_behaviorLightId, m_behaviorStage);
      changed = true;
    });
    if (!changed)
      throw StarException("BehaviorLab: lost authoritative fixture world during action");
    m_behaviorPhase = 2;
    m_behaviorSettledFrames = 0;
  }

  if (m_behaviorPhase == 2) {
    bool replicated = world->material(Vec2I(fixtureX(40), 48), TileLayer::Foreground) == m_behaviorMaterial
        && world->material(Vec2I(fixtureX(64), 48), TileLayer::Background) == m_behaviorMaterial
        && (!staticVector || (world->material(Vec2I(24, 48), TileLayer::Foreground) == m_behaviorMaterial
            && world->material(Vec2I(116, 48), TileLayer::Background) == m_behaviorMaterial))
        && world->entity(m_behaviorLightId);
    auto expected = m_behaviorStage == 1 ? m_behaviorMaterial : EmptyMaterialId;
    for (int x : {62, 70}) {
      if (x == 70 && !m_behaviorRaycastRoom && !staticVector)
        continue;
      int column = staticVector ? (x == 62 ? 126 : 2) : x;
      for (int y = 33; y <= 59; ++y)
        replicated = replicated && world->material(Vec2I(column, y), TileLayer::Foreground) == expected;
    }
    if (!replicated) {
      m_behaviorSettledFrames = 0;
      return;
    }
    // Require real replication plus a bounded settling interval, not merely a
    // timer from the send call. Rendering still waits for the lighting worker.
    if (++m_behaviorSettledFrames >= 90)
      m_behaviorReady = true;
  }
}

void ClientApplication::prepareBehaviorRaycastFrame() {
  m_behaviorRaycastState = Json();
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright)
    return;
  auto world = m_universeClient->worldClient();
  if (!world || !world->inWorld())
    return;

  Vec2F const start(54.5f, 48.5f);
  Vec2F const end(74.5f, 48.5f);
  Vec2F markerEnd = end;
  auto observe = [&](auto const& queryWorld, Vec2F* endpoint) -> Json {
    JsonObject calls;
    auto count = []() -> uint64_t {
#ifdef STAR_USE_RUST_BLOCKS_ALONG_LINE
      return star_blocks_along_line_call_count();
#else
      return 0;
#endif
    };
    auto measured = [&](String const& name, auto&& query) {
      // Receipts are TLS: read immediately around each public query on the
      // executing thread, including inside the locked server action below.
      auto before = count();
      auto result = query();
      calls[name] = count() - before;
      return result;
    };
    auto collision = measured("collision", [&] { return queryWorld->lineTileCollision(start, end); });
    auto point = measured("point", [&] { return queryWorld->lineTileCollisionPoint(start, end); });
    auto tiles = measured("tiles", [&] { return queryWorld->collidingTilesAlongLine(start, end); });
    auto limited = measured("limitedTiles", [&] {
      return queryWorld->collidingTilesAlongLine(start, end, DefaultCollisionSet, 1, true);
    });
    auto zero = measured("zeroLimitTiles", [&] {
      return queryWorld->collidingTilesAlongLine(start, end, DefaultCollisionSet, 0, true);
    });
    auto tileJson = [](List<Vec2I> const& list) {
      JsonArray result;
      for (auto const& tile : list)
        result.append(jsonFromVec2I(tile));
      return result;
    };
    if (endpoint)
      *endpoint = point ? point->first : end;
    String backend = "cpp";
#ifdef STAR_USE_RUST_BLOCKS_ALONG_LINE
    backend = "rust";
#endif
    // Preserve the public API's positive directional normal and border offset;
    // neither the collision point nor the rendered endpoint is reconstructed.
    return JsonObject{{"collision", collision},
        {"point", point ? jsonFromVec2F(point->first) : Json()},
        {"normal", point ? jsonFromVec2I(point->second) : Json()},
        {"tiles", tileJson(tiles)}, {"limitedTiles", tileJson(limited)},
        {"zeroLimitTiles", tileJson(zero)}, {"backend", backend}, {"rustCalls", std::move(calls)}};
  };
  auto client = observe(world, &markerEnd);
  Json serverState;
  // executeForClient synchronously executes under the world's lock. Do not
  // measure its TLS receipts outside this action or reuse the client's count.
  m_universeServer->executeForClient(world->connection(), [&](WorldServer* server, PlayerPtr) {
    if (server->worldId() == printWorldId(CustomWorldId("behavior-raycast-room")))
      serverState = observe(server, nullptr);
  });
  if (serverState.isNull())
    throw StarException("BehaviorLab: lost authoritative fixture world during raycast");

  m_behaviorRaycastState = JsonObject{{"start", jsonFromVec2F(start)}, {"end", jsonFromVec2F(end)},
      {"occluderColumns", JsonArray{62, 70}}, {"markerEnd", jsonFromVec2F(markerEnd)},
      {"client", std::move(client)}, {"server", std::move(serverState)}};
  // WorldClient::render clears/repopulates overlays each frame. Append only
  // after that call, before WorldPainter, and publish these same observations.
  auto appendLine = [&](Vec2F const& a, Vec2F const& b, Color const& color) {
    // Line widths are logical pixels, unlike endpoints in world tile units.
    auto drawable = Drawable::makeLine(Line2F(a, b), 2.0f, color);
    drawable.fullbright = true;
    m_renderData.foregroundOverlays.append(std::move(drawable));
  };
  appendLine(start, markerEnd, Color::Cyan);
  appendLine(markerEnd - Vec2F(0.3f, 0), markerEnd + Vec2F(0.3f, 0), Color::Yellow);
  appendLine(markerEnd - Vec2F(0, 0.3f), markerEnd + Vec2F(0, 0.3f), Color::Yellow);
}

void ClientApplication::prepareBehaviorEncodingFrame() {
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright)
    return;

  if (m_behaviorEncodingProof.isNull()) {
    auto assets = m_root->assets();
    String const proofPath = "/behaviorlab/encoding-proof.json";
    String const imagePath = "/behaviorlab/encoding-roundtrip.png";
    // Load-script exceptions are logged and swallowed by Assets. Demand both
    // generated outputs, never a seed fallback or a fabricated receipt.
    if (!assets->assetExists(proofPath) || !assets->assetExists(imagePath))
      throw StarException("BehaviorLab: encoding postLoad outputs are missing");
    auto proof = assets->json(proofPath);
    if (proof.getUInt("version") != 1 || proof.getArray("patternSize") != JsonArray{16, 16}
        || assets->image(imagePath)->size() != Vec2U(16, 16)
        || assets->image("/objects/behaviorlab/constantlight/constantlight.png")->size() != Vec2U(16, 16))
      throw StarException("BehaviorLab: invalid encoding postLoad outputs");
    // Measure only canonical production serialization. The resulting directive
    // is the actual foreground image path, not a disconnected encoding probe.
    auto count = [](uint32_t op) -> uint64_t {
#ifdef STAR_USE_RUST_ENCODE
      return star_encode_call_count(op);
#else
      return 0;
#endif
    };
    uint64_t before[5];
    for (uint32_t op = 0; op != 5; ++op)
      before[op] = count(op);
    auto directive = imageOperationToString(MultiplyImageOperation{Vec4B(255, 255, 255, 255)});
    JsonArray receipts;
    for (uint32_t op = 0; op != 5; ++op)
      receipts.append(count(op) - before[op]);
    if (directive != "multiply=ffffff")
      throw StarException("BehaviorLab: unexpected encoding draw directive");
    String backend = "cpp";
#ifdef STAR_USE_RUST_ENCODE
    backend = "rust";
#endif
    m_behaviorEncodingImage = imagePath + "?" + directive;
    m_behaviorEncodingProof = proof.set("backend", backend).set("drawDirective", directive)
        .set("drawReceipts", std::move(receipts));
  }
  // Foreground overlays are normal WorldPainter image drawables, rebuilt after
  // WorldClient::render clears them. 16 * (2/TilePixels) * TilePixels * camera
  // ratio 2 = 64 physical pixels, centered at the unchanged camera (64,48).
  auto drawable = Drawable::makeImage(m_behaviorEncodingImage, 2.0f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::prepareBehaviorSha256Frame() {
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright
      || !m_behaviorSha256Proof.isNull())
    return;

  auto assets = sha256BehaviorAssetProof();
  if (assets.isNull())
    throw StarException("BehaviorLab: SHA256 root asset proof is missing");

  auto count = [](uint32_t op) -> uint64_t {
#ifdef STAR_USE_RUST_SHA256
    return star_sha256_call_count(op);
#else
    return 0;
#endif
  };
  uint64_t before[4];
  for (uint32_t op = 0; op != 4; ++op)
    before[op] = count(op);

  // Real persistent BTree pages, but only in RAM. A fresh database object must
  // reopen the same Buffer; do not substitute a map or touch player storage.
  auto buffer = make_shared<BehaviorBTreeBuffer>();
  String const key = "behaviorlab-sha256-key";
  ByteArray const initial("alpha\0one", 9);
  ByteArray const updated("beta\0two", 8);
  BTreeSha256Database database("behavior_sha256");
  database.setIODevice(buffer);
  database.setBlockSize(512);
  if (!database.open())
    throw StarException("BehaviorLab: SHA256 RAM database was not newly created");
  bool insertedOverExisting = database.insert(key, initial);
  auto foundBefore = database.find(key);
  bool updatedExisting = database.insert(key, updated);
  auto foundUpdated = database.find(key);
  database.commit();
  database.close(); // default false preserves the device, including its bytes.

  BTreeSha256Database reopened("behavior_sha256");
  reopened.setIODevice(buffer);
  reopened.setBlockSize(512);
  if (reopened.open())
    throw StarException("BehaviorLab: SHA256 RAM database did not reopen existing pages");
  auto foundReopened = reopened.find(key);
  bool removed = reopened.remove(key);
  bool containsAfterRemove = reopened.contains(key);
  auto recordCountAfterRemove = reopened.recordCount();
  reopened.close();

  JsonArray calls;
  for (uint32_t op = 0; op != 4; ++op)
    calls.append(count(op) - before[op]);
  if (insertedOverExisting || !updatedExisting || !foundBefore || *foundBefore != initial
      || !foundUpdated || *foundUpdated != updated || !foundReopened || *foundReopened != updated
      || !removed || containsAfterRemove || recordCountAfterRemove != 0)
    throw StarException("BehaviorLab: SHA256 RAM database persistence/key checks failed");

  String backend = "cpp";
  JsonArray expectedCalls{0, 0, 0, 0};
#ifdef STAR_USE_RUST_SHA256
  backend = "rust";
  expectedCalls = JsonArray{0, 0, 0, 7};
#endif
  if (calls != expectedCalls)
    throw StarException::format("BehaviorLab: unexpected SHA256 database calls: {}", Json(calls));
  auto const assetChunks = assets.getArray("chunkSizes").size();
  JsonArray expectedAssetCalls{0, 0, 0, 0};
#ifdef STAR_USE_RUST_SHA256
  expectedAssetCalls = JsonArray{1, assetChunks, 1, 0};
#else
  (void)assetChunks;
#endif
  if (assets.getString("backend") != backend || assets.getArray("rustCalls") != expectedAssetCalls)
    throw StarException("BehaviorLab: unexpected SHA256 asset backend/calls");

  // Encode actual observed values only after the measured database operations.
  Json databaseProof = JsonObject{{"backend", backend}, {"key", key},
      {"foundBeforeHex", hexEncode(*foundBefore)}, {"foundUpdatedHex", hexEncode(*foundUpdated)},
      {"foundReopenedHex", hexEncode(*foundReopened)}, {"removed", removed},
      {"containsAfterRemove", containsAfterRemove}, {"recordCountAfterRemove", recordCountAfterRemove},
      {"rustCalls", std::move(calls)}};
  m_behaviorSha256Proof = JsonObject{{"version", 1}, {"assets", std::move(assets)},
      {"database", std::move(databaseProof)}};
}

void ClientApplication::prepareBehaviorVlqFrame() {
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright)
    return;

  if (m_behaviorVlqProof.isNull()) {
    auto count = [](uint32_t op) -> uint64_t {
#ifdef STAR_USE_RUST_VLQ
      return star_vlq_call_count(op);
#else
      (void)op;
      return 0;
#endif
    };
    auto snapshot = [&]() {
      std::array<uint64_t, 6> result;
      for (uint32_t op = 0; op != 6; ++op)
        result[op] = count(op);
      return result;
    };
    auto delta = [&](std::array<uint64_t, 6> const& before) {
      JsonArray result;
      for (uint32_t op = 0; op != 6; ++op)
        result.append(count(op) - before[op]);
      return result;
    };
    auto requireCalls = [](JsonArray const& calls, std::array<bool, 6> active) {
      for (size_t op = 0; op != 6; ++op) {
#ifdef STAR_USE_RUST_VLQ
        bool expectedPositive = active[op];
#else
        (void)active;
        bool expectedPositive = false;
#endif
        if (expectedPositive ? calls[op].toUInt() == 0 : calls[op].toUInt() != 0)
          throw StarException::format("BehaviorLab: unexpected VLQ operation receipts: {}", Json(calls));
      }
    };
    String backend = "cpp";
    JsonArray pairCalls{0, 0, 0, 0, 0, 0}, stringCalls = pairCalls;
    JsonArray sizeCallsExpected = pairCalls, packetWriteExpected = pairCalls, packetReadExpected = pairCalls;
    JsonArray eofCallsExpected = pairCalls;
#ifdef STAR_USE_RUST_VLQ
    backend = "rust";
    pairCalls = JsonArray{0, 0, 1, 0, 0, 2};
    stringCalls = JsonArray{0, 0, 1, 0, 0, 0};
    sizeCallsExpected = JsonArray{0, 0, 0, 0, 1, 0};
    packetWriteExpected = JsonArray{0, 0, 0, 2, 0, 0};
    packetReadExpected = JsonArray{0, 0, 0, 0, 0, 2};
    eofCallsExpected = JsonArray{0, 0, 1, 0, 0, 0};
#endif
    String const text(std::string(128, 'x'));
    String stringInputHex = "058100";
    for (unsigned i = 0; i != 128; ++i)
      stringInputHex += "78";
    auto assetProof = vlqBehaviorAssetProof();
    Json expectedAssets = JsonObject{{"backend", backend}, {"pairInputHex", "0602048101048200"},
        {"pairValue", JsonArray{-65, 128}}, {"stringInputHex", stringInputHex}, {"stringValue", text},
        {"readCalls", JsonObject{{"pair", pairCalls}, {"string", stringCalls}}},
        {"visualColor", JsonArray{255, 0, 0, 255}}};
    auto assets = m_root->assets();
    String const imagePath = "/behaviorlab/vlq-result.png";
    // Assets swallows postLoad Lua exceptions. Require both independent proof
    // and actual normal image pixels; a lamp seed fallback is not acceptance.
    if (assetProof != expectedAssets || !assets->assetExists(imagePath))
      throw StarException("BehaviorLab: missing or invalid VLQ asset proof/image");
    auto image = assets->image(imagePath);
    if (image->size() != Vec2U(16, 16))
      throw StarException("BehaviorLab: VLQ result image must be 16x16");
    for (unsigned y = 0; y != 16; ++y)
      for (unsigned x = 0; x != 16; ++x)
        if (image->get(x, y) != Vec4B(255, 0, 0, 255))
          throw StarException("BehaviorLab: VLQ result pixels differ from decoded values");

    // Production save codec, including magic and subversion trailer, in RAM
    // only. The parent independently compares the entire CPP/Rust wire bytes.
    auto value = VersionedJson::fromJson(JsonObject{{"id", "vlqlab"}, {"version", 1},
        {"content", JsonArray{-65, 128, text}}, {"subVersions", JsonObject{{"vlq", 128}}}});
    DataStreamBuffer saveStream;
    auto before = snapshot();
    saveStream.writeData(VersionedJson::Magic, VersionedJson::MagicStringSize);
    saveStream.write(value);
    VersionedJson::writeSubVersioning(saveStream, value);
    auto saveWriteCalls = delta(before);
    requireCalls(saveWriteCalls, {true, false, false, true, false, false});
    auto saveBytes = saveStream.data();
    DataStreamBuffer saveReader(saveBytes);
    before = snapshot();
    if (saveReader.readBytes(VersionedJson::MagicStringSize)
        != ByteArray(VersionedJson::Magic, VersionedJson::MagicStringSize))
      throw StarException("BehaviorLab: VLQ save magic mismatch");
    VersionedJson decoded;
    saveReader.read(decoded);
    VersionedJson::readSubVersioning(saveReader, decoded);
    auto saveReadCalls = delta(before);
    requireCalls(saveReadCalls, {false, false, true, false, false, true});
    if (decoded.toJson() != value.toJson() || saveReader.pos() != saveBytes.size())
      throw StarException("BehaviorLab: VLQ save decode/trailer mismatch");
    Json save = JsonObject{{"wireHex", hexEncode(saveBytes)}, {"value", decoded.toJson()},
        {"consumed", saveReader.pos()}, {"writeCalls", saveWriteCalls}, {"readCalls", saveReadCalls}};

    // LocalSockets bypass serialization in release. Explicitly exercise real
    // production packets, with both compatibility rules, without any sockets.
    DataStreamBuffer currentPing, currentPong, legacyPing, legacyPong;
    before = snapshot();
    auto signedSize = vlqISize(-65);
    auto sizeCalls = delta(before);
    currentPing.reserve(signedSize);
    before = snapshot();
    PingPacket(-65).write(currentPing, NetCompatibilityRules());
    PongPacket(128).write(currentPong, NetCompatibilityRules());
    PingPacket(-65).write(legacyPing, NetCompatibilityRules(LegacyVersion));
    PongPacket(128).write(legacyPong, NetCompatibilityRules(LegacyVersion));
    auto packetWriteCalls = delta(before);
    currentPing.seek(0);
    currentPong.seek(0);
    legacyPing.seek(0);
    legacyPong.seek(0);
    PingPacket pingDecoded, legacyPingDecoded;
    PongPacket pongDecoded, legacyPongDecoded;
    before = snapshot();
    pingDecoded.read(currentPing, NetCompatibilityRules());
    pongDecoded.read(currentPong, NetCompatibilityRules());
    legacyPingDecoded.read(legacyPing, NetCompatibilityRules(LegacyVersion));
    legacyPongDecoded.read(legacyPong, NetCompatibilityRules(LegacyVersion));
    auto packetReadCalls = delta(before);
    JsonArray times{pingDecoded.time, pongDecoded.time, legacyPingDecoded.time, legacyPongDecoded.time};
    if (signedSize != 2 || signedSize != currentPing.size() || sizeCalls != sizeCallsExpected
        || packetWriteCalls != packetWriteExpected || packetReadCalls != packetReadExpected
        || times != JsonArray{-65, 128, 0, 0}
        || hexEncode(currentPing.data()) != "8101" || hexEncode(currentPong.data()) != "8200"
        || hexEncode(legacyPing.data()) != "00" || hexEncode(legacyPong.data()) != "00"
        || !currentPing.atEnd() || !currentPong.atEnd() || !legacyPing.atEnd() || !legacyPong.atEnd())
      throw StarException("BehaviorLab: VLQ production packet bytes/receipts mismatch");
    Json packets = JsonObject{{"currentPingHex", hexEncode(currentPing.data())},
        {"currentPongHex", hexEncode(currentPong.data())}, {"legacyPingHex", hexEncode(legacyPing.data())},
        {"legacyPongHex", hexEncode(legacyPong.data())}, {"decodedTimes", times},
        {"signedSize", signedSize}, {"sizeCalls", sizeCalls}, {"writeCalls", packetWriteCalls},
        {"readCalls", packetReadCalls}};

    before = snapshot();
    auto rawBuffer = make_shared<BehaviorBTreeBuffer>();
    std::array<String, 3> const keys{"vlq-a", "vlq-b", "vlq-c"};
    std::array<size_t, 3> const lengths{127, 128, 700};
    std::array<ByteArray, 3> values;
    for (size_t seed = 0; seed != values.size(); ++seed) {
      values[seed].resize(lengths[seed]);
      for (size_t i = 0; i != lengths[seed]; ++i)
        values[seed][i] = static_cast<char>((i + seed) & 255);
    }
    BTreeSha256Database database("behavior_vlq");
    database.setIODevice(rawBuffer);
    database.setBlockSize(512);
    database.setAutoCommit(false);
    if (!database.open())
      throw StarException("BehaviorLab: VLQ database unexpectedly existed");
    for (size_t i = 0; i != keys.size(); ++i)
      if (database.insert(keys[i], values[i]))
        throw StarException("BehaviorLab: VLQ database duplicate initial key");
    database.commit();
    // Observe the actual committed device, not a re-encoded reconstruction.
    auto pages = rawBuffer->data();
    database.close(false);
    BTreeSha256Database reopened("behavior_vlq");
    reopened.setIODevice(rawBuffer);
    reopened.setBlockSize(512);
    if (reopened.open())
      throw StarException("BehaviorLab: VLQ database lost committed pages");
    JsonArray foundHex, valueLengths;
    for (size_t i = 0; i != keys.size(); ++i) {
      auto found = reopened.find(keys[i]);
      if (!found || *found != values[i])
        throw StarException("BehaviorLab: VLQ database reopened value mismatch");
      valueLengths.append(found->size());
      foundHex.append(hexEncode(*found));
    }
    reopened.close(false);
    auto databaseCalls = delta(before);
    requireCalls(databaseCalls, {true, true, true, false, false, false});
    Json databaseProof = JsonObject{{"valueLengths", valueLengths}, {"foundHex", foundHex},
        {"pagesBase64", base64Encode(pages)}, {"rustCalls", databaseCalls}};

    DataStreamBuffer eofStream(ByteArray("\x81", 1));
    uint64_t unsignedValue = 0x12345678;
    bool caughtEof = false;
    before = snapshot();
    try {
      eofStream.readVlqU(unsignedValue);
    } catch (EofException const&) {
      caughtEof = true;
    }
    auto eofCalls = delta(before);
    if (!caughtEof || unsignedValue != 1 || eofStream.pos() != 1 || eofCalls != eofCallsExpected)
      throw StarException("BehaviorLab: VLQ EOF exception/partial output mismatch");
    Json eof = JsonObject{{"kind", "EofException"}, {"unsignedValue", unsignedValue},
        {"consumed", eofStream.pos()}, {"readCalls", eofCalls}};
    m_behaviorVlqProof = JsonObject{{"version", 1}, {"assets", assetProof}, {"save", save},
        {"packets", packets}, {"database", databaseProof}, {"eof", eof}};
  }
  auto drawable = Drawable::makeImage("/behaviorlab/vlq-result.png", 2.0f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::prepareBehaviorBytesFrame() {
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright)
    return;

  if (m_behaviorBytesProof.isNull()) {
    auto count = [](uint32_t op) -> uint64_t {
#ifdef STAR_USE_RUST_BYTES
      return star_bytes_call_count(op);
#else
      (void)op;
      return 0;
#endif
    };
    auto snapshot = [&]() {
      std::array<uint64_t, 6> result;
      for (uint32_t op = 0; op != 6; ++op)
        result[op] = count(op);
      return result;
    };
    auto delta = [&](std::array<uint64_t, 6> const& before) {
      JsonArray result;
      for (uint32_t op = 0; op != 6; ++op)
        result.append(count(op) - before[op]);
      return result;
    };
    String backend = "cpp";
    JsonArray assetCalls{0, 0, 0, 0, 0, 0}, saveWriteExpected = assetCalls;
    JsonArray saveReadExpected = assetCalls, packetWriteExpected = assetCalls, packetReadExpected = assetCalls;
#ifdef STAR_USE_RUST_BYTES
    backend = "rust";
    assetCalls = JsonArray{0, 0, 0, 0, 0, 3};
    saveWriteExpected = JsonArray{0, 0, 0, 5, 0, 0};
    saveReadExpected = JsonArray{0, 0, 0, 0, 0, 5};
    packetWriteExpected = JsonArray{0, 0, 0, 1, 0, 0};
    packetReadExpected = JsonArray{0, 0, 0, 0, 0, 1};
#endif
    auto assetProof = bytesBehaviorAssetProof();
    Json expectedAssets = JsonObject{{"backend", backend},
        {"inputHex", "0603023fd0000000000000023fe0000000000000023fe8000000000000"},
        {"values", JsonArray{0.25, 0.5, 0.75}}, {"rustCalls", assetCalls},
        {"visualColor", JsonArray{64, 128, 192, 255}}};
    auto assets = m_root->assets();
    String const imagePath = "/behaviorlab/bytes-result.png";
    // Lua postLoad failures are swallowed: proof AND real normal Assets pixels
    // are required before any capture is accepted.
    if (assetProof != expectedAssets || !assets->assetExists(imagePath))
      throw StarException("BehaviorLab: missing or invalid bytes asset proof/image");
    auto image = assets->image(imagePath);
    if (image->size() != Vec2U(16, 16))
      throw StarException("BehaviorLab: bytes result image must be 16x16");
    for (unsigned y = 0; y != 16; ++y)
      for (unsigned x = 0; x != 16; ++x)
        if (image->get(x, y) != Vec4B(64, 128, 192, 255))
          throw StarException("BehaviorLab: bytes result pixels differ from decoded values");

    auto value = VersionedJson::fromJson(JsonObject{{"id", "byteslab"}, {"version", 16909060},
        {"content", JsonArray{0.25, 0.5, 0.75}}, {"subVersions", JsonObject{}}});
    String const saveInputHex = "5342564a30310862797465736c616201010203040603023fd0000000000000023fe0000000000000023fe800000000000000000001010b73756256657273696f6e730700";
    auto saveInput = hexDecode(saveInputHex);
    if (saveInput.size() != 68)
      throw StarException("BehaviorLab: independent bytes save literal length mismatch");
    DataStreamBuffer saveStream;
    auto before = snapshot();
    saveStream.writeData(VersionedJson::Magic, VersionedJson::MagicStringSize);
    saveStream.write(value);
    VersionedJson::writeSubVersioning(saveStream, value);
    auto saveWriteCalls = delta(before);
    DataStreamBuffer saveReader(saveInput);
    before = snapshot();
    auto magic = saveReader.readBytes(VersionedJson::MagicStringSize);
    VersionedJson decoded;
    saveReader.read(decoded);
    VersionedJson::readSubVersioning(saveReader, decoded);
    auto saveReadCalls = delta(before);
    if (magic != ByteArray(VersionedJson::Magic, VersionedJson::MagicStringSize)
        || saveStream.data() != saveInput || decoded.toJson() != value.toJson()
        || saveReader.pos() != saveInput.size() || saveWriteCalls != saveWriteExpected
        || saveReadCalls != saveReadExpected)
      throw StarException("BehaviorLab: bytes save literal/value/receipts mismatch");
    Json save = JsonObject{{"wireHex", hexEncode(saveStream.data())}, {"value", decoded.toJson()},
        {"consumed", saveReader.pos()}, {"writeCalls", saveWriteCalls}, {"readCalls", saveReadCalls}};

    // Explicit production codec calls, NOT transport: local release sockets
    // bypass serialization. Never deliver these packets to the live session.
    DataStreamBuffer currentWire, legacyWire;
    before = snapshot();
    PausePacket(true, 0.5f).write(currentWire, NetCompatibilityRules());
    PausePacket(true, 0.5f).write(legacyWire, NetCompatibilityRules(LegacyVersion));
    auto packetWriteCalls = delta(before);
    DataStreamBuffer currentInput(hexDecode("013f000000")), legacyInput(hexDecode("01"));
    PausePacket currentDecoded, legacyDecoded;
    before = snapshot();
    currentDecoded.read(currentInput, NetCompatibilityRules());
    legacyDecoded.read(legacyInput, NetCompatibilityRules(LegacyVersion));
    auto packetReadCalls = delta(before);
    if (!currentDecoded.pause || !legacyDecoded.pause || currentDecoded.timescale != 0.5f
        || legacyDecoded.timescale != 1.0f || !currentInput.atEnd() || !legacyInput.atEnd()
        || hexEncode(currentWire.data()) != "013f000000" || hexEncode(legacyWire.data()) != "01"
        || packetWriteCalls != packetWriteExpected || packetReadCalls != packetReadExpected)
      throw StarException("BehaviorLab: bytes pause packet literal/value/receipts mismatch");
    Json packets = JsonObject{{"currentInputHex", "013f000000"}, {"legacyInputHex", "01"},
        {"currentWireHex", hexEncode(currentWire.data())}, {"legacyWireHex", hexEncode(legacyWire.data())},
        {"currentConsumed", currentInput.pos()}, {"legacyConsumed", legacyInput.pos()},
        {"paused", JsonArray{currentDecoded.pause, legacyDecoded.pause}},
        {"timescales", JsonArray{currentDecoded.timescale, legacyDecoded.timescale}},
        {"writeCalls", packetWriteCalls}, {"readCalls", packetReadCalls}};

    before = snapshot();
    auto rawBuffer = make_shared<BehaviorBTreeBuffer>();
    std::array<String, 3> const keys{"vlq-a", "vlq-b", "vlq-c"};
    std::array<size_t, 3> const lengths{127, 128, 700};
    std::array<ByteArray, 3> values;
    for (size_t seed = 0; seed != values.size(); ++seed) {
      values[seed].resize(lengths[seed]);
      for (size_t i = 0; i != lengths[seed]; ++i)
        values[seed][i] = static_cast<char>((i + seed) & 255);
    }
    // Same frozen key/insert/reopen sequence as the VLQ fixture; preserving
    // keys also permits an independent raw-page oracle across both slices.
    BTreeSha256Database database("behavior_vlq");
    database.setIODevice(rawBuffer);
    database.setBlockSize(512);
    database.setAutoCommit(false);
    if (!database.open())
      throw StarException("BehaviorLab: bytes database unexpectedly existed");
    for (size_t i = 0; i != keys.size(); ++i)
      if (database.insert(keys[i], values[i]))
        throw StarException("BehaviorLab: bytes database duplicate initial key");
    database.commit();
    auto pages = rawBuffer->data();
    database.close(false);
    BTreeSha256Database reopened("behavior_vlq");
    reopened.setIODevice(rawBuffer);
    reopened.setBlockSize(512);
    if (reopened.open())
      throw StarException("BehaviorLab: bytes database lost committed pages");
    JsonArray foundHex, valueLengths;
    for (size_t i = 0; i != keys.size(); ++i) {
      auto found = reopened.find(keys[i]);
      if (!found || *found != values[i])
        throw StarException("BehaviorLab: bytes database reopened value mismatch");
      valueLengths.append(found->size());
      foundHex.append(hexEncode(*found));
    }
    reopened.close(false);
    auto databaseCalls = delta(before);
    for (size_t op = 0; op != 6; ++op) {
      bool positive = false;
#ifdef STAR_USE_RUST_BYTES
      positive = op == 3 || op == 5;
#endif
      if (positive ? databaseCalls[op].toUInt() == 0 : databaseCalls[op].toUInt() != 0)
        throw StarException("BehaviorLab: bytes database operation receipts mismatch");
    }
    Json databaseProof = JsonObject{{"valueLengths", valueLengths}, {"foundHex", foundHex},
        {"pagesBase64", base64Encode(pages)}, {"rustCalls", databaseCalls}};
    m_behaviorBytesProof = JsonObject{{"version", 1}, {"assets", assetProof}, {"save", save},
        {"packets", packets}, {"database", databaseProof}};
  }
  float timescale = m_behaviorBytesProof.get("packets").getArray("timescales")[0].toFloat();
  auto drawable = Drawable::makeImage("/behaviorlab/bytes-result.png",
      4.0f * timescale / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::prepareBehaviorUnicodeFrame() {
  auto world = m_universeClient->worldClient();
  if (!world || !world->inWorld())
    return;
  if (m_behaviorUnicodeProof.isNull()) {
    String const textHex = "41c3a9f09f9880005a";
    auto assetProof = unicodeBehaviorAssetProof();
    auto assets = m_root->assets();
    String const imagePath = "/behaviorlab/unicode-result.png";
    String backend = "cpp";
#ifdef STAR_USE_RUST_UNICODE
    backend = "rust";
#endif
    if (assetProof.isNull() || assetProof.getString("backend") != backend
        || assetProof.getString("textHex") != textHex
        || assetProof.getString("label") != "UNICODE"
        || assetProof.getArray("visualColor") != JsonArray{65, 195, 169, 255}
        || !assets->assetExists(imagePath))
      throw StarException("BehaviorLab: missing or invalid unicode asset proof/image");
    auto requireCalls = [&](JsonArray const& calls, std::initializer_list<size_t> positive) {
      if (calls.size() != 10)
        throw StarException("BehaviorLab: unicode receipt vector must have ten operations");
      for (size_t op = 0; op != 10; ++op) {
        auto count = calls[op].toUInt();
        if (backend == "cpp" && count != 0)
          throw StarException("BehaviorLab: C++ unicode receipt is nonzero");
      }
      if (backend == "rust")
        for (auto op : positive)
          if (calls[op].toUInt() == 0)
            throw StarException("BehaviorLab: required unicode operation did not execute");
    };
    requireCalls(assetProof.getArray("parseCalls"), {1, 3, 4, 6});
    auto image = assets->image(imagePath);
    if (image->size() != Vec2U(16, 16))
      throw StarException("BehaviorLab: unicode image must be 16x16");
    for (unsigned y = 0; y != 16; ++y)
      for (unsigned x = 0; x != 16; ++x)
        if (image->get(x, y) != Vec4B(65, 195, 169, 255))
          throw StarException("BehaviorLab: unicode pixels differ from decoded bytes");

    auto text = assets->json("/behaviorlab/unicode-input.json").getString("text");
    if (text.utf8Size() != 9 || hexEncode(text.utf8Bytes()) != textHex)
      throw StarException("BehaviorLab: unicode text byte literal mismatch");
    auto before = unicodeLabSnapshot();
    bool valid = text.isValid();
    auto boundedLength = text.size();
    auto sentinelLength = utf8Length(text.utf8Ptr(), NPos);
    auto stringCounts = unicodeLabDelta(before);
    UnicodeLabCounts expectedStringCounts{};
#ifdef STAR_USE_RUST_UNICODE
    expectedStringCounts[0] = 1;
    expectedStringCounts[1] = 2;
#endif
    if (!valid || boundedLength != 5 || sentinelLength != 3 || stringCounts != expectedStringCounts)
      throw StarException("BehaviorLab: unicode String length/validation/receipts mismatch");
    Json stringProof = JsonObject{{"boundedLength", boundedLength}, {"sentinelLength", sentinelLength},
        {"validUtf8", valid}, {"rustCalls", unicodeLabJson(stringCounts)}};

    // Read an INDEPENDENT literal, not the candidate writer's result.
    String const jsonInputHex = "2241c3a9f09f98805c75303030305a22";
    auto jsonInputBytes = hexDecode(jsonInputHex);
    String jsonInput(jsonInputBytes.ptr(), jsonInputBytes.size());
    Json textValue(text);
    before = unicodeLabSnapshot();
    // printJson rejects scalar roots; repr is its normal underlying writer.
    auto wire = textValue.repr();
    auto writeCounts = unicodeLabDelta(before);
    before = unicodeLabSnapshot();
    auto readValue = Json::parse(jsonInput);
    auto readCounts = unicodeLabDelta(before);
    if (hexEncode(wire.utf8Bytes()) != jsonInputHex || readValue.toString() != text)
      throw StarException("BehaviorLab: unicode JSON literal/value mismatch");
    auto jsonWriteCalls = unicodeLabJson(writeCounts), jsonReadCalls = unicodeLabJson(readCounts);
    requireCalls(jsonWriteCalls, {5});
    requireCalls(jsonReadCalls, {3, 4, 6});
    Json jsonProof = JsonObject{{"wireHex", hexEncode(wire.utf8Bytes())}, {"textHex", textHex},
        {"writeCalls", jsonWriteCalls}, {"readCalls", jsonReadCalls}};

    auto value = VersionedJson::fromJson(JsonObject{{"id", "unicodelab"}, {"version", 1},
        {"content", JsonObject{{"text", text}}}, {"subVersions", JsonObject{}}});
    // SBVJ01 + id + Maybe<u32> + binary JSON content + subversion suffix.
    auto saveInput = hexDecode("5342564a30310a756e69636f64656c6162010000000107010474657874050941c3a9f09f9880005a00000001010b73756256657273696f6e730700");
    if (saveInput.size() != 59)
      throw StarException("BehaviorLab: unicode independent save literal length mismatch");
    DataStreamBuffer saveStream;
    before = unicodeLabSnapshot();
    saveStream.writeData(VersionedJson::Magic, VersionedJson::MagicStringSize);
    saveStream.write(value);
    VersionedJson::writeSubVersioning(saveStream, value);
    auto saveWriteCounts = unicodeLabDelta(before);
    DataStreamBuffer saveReader(saveInput);
    VersionedJson decoded;
    before = unicodeLabSnapshot();
    auto magic = saveReader.readBytes(VersionedJson::MagicStringSize);
    saveReader.read(decoded);
    VersionedJson::readSubVersioning(saveReader, decoded);
    auto saveReadCounts = unicodeLabDelta(before);
    if (magic != ByteArray(VersionedJson::Magic, VersionedJson::MagicStringSize)
        || saveStream.data() != saveInput || decoded.toJson() != value.toJson()
        || saveReader.pos() != saveInput.size())
      throw StarException("BehaviorLab: unicode save literal/value mismatch");
    auto saveWriteCalls = unicodeLabJson(saveWriteCounts), saveReadCalls = unicodeLabJson(saveReadCounts);
    requireCalls(saveWriteCalls, {});
    requireCalls(saveReadCalls, {});
    Json saveProof = JsonObject{{"wireHex", hexEncode(saveStream.data())}, {"value", decoded.toJson()},
        {"consumed", saveReader.pos()}, {"writeCalls", saveWriteCalls}, {"readCalls", saveReadCalls}};
    m_behaviorUnicodeProof = JsonObject{{"version", 1}, {"assets", assetProof}, {"string", stringProof},
        {"json", jsonProof}, {"save", saveProof}};
  }
  float length = m_behaviorUnicodeProof.get("string").getUInt("boundedLength");
  auto drawable = Drawable::makeImage("/behaviorlab/unicode-result.png",
      (length - 3.0f) / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::prepareBehaviorOptionParserFrame() {
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright)
    return;
  if (m_behaviorOptionParserProof.isNull()) {
    auto startup = optionParserLabStartup();
    if (startup.isNull() || !startup.contains("root"))
      throw StarException("BehaviorLab: actual option parser startup receipt missing");
    auto config = m_root->configuration()->get("optionParserProof");
    if (config != m_root->settings().defaultConfiguration.get("optionParserProof"))
      throw StarException("BehaviorLab: option parser Root configuration differs from boot defaults");
    auto assets = m_root->assets();
    auto engine = LuaEngine::create();
    auto context = engine->createContext();
    context.setCallbacks("root", LuaBindings::makeRootCallbacks());
    context.load(*assets->bytes("/behaviorlab/option-parser-consumer.lua"),
        "/behaviorlab/option-parser-consumer.lua");
    auto visual = context.invokePath<Json>("proof");
    if (visual.get("configuration") != config)
      throw StarException("BehaviorLab: normal Lua Root binding lost option parser configuration");
    auto image = assets->image(visual.getString("imagePath"));
    auto color = visual.getArray("color");
    if (image->size() != Vec2U(16, 16) || color.size() != 4)
      throw StarException("BehaviorLab: option parser image dimensions/color invalid");
    Vec4B expected(color[0].toUInt(), color[1].toUInt(), color[2].toUInt(), color[3].toUInt());
    for (unsigned y = 0; y != 16; ++y)
      for (unsigned x = 0; x != 16; ++x)
        if (image->get(x, y) != expected)
          throw StarException("BehaviorLab: normal Assets image differs from Root configuration");
    String backend = "cpp";
#ifdef STAR_USE_RUST_OPTION_PARSER
    backend = "rust";
#endif
    m_behaviorOptionParserProof = JsonObject{{"version", 1}, {"backend", backend},
        {"startup", startup}, {"rootConfiguration", config}, {"visual", visual},
        {"sourceSize", JsonArray{16, 16}}, {"displaySize", JsonArray{64, 64}},
        {"configurationConsumer", "normal-root-lua-getConfiguration"},
        {"imageConsumer", "normal-Assets-image"}, {"labelConsumer", "normal-Font-TextPainter"},
        {"mainThreadCounters", optionParserLabCounters()}};
  }
  auto visual = m_behaviorOptionParserProof.get("visual");
  auto drawable = Drawable::makeImage(visual.getString("imagePath"),
      visual.getFloat("scale") * 0.5f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::prepareBehaviorBufferFrame() {
  if (m_behaviorBufferProof.isNull()) {
    auto byteBefore = byteArrayConsumerSnapshot();
    auto before = BufferLabCounts::snapshot();
    auto ioBefore = IODeviceLabCounts::snapshot();
    struct ByteScope {
      String method;
      ByteArrayLabCounts calls;
    };
    std::array<ByteScope, 14> byteScopes;
    size_t byteScopeCount = 0;
    JsonArray scopes;
    JsonArray ioScopes;
    uint64_t nativeCalls = 0;
    auto observed = [&](String const& method, auto&& operation, ByteArrayLabCounts const* consumerCalls = nullptr) {
      auto start = BufferLabCounts::snapshot();
      auto ioStart = IODeviceLabCounts::snapshot();
      auto byteStart = byteArrayConsumerSnapshot();
      operation();
      auto byteEnd = byteArrayConsumerSnapshot();
      auto& byteScope = byteScopes.at(byteScopeCount++);
      byteScope.calls = consumerCalls ? *consumerCalls : byteEnd.delta(byteStart);
      byteScope.method = method;
      ++nativeCalls;
      scopes.append(JsonObject{{"method", method}, {"completed", true},
          {"calls", BufferLabCounts::snapshot().delta(start)}});
      ioScopes.append(JsonObject{{"method", method}, {"completed", true},
          {"calls", IODeviceLabCounts::snapshot().delta(ioStart)}});
    };
    TcpSocketPtr listener;
    HostAddressWithPort parsed;
    uint16_t port = 0;
    for (uint16_t candidate = 40233; candidate <= 40264; ++candidate) {
      parsed = HostAddressWithPort(strf("127.0.0.1:{}", candidate));
      if (!(parsed.address() == HostAddress::localhost(NetworkMode::IPv4)) || parsed.port() != candidate)
        throw StarException("BehaviorLab: unsafe Buffer bind identity");
      try { listener = TcpSocket::listen(parsed); port = candidate; break; }
      catch (NetworkException const&) {}
    }
    if (!listener) throw StarException("BehaviorLab: no owned Buffer port");
    listener->setNonBlocking(true);
    auto rawSender = TcpSocket::connectTo(parsed);
    TcpSocketPtr rawReceiver;
    auto deadline = Time::monotonicMilliseconds() + 2000;
    while (!rawReceiver && Time::monotonicMilliseconds() < deadline) rawReceiver = listener->accept();
    if (!rawReceiver) throw StarException("BehaviorLab: Buffer accept deadline");
    auto acceptedPeer = rawReceiver->remoteAddress();
    if (!(acceptedPeer.address() == HostAddress::localhost(NetworkMode::IPv4)) || !acceptedPeer.port()
        || !(rawReceiver->localAddress() == parsed))
      throw StarException("BehaviorLab: Buffer accepted OS peer mismatch");
    listener->close(); rawSender->setNonBlocking(true); rawSender->setNoDelay(true);
    auto receiver = TcpPacketSocket::open(rawReceiver);
    receiver->setNetRules(NetCompatibilityRules(VersionNumber(5)));
    receiver->setCompressionStreamEnabled(false);
    BufferLabReceiver wire; wire.socket = receiver.get();
    struct Armed {
      explicit Armed(BufferLabReceiver* p) {
        if (BufferLabActiveReceiver) throw StarException("BehaviorLab: nested Buffer receiver observer");
        BufferLabActiveReceiver = p;
      }
      ~Armed() { BufferLabActiveReceiver = nullptr; }
    } armed(&wire);
    // Independent raw producer, derived from ChatSendPacket::write, rules 5:
    // type 0x12, signed VLQ(8)=0x10, string length5, BUF-A/B,
    // broadcast enum0, empty JsonObject length0. No paired encoder is used.
    char const frameA[] = {0x12,0x10,5,'B','U','F','-','A',0,0};
    char const frameB[] = {0x12,0x10,5,'B','U','F','-','B',0,0};
    ByteArray chunks[] = {ByteArray(frameA,1), ByteArray(frameA+1,4), ByteArray(frameA+5,5), ByteArray(frameB+4,6)};
    chunks[2].append(frameB,4);
    size_t const totals[] = {1,5,14,20}, counts[] = {0,0,1,2};
    List<PacketPtr> received;
    JsonArray stages;
    ByteArray sentWire;
    uint64_t sendAttempts = 0;
    for (unsigned stage = 0; stage != 4; ++stage) {
      wire.stage = stage;
      ByteArrayLabCounts tcpConsumerCalls;
      observed(strf("TcpPacketSocket::readData/receivePackets(stage{})", stage), [&] {
        size_t sent = 0;
        deadline = Time::monotonicMilliseconds() + 2000;
        do {
          if (sent < chunks[stage].size()) {
            auto amount = rawSender->send(chunks[stage].ptr()+sent, chunks[stage].size()-sent);
            ++sendAttempts;
            {
              ByteArrayLabBookkeepingScope bookkeeping;
              sentWire.append(chunks[stage].ptr()+sent, amount);
            }
            sent += amount;
          }
          // Sender/polling getters remain outside this production interval.
          // The receiver observer bodies are subtracted by the count helper.
          auto consumerStart = byteArrayConsumerSnapshot();
          receiver->readData();
          auto packets = receiver->receivePackets();
          auto consumerDelta = byteArrayConsumerSnapshot().delta(consumerStart);
          for (unsigned mode = 0; mode != 56; ++mode)
            for (unsigned event = 0; event != 3; ++event)
              tcpConsumerCalls.values[mode][event] += consumerDelta.values[mode][event];
          received.appendAll(std::move(packets));
          if (!receiver->isOpen() || received.size() > counts[stage])
            throw StarException("BehaviorLab: Buffer closed receiver/extra packet");
          if (sent == chunks[stage].size() && wire.wire.size() >= totals[stage]) break;
        } while (Time::monotonicMilliseconds() < deadline);
        if (sent != chunks[stage].size() || wire.wire.size() != totals[stage] || received.size() != counts[stage])
          throw StarException("BehaviorLab: Buffer staged receive deadline/count mismatch");
      }, &tcpConsumerCalls);
      stages.append(JsonObject{{"stage", stage}, {"sentBytes", sentWire.size()},
          {"receivedBytes", wire.wire.size()}, {"packetCount", received.size()}});
    }
    String label;
    JsonArray receivedTexts;
    for (unsigned i = 0; i != 2; ++i) {
      auto chat = std::dynamic_pointer_cast<ChatSendPacket>(received[i]);
      if (!chat || chat->text != (i == 0 ? "BUF-A" : "BUF-B") || chat->sendMode != ChatSendMode::Broadcast || !chat->data.empty())
        throw StarException("BehaviorLab: Buffer typed packet mismatch");
      receivedTexts.append(chat->text);
      if (i) label += "|";
      label += chat->text;
    }
    String const expectedWire = "1210054255462d4100001210054255462d420000";
    if (hexEncode(wire.wire) != expectedWire || sentWire != wire.wire)
      throw StarException("BehaviorLab: Buffer independent wire mismatch");
    BufferLabActiveReceiver = nullptr;
    receiver->close(); rawSender->close();

    // Startup already bound Root storage to a strict canonical descendant of
    // the sentinel-owned output. Reject existing files, including swap files.
    namespace fs = std::filesystem;
    auto storage = fs::canonical(fs::path(m_root->toStoragePath("").utf8()));
    auto declared = fs::canonical(fs::path(BehaviorLab::configuration().getString("storageDirectory").utf8()));
    if (storage != declared) throw StarException("BehaviorLab: Buffer storage binding drift");
    String savePath((storage / "buffer-save.sbvj").string());
    String databasePath((storage / "buffer-payload.btree").string());
    for (auto const& path : {savePath, savePath + ".new", databasePath})
      if (fs::symlink_status(fs::path(path.utf8())).type() != fs::file_type::not_found)
        throw StarException("BehaviorLab: Buffer refuses existing owned output");
    std::string payload;
    for (unsigned i = 0; i != 1537; ++i) payload += char('a' + i % 26);
    auto value = VersionedJson::fromJson(JsonObject{{"id", "bufferlab"}, {"version", 1},
        {"content", JsonArray{64, 144, 224, 255, String(payload)}}, {"subVersions", JsonObject{}}});
    FileLab::Recorder recorder;
    observed("VersionedJson::writeFile", [&] {
      FileLab::Scope scope(recorder, 0, std::this_thread::get_id() == m_behaviorMainThread);
      VersionedJson::writeFile(value, savePath);
      scope.complete();
    });
    VersionedJson decoded;
    observed("VersionedJson::readFile", [&] {
      FileLab::Scope scope(recorder, 1, std::this_thread::get_id() == m_behaviorMainThread);
      decoded = VersionedJson::readFile(savePath);
      scope.complete();
    });
    FileLab::Scope saveReadScope(recorder, 2, std::this_thread::get_id() == m_behaviorMainThread);
    auto saveBytes = File::readFile(savePath);
    saveReadScope.complete();
    // Single-key trailer and integer-array content have a fixed source-derived
    // encoding: SBVJ01, id, Maybe<u32>, Json array, u32 trailer version,
    // one-entry subVersions map containing an empty Json object.
    // SBVJ01/id/Maybe<u32>, array5, signed VLQ integers, string tag5,
    // unsigned VLQ(1537)=8c01, then the one-key subVersions trailer.
    String const expectedSave = "5342564a3031096275666665726c61620100000001060504810004822004834004837e058c01"
        + hexEncode(ByteArray(payload.data(), payload.size())) + "00000001010b73756256657273696f6e730700";
    if (hexEncode(saveBytes) != expectedSave)
      throw StarException("BehaviorLab: Buffer independent save bytes mismatch");
    DataStreamBuffer saveReader(saveBytes);
    VersionedJson inspected;
    observed("VersionedJson::readSubVersioning(owned file bytes)", [&] {
      if (saveReader.readBytes(VersionedJson::MagicStringSize) != ByteArray("SBVJ01", 6))
        throw StarException("BehaviorLab: Buffer save magic mismatch");
      saveReader.read(inspected); VersionedJson::readSubVersioning(saveReader, inspected);
    });
    if (decoded.toJson() != value.toJson() || inspected.toJson() != value.toJson() || !saveReader.atEnd())
      throw StarException("BehaviorLab: Buffer save schema/data/EOF mismatch");
    // Buffer::resize does not initialize growth. Seed the entire bounded
    // backing allocation before truncating so unused database-header bytes
    // are defined, like the real file device's zero-filled extension.
    auto memoryDevice = make_shared<BehaviorBTreeBuffer>();
    ByteArray memoryPages, memoryFound;
    observed("BTreeSha256Database::open/insert/commit/close(memory)", [&] {
      BTreeSha256Database db("bufferlab");
      db.setIODevice(memoryDevice); db.setBlockSize(512); db.setAutoCommit(false);
      if (!db.open() || db.insert(String("buffer-payload"), saveBytes))
        throw StarException("BehaviorLab: Buffer memory database initial state mismatch");
      db.commit();
      if (memoryDevice->size() > 8192) throw StarException("BehaviorLab: Buffer initialized memory extent exceeded");
      memoryPages = memoryDevice->data(); db.close(false);
    });
    observed("BTreeSha256Database::open/find/close(memory)", [&] {
      BTreeSha256Database db("bufferlab"); db.setIODevice(memoryDevice);
      if (db.open()) throw StarException("BehaviorLab: Buffer memory database lost pages");
      auto result = db.find(String("buffer-payload"));
      if (!result || *result != saveBytes) throw StarException("BehaviorLab: Buffer memory database mismatch");
      memoryFound = *result; db.close(false);
    });
    DataStreamBuffer memoryReader(memoryFound);
    VersionedJson memoryValue;
    observed("VersionedJson::readSubVersioning(memory BTree value)", [&] {
      if (memoryReader.readBytes(6) != ByteArray("SBVJ01", 6))
        throw StarException("BehaviorLab: Buffer memory database magic mismatch");
      memoryReader.read(memoryValue); VersionedJson::readSubVersioning(memoryReader, memoryValue);
    });
    if (memoryValue.toJson() != value.toJson() || !memoryReader.atEnd())
      throw StarException("BehaviorLab: Buffer memory database decoded value/EOF mismatch");
    // BTree uses its real file device, commits, closes, then reopens independently.
    ByteArray found;
    observed("BTreeSha256Database::open/insert/commit/close(file)", [&] {
      FileLab::Scope scope(recorder, 3, std::this_thread::get_id() == m_behaviorMainThread);
      // Include native database/device destruction before freezing File counts.
      {
        auto device = File::open(databasePath, IOMode::ReadWrite | IOMode::Truncate);
        BTreeSha256Database db("bufferlab");
        db.setIODevice(device); db.setBlockSize(512); db.setAutoCommit(false);
        if (!db.open() || db.insert(String("buffer-payload"), saveBytes))
          throw StarException("BehaviorLab: Buffer database initial state mismatch");
        db.commit(); db.close(true);
      }
      scope.complete();
    });
    observed("BTreeSha256Database::open/find/close(file)", [&] {
      FileLab::Scope scope(recorder, 4, std::this_thread::get_id() == m_behaviorMainThread);
      {
        BTreeSha256Database db("bufferlab");
        db.setIODevice(File::open(databasePath, IOMode::ReadWrite));
        if (db.open()) throw StarException("BehaviorLab: Buffer database lost committed file");
        auto result = db.find(String("buffer-payload"));
        if (!result) throw StarException("BehaviorLab: Buffer database missing key");
        found = *result; db.close(true);
      }
      scope.complete();
    });
    if (found != saveBytes) throw StarException("BehaviorLab: Buffer database value mismatch");
    DataStreamBuffer colorReader(found);
    VersionedJson databaseValue;
    observed("VersionedJson::readSubVersioning(BTree value)", [&] {
      if (colorReader.readBytes(6) != ByteArray("SBVJ01", 6))
        throw StarException("BehaviorLab: Buffer database value magic mismatch");
      colorReader.read(databaseValue); VersionedJson::readSubVersioning(colorReader, databaseValue);
    });
    if (databaseValue.toJson() != decoded.toJson() || !colorReader.atEnd())
      throw StarException("BehaviorLab: Buffer database decoded value/EOF mismatch");
    auto components = databaseValue.content.toArray();
    Vec4B color(components[0].toUInt(), components[1].toUInt(), components[2].toUInt(), components[3].toUInt());
    String path = strf("/behaviorlab/buffer.png?multiply={:02x}{:02x}{:02x}{:02x}", color[0], color[1], color[2], color[3]);
    auto image = m_root->assets()->image(path);
    if (image->size() != Vec2U(16, 16)) throw StarException("BehaviorLab: Buffer image dimensions");
    for (unsigned y = 0; y != 16; ++y)
      for (unsigned x = 0; x != 16; ++x)
        if (image->get(x, y) != color) throw StarException("BehaviorLab: Buffer Assets pixels mismatch");
    String backend = "cpp";
#ifdef STAR_USE_RUST_BUFFER
    backend = "rust";
#endif
    // Preserve the original Buffer aggregate: the additional PNG decoder is
    // an IODevice consumer, outside the existing 13 Buffer scopes.
    auto bufferCalls = BufferLabCounts::snapshot().delta(before);
    auto assetBytes = m_root->assets()->bytes("/behaviorlab/buffer.png");
    // Assets may load on a worker or return cached bytes. Only this explicit
    // production decode is attributed to the main-thread PNG scope.
    auto pngStart = IODeviceLabCounts::snapshot();
    auto byteStart = byteArrayConsumerSnapshot();
    auto sourceImage = Image::readPng(make_shared<Buffer>(*assetBytes));
    auto byteEnd = byteArrayConsumerSnapshot();
    auto& pngByteScope = byteScopes.at(byteScopeCount++);
    pngByteScope.calls = byteEnd.delta(byteStart);
    pngByteScope.method = "Image::readPng(owned asset bytes)";
    if (sourceImage.size() != Vec2U(16, 16))
      throw StarException("BehaviorLab: IODevice PNG source dimensions mismatch");
    auto sourceColor = sourceImage.getrgb(0, 0);
    for (unsigned y = 0; y != 16; ++y)
      for (unsigned x = 0; x != 16; ++x)
        if (sourceImage.getrgb(x, y) != Vec4B(255, 255, 255, 255))
          throw StarException("BehaviorLab: IODevice PNG source pixels mismatch");
    ioScopes.append(JsonObject{{"method", "Image::readPng(owned asset bytes)"}, {"completed", true},
        {"calls", IODeviceLabCounts::snapshot().delta(pngStart)}});
    String ioBackend = "cpp";
#ifdef STAR_USE_RUST_IO_DEVICE
    ioBackend = "rust";
#endif
    // Freeze consumer counts before frame capture writes its evidence PNG.
    auto ioCalls = IODeviceLabCounts::snapshot().delta(ioBefore);
    auto byteCalls = byteArrayConsumerSnapshot().delta(byteBefore);
    // All five File scopes are complete; serialize outside every consumer
    // measurement and retain this snapshot for all three acknowledged frames.
    m_behaviorFileProof = recorder.toJson(hexEncode(saveBytes), hexEncode(found));
    // Keep the original consumers and receipts intact; only the saved raw
    // main-thread intervals contribute to the new per-operation proof.
    JsonArray byteScopeProof;
    for (size_t i = 0; i != byteScopeCount; ++i)
      byteScopeProof.append(JsonObject{{"method", byteScopes[i].method}, {"completed", true},
          {"calls", byteScopes[i].calls.toJson()}});
    char const* byteBackend = "cpp";
#ifdef STAR_USE_RUST_BYTE_ARRAY
    byteBackend = "rust";
#endif
    m_behaviorBufferProof = JsonObject{{"version", 1}, {"backend", backend},
        {"nativeObservedCalls", nativeCalls}, {"scopes", std::move(scopes)},
        {"calls", std::move(bufferCalls)},
        {"byteArray", JsonObject{{"version", 1}, {"backend", byteBackend},
            {"scopeThread", "main"}, {"captureExcluded", true},
            {"calls", byteCalls.toJson()}, {"scopes", std::move(byteScopeProof)}}},
        {"ioDevice", JsonObject{{"version", 1}, {"backend", ioBackend},
            {"scopeThread", "main"}, {"captureExcluded", true},
            {"calls", std::move(ioCalls)}, {"scopes", std::move(ioScopes)},
            {"png", JsonObject{{"source", "Root::assets()->bytes(/behaviorlab/buffer.png)"},
                {"decoder", "Image::readPng(Buffer)"},
                {"sourceSize", JsonArray{sourceImage.width(), sourceImage.height()}},
                {"color", JsonArray{sourceColor[0], sourceColor[1], sourceColor[2], sourceColor[3]}}}}}},
        {"network", JsonObject{{"transport", "tcp"}, {"producer", "independent-literal-raw-sender"},
            {"inputEndpoint", strf("127.0.0.1:{}", port)}, {"chosenPort", port}, {"ownedBindSucceeded", true},
            {"rulesVersion", 5}, {"streamEnabled", false}, {"universeHandshake", false},
            {"expectedWireHex", expectedWire}, {"actualWireHex", hexEncode(wire.wire)}, {"sentWireHex", hexEncode(sentWire)},
            {"sendAttempts", sendAttempts}, {"stages", std::move(stages)}, {"parserEvents", std::move(wire.events)},
            {"acceptedPeerAddress", "127.0.0.1"}, {"acceptedPeerPort", acceptedPeer.port()},
            {"acceptedPeerSource", "OS-accept-sockaddr"}, {"clientLocalOsAvailable", false},
            {"receivedTexts", std::move(receivedTexts)}, {"receivedPacketCount", received.size()}}},
        {"save", JsonObject{{"filename", savePath}, {"wireHex", hexEncode(saveBytes)}, {"expectedWireHex", expectedSave}, {"value", decoded.toJson()},
            {"consumed", saveReader.pos()}, {"atEnd", saveReader.atEnd()}}},
        {"database", JsonObject{{"filename", databasePath}, {"key", "buffer-payload"}, {"blockSize", 512},
            {"pagesHex", hexEncode(File::readFile(databasePath))}, {"foundHex", hexEncode(found)},
            {"memoryPagesHex", hexEncode(memoryPages)}, {"memoryFoundHex", hexEncode(memoryFound)},
            {"memoryValue", memoryValue.toJson()}, {"memoryConsumed", memoryReader.pos()}, {"memoryAtEnd", memoryReader.atEnd()},
            {"value", databaseValue.toJson()}, {"consumed", colorReader.pos()}, {"atEnd", colorReader.atEnd()}}},
        {"visual", JsonObject{{"imagePath", path}, {"color", JsonArray{color[0], color[1], color[2], color[3]}}, {"sourceSize", JsonArray{16, 16}},
            {"displaySize", JsonArray{64, 64}}, {"scale", 4}, {"label", label}}}};
  }
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright) return;
  auto visual = m_behaviorBufferProof.get("visual");
  auto drawable = Drawable::makeImage(visual.getString("imagePath"),
      visual.getFloat("scale") * 0.5f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::prepareBehaviorDataStreamFrame() {
  if (m_behaviorDataStreamProof.isNull()) {
    auto before = DataStreamLabCounts::snapshot();
    JsonArray scopes;
    uint64_t nativeCalls = 0;
    auto observed = [&](String const& method, auto&& operation) {
      auto start = DataStreamLabCounts::snapshot();
      operation();
      ++nativeCalls;
      scopes.append(JsonObject{{"method", method}, {"completed", true},
          {"calls", DataStreamLabCounts::snapshot().delta(start)}});
    };
    TcpSocketPtr listener;
    HostAddressWithPort parsed;
    uint16_t port = 0;
    for (uint16_t candidate = 40201; candidate <= 40232; ++candidate) {
      parsed = HostAddressWithPort(strf("127.0.0.1:{}", candidate));
      if (!(parsed.address() == HostAddress::localhost(NetworkMode::IPv4)) || parsed.port() != candidate)
        throw StarException("BehaviorLab: unsafe DataStream bind identity");
      try { listener = TcpSocket::listen(parsed); port = candidate; break; }
      catch (NetworkException const&) {}
    }
    if (!listener) throw StarException("BehaviorLab: no owned DataStream port");
    listener->setNonBlocking(true);
    auto rawA = TcpSocket::connectTo(parsed);
    TcpSocketPtr rawB;
    auto deadline = Time::monotonicMilliseconds() + 2000;
    while (!rawB && Time::monotonicMilliseconds() < deadline) rawB = listener->accept();
    if (!rawB) throw StarException("BehaviorLab: DataStream accept deadline");
    auto acceptedPeer = rawB->remoteAddress();
    auto clientLocal = rawA->localAddress();
    if (!(acceptedPeer.address() == HostAddress::localhost(NetworkMode::IPv4)) || !acceptedPeer.port()
        || !(rawB->localAddress() == parsed) || !(rawA->remoteAddress() == parsed))
      throw StarException("BehaviorLab: DataStream owned peer mismatch");
    listener->close();
    auto a = TcpPacketSocket::open(rawA), b = TcpPacketSocket::open(rawB);
    a->setNetRules(NetCompatibilityRules(VersionNumber(5)));
    b->setNetRules(NetCompatibilityRules(VersionNumber(5)));
    a->setCompressionStreamEnabled(false); b->setCompressionStreamEnabled(false);
    DataStreamLabWire wire;
    wire.socket = a.get();
    struct Armed {
      explicit Armed(DataStreamLabWire* p) {
        if (DataStreamLabActiveWire) throw StarException("BehaviorLab: nested DataStream wire observer");
        DataStreamLabActiveWire = p;
      }
      ~Armed() { DataStreamLabActiveWire = nullptr; }
    } armed(&wire);
    observed("TcpPacketSocket::sendPackets(ChatSendPacket)", [&] {
      a->sendPackets({make_shared<ChatSendPacket>("STREAM", ChatSendMode::Broadcast, JsonObject{})});
    });
    List<PacketPtr> received;
    observed("TcpPacketSocket::writeData/readData/receivePackets", [&] {
      deadline = Time::monotonicMilliseconds() + 2000;
      while (Time::monotonicMilliseconds() < deadline) {
        if (auto ready = Socket::poll({{rawA, {true, false}}, {rawB, {true, false}}}, 0))
          for (auto const& peer : *ready)
            if (peer.second.exception) throw StarException("BehaviorLab: DataStream TCP EOF/error");
        a->writeData(); b->readData(); received.appendAll(b->receivePackets());
        if (!a->sentPacketsPending() && !received.empty()) break;
      }
      b->readData(); received.appendAll(b->receivePackets());
    });
    // Source anchor: packet type 0x12, signed VLQ(9)=0x12, String
    // length6, STREAM, broadcast enum0, empty JsonObject length0. No codec here.
    String const expectedWire = "12120653545245414d0000";
    if (a->sentPacketsPending() || received.size() != 1 || hexEncode(wire.wire) != expectedWire
        || wire.attempts == 0 || wire.attempts != wire.completions)
      throw StarException("BehaviorLab: DataStream actual TCP frame/count mismatch");
    auto chat = std::dynamic_pointer_cast<ChatSendPacket>(received.first());
    if (!chat || chat->text != "STREAM" || chat->sendMode != ChatSendMode::Broadcast || !chat->data.empty())
      throw StarException("BehaviorLab: DataStream typed packet mismatch");
    DataStreamLabActiveWire = nullptr;
    a->close(); b->close();

    // Startup already bound Root storage to a strict canonical descendant of
    // the sentinel-owned output. Reject existing files, including swap files.
    namespace fs = std::filesystem;
    auto storage = fs::canonical(fs::path(m_root->toStoragePath("").utf8()));
    auto declared = fs::canonical(fs::path(BehaviorLab::configuration().getString("storageDirectory").utf8()));
    if (storage != declared) throw StarException("BehaviorLab: DataStream storage binding drift");
    String savePath((storage / "datastream-save.sbvj").string());
    String databasePath((storage / "datastream-color.btree").string());
    for (auto const& path : {savePath, savePath + ".new", databasePath})
      if (fs::symlink_status(fs::path(path.utf8())).type() != fs::file_type::not_found)
        throw StarException("BehaviorLab: DataStream refuses existing owned output");
    auto value = VersionedJson::fromJson(JsonObject{{"id", "datastreamlab"}, {"version", 1},
        {"content", JsonArray{200, 112, 48, 255}}, {"subVersions", JsonObject{}}});
    observed("VersionedJson::writeFile", [&] { VersionedJson::writeFile(value, savePath); });
    VersionedJson decoded;
    observed("VersionedJson::readFile", [&] { decoded = VersionedJson::readFile(savePath); });
    auto saveBytes = File::readFile(savePath);
    // Single-key trailer and integer-array content have a fixed source-derived
    // encoding: SBVJ01, id, Maybe<u32>, Json array, u32 trailer version,
    // one-entry subVersions map containing an empty Json object.
    String const expectedSave = "5342564a30310d6461746173747265616d6c616201000000010604048310048160046004837e00000001010b73756256657273696f6e730700";
    if (hexEncode(saveBytes) != expectedSave)
      throw StarException("BehaviorLab: DataStream independent save bytes mismatch");
    DataStreamBuffer saveReader(saveBytes);
    VersionedJson inspected;
    observed("VersionedJson::readSubVersioning(owned file bytes)", [&] {
      if (saveReader.readBytes(VersionedJson::MagicStringSize) != ByteArray("SBVJ01", 6))
        throw StarException("BehaviorLab: DataStream save magic mismatch");
      saveReader.read(inspected); VersionedJson::readSubVersioning(saveReader, inspected);
    });
    if (decoded.toJson() != value.toJson() || inspected.toJson() != value.toJson() || !saveReader.atEnd())
      throw StarException("BehaviorLab: DataStream save schema/data/EOF mismatch");
    // Buffer::resize does not initialize growth. Seed the entire bounded
    // backing allocation before truncating so unused database-header bytes
    // are defined, like the real file device's zero-filled extension.
    auto memoryDevice = make_shared<Buffer>(ByteArray(8192, 0));
    memoryDevice->resize(0);
    ByteArray memoryPages, memoryFound;
    observed("BTreeSha256Database::open/insert/commit/close(memory)", [&] {
      BTreeSha256Database db("datastreamlab");
      db.setIODevice(memoryDevice); db.setBlockSize(512); db.setAutoCommit(false);
      if (!db.open() || db.insert(String("color"), saveBytes))
        throw StarException("BehaviorLab: DataStream memory database initial state mismatch");
      db.commit();
      if (memoryDevice->size() > 8192) throw StarException("BehaviorLab: DataStream initialized memory extent exceeded");
      memoryPages = memoryDevice->data(); db.close(false);
    });
    observed("BTreeSha256Database::open/find/close(memory)", [&] {
      BTreeSha256Database db("datastreamlab"); db.setIODevice(memoryDevice);
      if (db.open()) throw StarException("BehaviorLab: DataStream memory database lost pages");
      auto result = db.find(String("color"));
      if (!result || *result != saveBytes) throw StarException("BehaviorLab: DataStream memory database mismatch");
      memoryFound = *result; db.close(false);
    });
    // BTree uses its real file device, commits, closes, then reopens independently.
    ByteArray found;
    observed("BTreeSha256Database::open/insert/commit/close(file)", [&] {
      auto device = File::open(databasePath, IOMode::ReadWrite | IOMode::Truncate);
      BTreeSha256Database db("datastreamlab");
      db.setIODevice(device); db.setBlockSize(512); db.setAutoCommit(false);
      if (!db.open() || db.insert(String("color"), saveBytes))
        throw StarException("BehaviorLab: DataStream database initial state mismatch");
      db.commit(); db.close(true);
    });
    observed("BTreeSha256Database::open/find/close(file)", [&] {
      BTreeSha256Database db("datastreamlab");
      db.setIODevice(File::open(databasePath, IOMode::ReadWrite));
      if (db.open()) throw StarException("BehaviorLab: DataStream database lost committed file");
      auto result = db.find(String("color"));
      if (!result) throw StarException("BehaviorLab: DataStream database missing key");
      found = *result; db.close(true);
    });
    if (found != saveBytes) throw StarException("BehaviorLab: DataStream database value mismatch");
    DataStreamBuffer colorReader(found);
    VersionedJson databaseValue;
    observed("VersionedJson::readSubVersioning(BTree value)", [&] {
      if (colorReader.readBytes(6) != ByteArray("SBVJ01", 6))
        throw StarException("BehaviorLab: DataStream database value magic mismatch");
      colorReader.read(databaseValue); VersionedJson::readSubVersioning(colorReader, databaseValue);
    });
    if (databaseValue.toJson() != decoded.toJson() || !colorReader.atEnd())
      throw StarException("BehaviorLab: DataStream database decoded value/EOF mismatch");
    auto components = databaseValue.content.toArray();
    Vec4B color(components[0].toUInt(), components[1].toUInt(), components[2].toUInt(), components[3].toUInt());
    String path = strf("/behaviorlab/datastream.png?multiply={:02x}{:02x}{:02x}{:02x}", color[0], color[1], color[2], color[3]);
    auto image = m_root->assets()->image(path);
    if (image->size() != Vec2U(16, 16)) throw StarException("BehaviorLab: DataStream image dimensions");
    for (unsigned y = 0; y != 16; ++y)
      for (unsigned x = 0; x != 16; ++x)
        if (image->get(x, y) != color) throw StarException("BehaviorLab: DataStream Assets pixels mismatch");
    String backend = "cpp";
#ifdef STAR_USE_RUST_DATA_STREAM
    backend = "rust";
#endif
    m_behaviorDataStreamProof = JsonObject{{"version", 1}, {"backend", backend},
        {"nativeObservedCalls", nativeCalls}, {"scopes", std::move(scopes)},
        {"calls", DataStreamLabCounts::snapshot().delta(before)},
        {"network", JsonObject{{"transport", "tcp"}, {"inputEndpoint", strf("127.0.0.1:{}", port)},
            {"chosenPort", port}, {"ownedBindSucceeded", true}, {"rulesVersion", 5}, {"streamEnabled", false},
            {"universeHandshake", false}, {"expectedWireHex", expectedWire}, {"actualWireHex", hexEncode(wire.wire)},
            {"sendAttempts", wire.attempts}, {"sendCompletions", wire.completions},
            {"acceptedPeerAddress", "127.0.0.1"}, {"acceptedPeerPort", acceptedPeer.port()},
            {"acceptedPeerSource", "OS-accept-sockaddr"}, {"clientLocalOsAvailable", false},
            {"clientLocalCachePort", clientLocal.port()}, {"sentText", "STREAM"}, {"receivedText", chat->text},
            {"sentMode", 0}, {"receivedMode", unsigned(chat->sendMode)}, {"receivedData", chat->data},
            {"receivedPacketCount", received.size()}, {"pending", false}}},
        {"save", JsonObject{{"filename", savePath}, {"wireHex", hexEncode(saveBytes)}, {"expectedWireHex", expectedSave}, {"value", decoded.toJson()},
            {"consumed", saveReader.pos()}, {"atEnd", saveReader.atEnd()}}},
        {"database", JsonObject{{"filename", databasePath}, {"key", "color"}, {"blockSize", 512},
            {"pagesHex", hexEncode(File::readFile(databasePath))}, {"foundHex", hexEncode(found)},
            {"memoryPagesHex", hexEncode(memoryPages)}, {"memoryFoundHex", hexEncode(memoryFound)},
            {"value", databaseValue.toJson()}, {"consumed", colorReader.pos()}, {"atEnd", colorReader.atEnd()}}},
        {"visual", JsonObject{{"imagePath", path}, {"color", databaseValue.content}, {"sourceSize", JsonArray{16, 16}},
            {"displaySize", JsonArray{64, 64}}, {"scale", 4}, {"label", chat->text}}}};
  }
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright) return;
  auto visual = m_behaviorDataStreamProof.get("visual");
  auto drawable = Drawable::makeImage(visual.getString("imagePath"),
      visual.getFloat("scale") * 0.5f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::prepareBehaviorHostAddressFrame() {
  if (m_behaviorHostAddressProof.isNull()) {
    JsonArray scopes;
    uint64_t nativeCalls = 0;
    auto observed = [&](String const& name, auto&& operation) {
      auto before = HostAddressLabCounts::snapshot();
      auto result = operation();
      ++nativeCalls;
      scopes.append(JsonObject{{"method", name}, {"completed", true},
          {"calls", HostAddressLabCounts::snapshot().delta(before)}});
      return result;
    };
    auto before = HostAddressLabCounts::snapshot();
    auto endpointText = [](HostAddressWithPort const& endpoint) {
      std::ostringstream stream;
      stream << endpoint;
      return String(stream.str());
    };
    auto hostText = [](HostAddress const& host) {
      std::ostringstream stream;
      stream << host;
      return String(stream.str());
    };
    auto endpointRecord = [&](HostAddressWithPort const& endpoint) {
      auto address = endpoint.address();
      JsonArray bytes;
      for (size_t i = 0; i != address.size(); ++i) bytes.append(address.octet(i));
      return Json(JsonObject{{"mode", int(address.mode())}, {"bytes", std::move(bytes)},
          {"size", address.size()}, {"isLocalHost", address.isLocalHost()}, {"isZero", address.isZero()},
          {"hash", uint64_t(hash<HostAddress>()(address))}, {"text", hostText(address)},
          {"port", endpoint.port()}, {"endpointText", endpointText(endpoint)},
          {"endpointHash", uint64_t(hash<HostAddressWithPort>()(endpoint))}});
    };
    TcpSocketPtr listener;
    HostAddressWithPort parsed;
    String input;
    uint16_t port = 0;
    for (uint16_t candidate = 40169; candidate <= 40200; ++candidate) {
      input = strf("127.0.0.1:{}", candidate);
      parsed = observed("HostAddressWithPort::HostAddressWithPort(String)", [&] { return HostAddressWithPort(input); });
      auto bindHost = parsed.address();
      if (parsed.port() != candidate || bindHost.mode() != NetworkMode::IPv4 || bindHost.size() != 4
          || bindHost.octet(0) != 127 || bindHost.octet(1) != 0 || bindHost.octet(2) != 0 || bindHost.octet(3) != 1)
        throw StarException("BehaviorLab: HostAddress parser returned unsafe bind identity");
      try {
        listener = observed("TcpSocket::listen(parsed)", [&] { return TcpSocket::listen(parsed); });
        port = candidate;
        break;
      } catch (NetworkException const&) {}
    }
    if (!listener) throw StarException("BehaviorLab: no owned HostAddress loopback port");
    listener->setNonBlocking(true);
    // No connect occurs until THIS fixture owns the successfully bound listener.
    auto client = observed("TcpSocket::connectTo(parsed)", [&] { return TcpSocket::connectTo(parsed); });
    TcpSocketPtr server;
    auto deadline = Time::monotonicMilliseconds() + 2000;
    while (!server && Time::monotonicMilliseconds() < deadline)
      server = observed("TcpSocket::accept()", [&] { return listener->accept(); });
    if (!server) throw StarException("BehaviorLab: HostAddress accept deadline");
    auto listenerLocal = listener->localAddress();
    listener->close();
    auto clientLocal = client->localAddress();
    auto clientRemote = client->remoteAddress();
    auto serverLocal = server->localAddress();
    auto serverRemote = server->remoteAddress();
    auto actualPeer = serverRemote.address();
    if (port < 40169 || port > 40200 || parsed.port() != port || !(listenerLocal == parsed)
        || !(serverLocal == clientRemote) || !(serverLocal == parsed)
        || actualPeer.mode() != NetworkMode::IPv4 || actualPeer.size() != 4
        || actualPeer.octet(0) != 127 || actualPeer.octet(1) != 0 || actualPeer.octet(2) != 0 || actualPeer.octet(3) != 1
        || serverRemote.port() == 0 || !actualPeer.isLocalHost() || actualPeer.isZero())
      throw StarException("BehaviorLab: HostAddress owned TCP identities mismatch");
    // Independent numeric anchors: PL101 host hash and native size_t wrapping
    // combine, not another invocation of the migrated hash to predict itself.
    size_t hostHash = ((size_t(127) * 101) * 101) * 101 + 1;
    size_t endpointHash = hostHash ^ (size_t(port) * 2654435761ULL + 0x9e3779b9ULL + (hostHash << 6) + (hostHash >> 2));
    if (hash<HostAddress>()(actualPeer) != hostHash || hash<HostAddressWithPort>()(parsed) != endpointHash)
      throw StarException("BehaviorLab: HostAddress independent hash mismatch");
    auto sent = observed("operator<<(HostAddress accepted OS peer)", [&] { return hostText(actualPeer); });
    auto a = TcpPacketSocket::open(client);
    auto b = TcpPacketSocket::open(server);
    a->setNetRules(NetCompatibilityRules(VersionNumber(5)));
    b->setNetRules(NetCompatibilityRules(VersionNumber(5)));
    a->setCompressionStreamEnabled(false);
    b->setCompressionStreamEnabled(false);
    a->sendPackets({make_shared<ChatSendPacket>(sent, ChatSendMode::Broadcast, JsonObject{})});
    List<PacketPtr> received;
    deadline = Time::monotonicMilliseconds() + 2000;
    while (Time::monotonicMilliseconds() < deadline) {
      if (auto ready = Socket::poll({{client, {true, false}}, {server, {true, false}}}, 0))
        for (auto const& peer : *ready)
          if (peer.second.exception) throw StarException("BehaviorLab: HostAddress TCP EOF/error");
      a->writeData(); b->readData();
      received.appendAll(b->receivePackets());
      if (!a->sentPacketsPending() && !received.empty()) break;
    }
    if (a->sentPacketsPending() || received.size() != 1)
      throw StarException("BehaviorLab: HostAddress typed TCP deadline/count");
    auto chat = std::dynamic_pointer_cast<ChatSendPacket>(received.first());
    if (!chat || chat->text != sent || chat->sendMode != ChatSendMode::Broadcast || !chat->data.empty())
      throw StarException("BehaviorLab: HostAddress typed TCP payload mismatch");
    Vec4B color(16, 192, 128 + 16 * actualPeer.octet(3), 255);
    String path = strf("/behaviorlab/host-address.png?multiply={:02x}{:02x}{:02x}{:02x}", color[0], color[1], color[2], color[3]);
    auto image = m_root->assets()->image(path);
    if (image->size() != Vec2U(16, 16)) throw StarException("BehaviorLab: HostAddress image dimensions");
    for (unsigned y = 0; y != 16; ++y)
      for (unsigned x = 0; x != 16; ++x)
        if (image->get(x, y) != color) throw StarException("BehaviorLab: HostAddress normal Assets pixel mismatch");
    auto parsedRecord = endpointRecord(parsed);
    auto listenerRecord = endpointRecord(listenerLocal);
    auto clientLocalRecord = endpointRecord(clientLocal);
    auto clientRemoteRecord = endpointRecord(clientRemote);
    auto serverLocalRecord = endpointRecord(serverLocal);
    auto serverRemoteRecord = endpointRecord(serverRemote);
    String backend = "cpp";
#ifdef STAR_USE_RUST_HOST_ADDRESS
    backend = "rust";
#endif
    m_behaviorHostAddressProof = JsonObject{{"version", 1}, {"backend", backend},
        {"inputEndpoint", input}, {"chosenPort", port}, {"ownedBindSucceeded", true},
        {"parsed", parsedRecord}, {"listenerLocal", listenerRecord},
        {"clientLocal", clientLocalRecord}, {"clientRemote", clientRemoteRecord},
        {"serverLocal", serverLocalRecord}, {"serverRemote", serverRemoteRecord},
        {"addressSources", JsonObject{{"listenerLocal", "cached-bind-input"},
            {"clientLocal", "unpopulated-default-NOT-OS-getsockname"}, {"clientRemote", "cached-connect-input"},
            {"serverLocal", "cached-listener-input"}, {"serverRemote", "OS-accept-sockaddr"}}},
        {"clientLocalOsAvailable", false}, {"nativeObservedCalls", nativeCalls}, {"scopes", std::move(scopes)},
        {"calls", HostAddressLabCounts::snapshot().delta(before)},
        {"network", JsonObject{{"transport", "tcp"}, {"rulesVersion", 5}, {"streamEnabled", false},
            {"universeHandshake", false}, {"sentText", sent}, {"receivedText", chat->text},
            {"sendMode", unsigned(chat->sendMode)}, {"data", chat->data}}},
        {"visual", JsonObject{{"imagePath", path}, {"color", JsonArray{color[0], color[1], color[2], color[3]}},
            {"sourceSize", JsonArray{16, 16}}, {"displaySize", JsonArray{64, 64}},
            {"scale", 4}, {"label", chat->text}}}};
    a->close(); b->close();
  }
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright) return;
  auto visual = m_behaviorHostAddressProof.get("visual");
  auto drawable = Drawable::makeImage(visual.getString("imagePath"),
      visual.getFloat("scale") * 0.5f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::prepareBehaviorPathEmbedFrame() {
  m_behaviorPathEmbedSubmitted = false;
  if (m_behaviorPathEmbedProof.isNull()) {
    auto assets = m_root->assets();
    String const proofPath = "/behaviorlab/path-embed-proof.json";
    if (!assets->assetExists(proofPath))
      throw StarException("BehaviorLab: PathEmbed Lua output missing (postLoad errors are fatal here)");
    auto source = assets->json(proofPath);
    auto measurement = source.get("measurement");
    auto path = source.getString("basePath");
    auto cropPath = source.getString("cropPath");
    Json const frameModel = JsonObject{{"frameList", JsonObject{{"reserved%:?;/", JsonArray{16, 0, 32, 16}},
        {"wrong", JsonArray{0, 0, 16, 16}}}}, {"aliases", JsonObject{{"crop", "reserved%:?;/"}}}};
    if (source.size() != 9 || !source.get("version").isType(Json::Type::Int) || source.getInt("version") != 1
        || source.getString("selectedAlias") != "crop" || source.getString("reservedFrameName") != "reserved%:?;/"
        || source.get("seedSize") != Json(JsonArray{32, 16}) || source.get("selectedRect") != Json(JsonArray{16, 0, 32, 16})
        || source.get("wrongRect") != Json(JsonArray{0, 0, 16, 16}) || cropPath != path + ":crop"
        || measurement.size() != 13 || measurement.getString("backend") != PathEmbedLab::backend()
        || !measurement.get("version").isType(Json::Type::Int) || measurement.getInt("version") != 1
        || measurement.getString("scopeThread") != "lua-calling-thread" || !measurement.getBool("completed")
        || !measurement.get("operationCount").isType(Json::Type::Int) || measurement.getInt("operationCount") != 1
        || measurement.getString("method") != "None" || measurement.getString("framesMode") != "text"
        || measurement.getString("path") != path || Json::parse(measurement.getString("rawFrames")) != frameModel)
      throw StarException("BehaviorLab: PathEmbed source/measurement fields differ");
    auto parts = path.split(";");
    if (parts.size() != 6 || parts[0] != "/opensb_data" || parts[1] != "image"
        || parts[3] != "frames" || parts[4] != "text" || parts[5] != measurement.getString("escapedFrames"))
      throw StarException("BehaviorLab: PathEmbed None/text path differs");
    if (parts[5].split("reserved%%%c%q%s%b").size() != 3)
      throw StarException("BehaviorLab: PathEmbed independent escaped name literal differs");
    for (auto name : {"selector", "escape"}) {
      auto before = measurement.get("before"), after = measurement.get("after"), delta = measurement.get("delta");
      uint64_t expected = String(PathEmbedLab::backend()) == "rust" ? 1 : 0;
      if (before.size() != 2 || after.size() != 2 || delta.size() != 2
          || !before.get(name).isType(Json::Type::Int) || !after.get(name).isType(Json::Type::Int)
          || !delta.get(name).isType(Json::Type::Int) || before.getInt(name) < 0 || after.getInt(name) < 0
          || after.getUInt(name) < before.getUInt(name) || after.getUInt(name) - before.getUInt(name) != expected
          || delta.getUInt(name) != expected || (!expected && before.getUInt(name) != 0))
        throw StarException("BehaviorLab: PathEmbed executing-thread completed counters differ");
    }
    uint8_t loopbackBytes[4] = {127, 0, 0, 1};
    HostAddress const loopback(NetworkMode::IPv4, loopbackBytes);
    TcpSocketPtr listener;
    uint16_t port = 0;
    for (uint16_t candidate = 40265; candidate <= 40296; ++candidate) {
      try {
        listener = TcpSocket::listen(HostAddressWithPort(loopback, candidate));
        port = candidate;
        break;
      } catch (NetworkException const&) {}
    }
    if (!listener) throw StarException("BehaviorLab: no owned PathEmbed loopback port");
    listener->setNonBlocking(true);
    auto rawA = TcpSocket::connectTo(HostAddressWithPort(loopback, port));
    TcpSocketPtr rawB;
    auto deadline = Time::monotonicMilliseconds() + 2000;
    while (!rawB && Time::monotonicMilliseconds() < deadline) rawB = listener->accept();
    if (!rawB) throw StarException("BehaviorLab: PathEmbed TCP accept deadline");
    listener->close();
    auto a = TcpPacketSocket::open(rawA), b = TcpPacketSocket::open(rawB);
    a->setNetRules(NetCompatibilityRules(VersionNumber(5)));
    b->setNetRules(NetCompatibilityRules(VersionNumber(5)));
    a->setCompressionStreamEnabled(false);
    b->setCompressionStreamEnabled(false);
    JsonArray rounds;
    auto transfer = [&](String const& text) {
      a->sendPackets({make_shared<ChatSendPacket>(text, ChatSendMode::Broadcast, JsonObject{})});
      List<PacketPtr> received;
      auto until = Time::monotonicMilliseconds() + 2000;
      while (Time::monotonicMilliseconds() < until) {
        if (auto ready = Socket::poll({{rawA, {true, false}}, {rawB, {true, false}}}, 0))
          for (auto const& peer : *ready)
            if (peer.second.exception) throw StarException("BehaviorLab: PathEmbed TCP EOF/error");
        a->writeData(); b->readData();
        received.appendAll(b->receivePackets());
        if (!a->sentPacketsPending() && !received.empty()) break;
      }
      b->readData(); received.appendAll(b->receivePackets());
      a->readData();
      if (!a->isOpen() || !b->isOpen() || a->sentPacketsPending() || received.size() != 1
          || !a->receivePackets().empty())
        throw StarException("BehaviorLab: PathEmbed TCP deadline/count/reverse traffic");
      auto chat = std::dynamic_pointer_cast<ChatSendPacket>(received.first());
      if (!chat || chat->text != text || chat->sendMode != ChatSendMode::Broadcast || !chat->data.empty())
        throw StarException("BehaviorLab: PathEmbed typed TCP payload differs");
      rounds.append(JsonObject{{"direction", "a-to-b"}, {"sentText", text}, {"receivedText", chat->text},
          {"sendMode", unsigned(chat->sendMode)}, {"receivedData", chat->data}});
      return chat->text;
    };
    auto receivedBase = transfer(path);
    auto receivedCrop = transfer(cropPath);
    auto receivedLabel = transfer("PATHEMBED");
    a->close(); b->close();
    // Two declared normal acquisitions, never a predecoded Lua PNG/proxy. The
    // alias image alone does not keep the embedded base alive across cache TTL.
    m_behaviorPathEmbedBaseImage = assets->image(receivedBase);
    ++m_behaviorPathEmbedBaseAcquisitions;
    m_behaviorPathEmbedBaseIdentity = m_behaviorPathEmbedBaseImage.get();
    m_behaviorPathEmbedCropImage = assets->image(receivedCrop);
    ++m_behaviorPathEmbedCropAcquisitions;
    m_behaviorPathEmbedCropIdentity = m_behaviorPathEmbedCropImage.get();
    auto frames = assets->imageFrames(receivedBase);
    Json const expectedFrames = JsonObject{{"file", "<embedded frames>"},
        {"frames", frameModel.get("frameList")}, {"aliases", frameModel.get("aliases")}};
    if (!frames || frames->toJson() != expectedFrames || frames->getRect("crop") != Maybe<RectU>(RectU(16, 0, 32, 16)))
      throw StarException("BehaviorLab: PathEmbed normal Assets text.frames/alias bounds differ");
    // Fail immediately on bad decoding, then observe the same originals again
    // after painting each captured stage.
    PathEmbedLab::imageJson(*m_behaviorPathEmbedBaseImage, false);
    PathEmbedLab::imageJson(*m_behaviorPathEmbedCropImage, true);
    m_behaviorPathEmbedProof = JsonObject{{"version", 1}, {"backend", PathEmbedLab::backend()},
        {"source", source}, {"parsedFrames", frames->toJson()},
        {"network", JsonObject{{"transport", "tcp"}, {"address", "127.0.0.1"}, {"rulesVersion", 5},
            {"streamEnabled", false}, {"universeHandshake", false}, {"ownedBindSucceeded", true}, {"rounds", std::move(rounds)}}},
        {"visual", JsonObject{{"imagePath", receivedCrop}, {"basePath", receivedBase}, {"scale", 4},
            {"displaySize", JsonArray{64, 64}}, {"center", JsonArray{64, 48}}, {"fullbright", true},
            {"consumer", "WorldPainter.foregroundOverlays"}, {"label", receivedLabel}}}};
  }
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright) return;
  auto visual = m_behaviorPathEmbedProof.get("visual");
  auto drawable = Drawable::makeImage(visual.getString("imagePath"),
      visual.getFloat("scale") * 0.5f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
  m_behaviorPathEmbedSubmitted = true;
}

void ClientApplication::prepareBehaviorZstdFrame() {
  // Run before the frame-ready guard: the first normal Assets image lookup must
  // be driven by the actual TCP-received path, not a Lua preload or proxy.
  if (m_behaviorZstdProof.isNull()) {
    auto source = zstdLabImageProof();
    if (!source.contains("embed") || source.contains("decode"))
      throw StarException("BehaviorLab: Zstd producer missing or image was preloaded");
    auto path = source.get("embed").getString("path");
    if (!path.beginsWith("/opensb_data;bin;zstd;"))
      throw StarException("BehaviorLab: Zstd producer path mismatch");
    uint8_t loopbackBytes[4] = {127, 0, 0, 1};
    HostAddress const loopback(NetworkMode::IPv4, loopbackBytes);
    TcpSocketPtr listener;
    uint16_t port = 0;
    for (uint16_t candidate = 40137; candidate <= 40168; ++candidate) {
      try {
        listener = TcpSocket::listen(HostAddressWithPort(loopback, candidate));
        port = candidate;
        break;
      } catch (NetworkException const&) {}
    }
    if (!listener) throw StarException("BehaviorLab: no owned Zstd loopback port");
    listener->setNonBlocking(true);
    // Connect ONLY after our own listener has bound this numeric loopback port.
    auto rawA = TcpSocket::connectTo(HostAddressWithPort(loopback, port));
    TcpSocketPtr rawB;
    auto deadline = Time::monotonicMilliseconds() + 2000;
    while (!rawB && Time::monotonicMilliseconds() < deadline) rawB = listener->accept();
    if (!rawB) throw StarException("BehaviorLab: Zstd accept deadline");
    listener->close();
    auto a = TcpPacketSocket::open(rawA);
    auto b = TcpPacketSocket::open(rawB);
    a->setNetRules(NetCompatibilityRules(VersionNumber(5)));
    b->setNetRules(NetCompatibilityRules(VersionNumber(5)));
    a->setCompressionStreamEnabled(true);
    b->setCompressionStreamEnabled(true);
    // Manual native PacketSocket configuration, NOT Universe negotiation.
    auto arena = std::make_unique<ZstdLabArena>();
    arena->a = a.get(); arena->b = b.get();
    struct Armed {
      Armed(ZstdLabArena* p) { if (ZstdLabActive) throw StarException("BehaviorLab: nested Zstd observer"); ZstdLabActive = p; }
      ~Armed() { ZstdLabActive = nullptr; }
    } armed(arena.get());
    bool rust = false;
    String backend = "cpp";
#ifdef STAR_USE_RUST_ZSTD
    rust = true; backend = "rust";
#endif
    auto requireCalls = [&](ZstdLabCounts const& calls, unsigned kind) {
      for (unsigned k = 0; k != 4; ++k)
        for (unsigned e = 0; e != 3; ++e)
          if (calls.values[k][e] != uint64_t(rust && k == kind && e < 2))
            throw StarException("BehaviorLab: Zstd native receipt mismatch");
    };
    // Independent literal framing, not DataStream or a replacement Packet codec.
    auto uv = [](ByteArray& out, uint64_t n) {
      unsigned shift = 0;
      while ((n >> shift) > 127) shift += 7;
      for (; shift; shift -= 7) out.appendByte(char(((n >> shift) & 127) | 128));
      out.appendByte(char(n & 127));
    };
    auto expectedPacket = [&](String const& text) {
      ByteArray payload;
      uv(payload, text.utf8Size()); payload.append(text.utf8Ptr(), text.utf8Size());
      payload.appendByte(0); payload.appendByte(0);
      ByteArray out; out.appendByte(0x12); uv(out, 2 * payload.size()); out.append(payload);
      return out;
    };
    if (hexEncode(expectedPacket("ZSTD")) != "120e045a5354440000")
      throw StarException("BehaviorLab: Zstd independent label literal mismatch");
    auto requirePeers = [&]() {
      // poll reports EOF/hangup and shuts down the raw peer; receive() alone
      // returns zero for both EAGAIN and EOF on this native socket API.
      if (auto ready = Socket::poll({{rawA, {true, false}}, {rawB, {true, false}}}, 0))
        for (auto const& peer : *ready)
          if (peer.second.exception) throw StarException("BehaviorLab: Zstd TCP EOF/error");
      if (!a->isOpen() || !b->isOpen()) throw StarException("BehaviorLab: closed Zstd TCP peer");
    };
    JsonArray rounds;
    auto round = [&](TcpPacketSocket* sender, TcpPacketSocket* receiver, String const& text, String const& direction) {
      size_t first = arena->count;
      auto packet = make_shared<ChatSendPacket>(text, ChatSendMode::Broadcast, JsonObject{});
      sender->sendPackets({packet});
      List<PacketPtr> received;
      auto until = Time::monotonicMilliseconds() + 2000;
      while (Time::monotonicMilliseconds() < until) {
        requirePeers();
        sender->writeData(); receiver->readData();
        received.appendAll(receiver->receivePackets());
        if (!sender->sentPacketsPending() && !received.empty()) break;
      }
      requirePeers();
      receiver->readData(); received.appendAll(receiver->receivePackets());
      sender->readData();
      if (!sender->receivePackets().empty()) throw StarException("BehaviorLab: unexpected Zstd reverse traffic");
      if (sender->sentPacketsPending() || received.size() != 1 || !arena->valid)
        throw StarException("BehaviorLab: Zstd TCP deadline/count/observer failure");
      auto chat = std::dynamic_pointer_cast<ChatSendPacket>(received.first());
      if (!chat || chat->text != text || chat->sendMode != ChatSendMode::Broadcast || !chat->data.empty())
        throw StarException("BehaviorLab: Zstd typed TCP packet mismatch");
      ByteArray ci, co, di, dout;
      JsonArray events;
      unsigned compressions = 0, decompressions = 0;
      for (size_t i = first; i != arena->count; ++i) {
        auto const& record = arena->records[i];
        requireCalls(record.calls, record.kind);
        ByteArray input(record.input, record.inputSize), output(record.output, record.outputSize);
        if (record.kind == 0) { ++compressions; ci.append(input); co.append(output); }
        else {
          if (record.kind != 1 || record.inputSize == 0 || record.inputSize > 1024)
            throw StarException("BehaviorLab: Zstd invalid TCP receive chunk");
          ++decompressions; di.append(input); dout.append(output);
        }
        events.append(JsonObject{{"kind", record.kind}, {"inputHex", hexEncode(input)},
            {"outputHex", hexEncode(output)}, {"calls", record.calls.json()}});
      }
      auto literal = expectedPacket(text);
      if (compressions != 1 || decompressions == 0 || ci != literal || co != di || dout != literal
          || (text.utf8Size() == 16384 && (co.size() <= 1024 || decompressions < 2)))
        throw StarException("BehaviorLab: Zstd actual native TCP wire mismatch");
      rounds.append(JsonObject{{"direction", direction}, {"textHex", hexEncode(text.utf8Bytes())},
          {"receivedHex", hexEncode(chat->text.utf8Bytes())}, {"sendMode", unsigned(packet->sendMode)},
          {"receivedMode", unsigned(chat->sendMode)}, {"receivedData", chat->data}, {"events", std::move(events)}});
      return chat->text;
    };
    auto receivedPath = round(a.get(), b.get(), path, "a-to-b");
    auto receivedLabel = round(b.get(), a.get(), "ZSTD", "b-to-a");
    std::string bulk; bulk.reserve(16384);
    uint32_t x = 0x12345678;
    for (unsigned i = 0; i != 16384; ++i) {
      x ^= x << 13; x ^= x >> 17; x ^= x << 5;
      bulk.push_back("0123456789abcdef"[(x >> 28) & 15]);
    }
    round(a.get(), b.get(), String(bulk), "a-to-b");
    ZstdLabActive = nullptr;
    auto image = m_root->assets()->image(receivedPath);
    // The one-decode fixture must own its original image through consumption.
    // Otherwise ordinary cache cleanup may evict it before the centered drawable
    // asks for dimensions/texture and the unchanged repeated-decode guard fires.
    m_behaviorZstdImage = image;
    auto imageProof = zstdLabImageProof();
    if (!imageProof.contains("decode") || !imageProof.contains("rgbaHex") || image->size() != Vec2U(16, 16))
      throw StarException("BehaviorLab: Zstd normal Assets decode missing");
    for (auto key : {"embed", "decode"}) {
      auto row = imageProof.get(key);
      auto calls = row.get("calls");
      unsigned kind = String(key) == "embed" ? 2 : 3;
      for (auto event : {"attempt", "success", "exception"}) {
        auto counts = calls.getArray(event);
        if (counts.size() != 4) throw StarException("BehaviorLab: Zstd image receipt shape");
        for (unsigned k = 0; k != 4; ++k)
          if (counts[k].toUInt() != uint64_t(rust && k == kind && String(event) != "exception"))
            throw StarException("BehaviorLab: Zstd image receipt mismatch");
      }
    }
    if (imageProof.get("embed").getString("path") != receivedPath
        || imageProof.get("decode").getString("path") != receivedPath
        || imageProof.get("embed").getString("compressedHex") != imageProof.get("decode").getString("compressedHex")
        || imageProof.get("embed").getString("pngHex") != imageProof.get("decode").getString("pngHex"))
      throw StarException("BehaviorLab: Zstd image producer/decoder mismatch");
    auto color = image->get(0, 0);
    m_behaviorZstdProof = JsonObject{{"version", 1}, {"backend", backend}, {"image", imageProof},
        {"network", JsonObject{{"transport", "tcp"}, {"address", "127.0.0.1"}, {"streamEnabled", true},
            {"rulesVersion", 5}, {"rounds", std::move(rounds)}}},
        {"visual", JsonObject{{"imagePath", receivedPath}, {"color", JsonArray{color[0], color[1], color[2], color[3]}},
            {"scale", 4}, {"label", receivedLabel}}}};
  }
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright) return;
  auto visual = m_behaviorZstdProof.get("visual");
  auto drawable = Drawable::makeImage(visual.getString("imagePath"),
      visual.getFloat("scale") * 0.5f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::prepareBehaviorCompressionFrame() {
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright)
    return;
  auto world = m_universeClient->worldClient();
  if (!world || !world->inWorld())
    return;
  if (m_behaviorCompressionProof.isNull()) {
    auto proof = compressionBehaviorAssetProof();
    String backend = "cpp";
    bool rust = false;
#ifdef STAR_USE_RUST_COMPRESSION
    backend = "rust";
    rust = true;
#endif
    if (proof.isNull() || proof.getUInt("version") != 1)
      throw StarException("BehaviorLab: compression native proof missing");
    auto operations = proof.get("operations");
    char const* names[] = {"embed", "zlib", "gzip"};
    for (unsigned k = 0; k != 3; ++k) {
      auto row = operations.get(names[k]);
      if (row.getString("backend") != backend || row.getString("path").empty()
          || row.getString("pngHex").empty() || row.getString("compressedHex").empty())
        throw StarException("BehaviorLab: compression native row missing");
      JsonArray expected;
      for (unsigned j = 0; j != 3; ++j) expected.append(rust && j == k ? 1 : 0);
      auto calls = row.get("calls");
      if (calls.getArray("attempt") != expected || calls.getArray("success") != expected
          || calls.getArray("exception") != JsonArray{0, 0, 0})
        throw StarException("BehaviorLab: compression controller receipts mismatch");
    }
    if (operations.get("embed").getString("path") != operations.get("zlib").getString("path")
        || operations.get("embed").getString("pngHex") != operations.get("zlib").getString("pngHex")
        || operations.get("embed").getString("compressedHex") != operations.get("zlib").getString("compressedHex"))
      throw StarException("BehaviorLab: compression producer/consumer mismatch");
    Json visual = JsonObject{{"imagePath", "/behaviorlab/compression-result.png"},
        {"color", JsonArray{96, 192, 224, 255}}, {"scale", 4}, {"label", "COMPRESS"}};
    if (proof.get("visual") != visual)
      throw StarException("BehaviorLab: compression visual mismatch");
    auto image = m_root->assets()->image(visual.getString("imagePath"));
    if (!compressionLabSource(*image))
      throw StarException("BehaviorLab: compression displayed result mismatch");
    m_behaviorCompressionProof = std::move(proof);
  }
  auto observedScale = m_behaviorCompressionProof.get("visual").getFloat("scale");
  auto drawable = Drawable::makeImage("/behaviorlab/compression-result.png",
      observedScale * 0.5f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::prepareBehaviorRandomMwcFrame() {
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright)
    return;
  auto world = m_universeClient->worldClient();
  if (!world || !world->inWorld())
    return;
  if (m_behaviorRandomMwcProof.isNull()) {
    auto proof = randomMwcBehaviorAssetProof();
    String backend = "cpp";
    bool rust = false;
#ifdef STAR_USE_RUST_RANDOM_MWC
    backend = "rust";
    rust = true;
#endif
    if (proof.isNull() || proof.getUInt("version") != 1
        || proof.getString("fixture") != "random-mwc-v1" || proof.getString("backend") != backend
        || !proof.getBool("complete") || !proof.getBool("sameUserdata"))
      throw StarException("BehaviorLab: missing or invalid random MWC native proof");
    auto counts = [rust](unsigned init, unsigned entropy, unsigned next) -> JsonArray {
      return rust ? JsonArray{init, entropy, next} : JsonArray{0, 0, 0};
    };
    JsonArray expected{
      JsonObject{{"op", "construct"}, {"seed", "31415926"}, {"calls", counts(1, 0, 0)}},
      JsonObject{{"op", "randu32"}, {"native", "2950892229"}, {"calls", counts(0, 0, 1)}},
      JsonObject{{"op", "randu64"}, {"native", "6090466678391964828"}, {"calls", counts(0, 0, 2)}},
      JsonObject{{"op", "randu32"}, {"native", "445970691"}, {"calls", counts(0, 0, 1)}},
      JsonObject{{"op", "addEntropy"}, {"seed", "27182818"}, {"calls", counts(0, 1, 0)}},
      JsonObject{{"op", "randu32"}, {"native", "2992900064"}, {"calls", counts(0, 0, 1)}},
      JsonObject{{"op", "randu64"}, {"native", "15329329036541151364"}, {"calls", counts(0, 0, 2)}},
      JsonObject{{"op", "randb"}, {"native", true}, {"calls", counts(0, 0, 1)}},
      JsonObject{{"op", "init"}, {"seed", "31415926"}, {"calls", counts(1, 0, 0)}}};
    Json reset = JsonObject{{"native", "2950892229"}, {"calls", counts(0, 0, 1)}};
    Json lua = JsonObject{{"b", "6090466678391964828"}, {"e", "-3117415037168400252"},
        {"f", true}, {"bInteger", true}, {"eInteger", true}};
    Json visual = JsonObject{{"rgb", JsonArray{197, 10, 227}}, {"width", 44}, {"height", 16},
        {"label", "RANDOM"}, {"imagePath", "/behaviorlab/random-result.png"}};
    if (proof.getArray("events") != expected || proof.get("resetDraw") != reset
        || proof.get("lua") != lua || proof.get("visual") != visual)
      throw StarException("BehaviorLab: random MWC values/order/receipts/Lua mismatch");
    auto image = m_root->assets()->image("/behaviorlab/random-result.png");
    if (image->size() != Vec2U(44, 16))
      throw StarException("BehaviorLab: random MWC result size mismatch");
    for (unsigned y = 0; y != 16; ++y)
      for (unsigned x = 0; x != 44; ++x)
        if (image->get(x, y) != Vec4B(197, 10, 227, 255))
          throw StarException("BehaviorLab: random MWC result pixels mismatch");
    m_behaviorRandomMwcProof = std::move(proof);
  }
  auto drawable = Drawable::makeImage(m_behaviorRandomMwcProof.get("visual").getString("imagePath"),
      2.0f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::prepareBehaviorAssetPathFrame() {
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright)
    return;
  auto world = m_universeClient->worldClient();
  if (!world || !world->inWorld())
    return;
  if (m_behaviorAssetPathProof.isNull()) {
    auto proof = assetPathBehaviorAssetProof();
    if (proof.isNull() || proof.getUInt("version") != 1)
      throw StarException("BehaviorLab: missing assetpath postLoad proof");
    auto rows = proof.get("assets");
    auto visual = proof.get("visual");
    String backend = "cpp";
    JsonArray namedCalls{0, 0}, aliasCalls{0, 0};
#ifdef STAR_USE_RUST_ASSET_PATH
    backend = "rust";
    namedCalls = JsonArray{1, 2};
    aliasCalls = JsonArray{1, 0};
#endif
    auto assets = m_root->assets();
    String frames = "{\"frameList\":{\"left\":[0,0,16,16],\"right\":[16,0,32,16]},\"aliases\":{\"alias\":\"right\"}}\n";
    auto atlasBytes = assets->bytes("/behaviorlab/assetpath-atlas.png");
    auto framesBytes = assets->bytes("/behaviorlab/assetpath-atlas.frames");
    if (rows.getString("backend") != backend
        || rows.getString("atlasHex") != hexEncode(*atlasBytes)
        || rows.getString("framesHex") != hexEncode(*framesBytes)
        || *framesBytes != frames.utf8Bytes())
      throw StarException("BehaviorLab: assetpath source/backend mismatch");
    // Decode the actual indexed PNG, not a replacement image. The literal
    // half-atlas oracle discriminates wrong frame selection/cropping.
    auto atlas = assets->image("/behaviorlab/assetpath-atlas.png");
    if (atlas->size() != Vec2U(32, 16))
      throw StarException("BehaviorLab: assetpath atlas must be 32x16");
    for (unsigned y = 0; y != 16; ++y)
      for (unsigned x = 0; x != 32; ++x)
        if (atlas->get(x, y) != (x < 16 ? Vec4B(255, 0, 0, 255) : Vec4B(64, 128, 192, 255)))
          throw StarException("BehaviorLab: assetpath atlas pixels mismatch");
    ByteArray expectedRgba;
    for (unsigned i = 0; i != 256; ++i) {
      expectedRgba.appendByte(32);
      expectedRgba.appendByte(static_cast<char>(128));
      expectedRgba.appendByte(96);
      expectedRgba.appendByte(static_cast<char>(255));
    }
    auto requireRow = [&](String const& key, String const& path, JsonArray const& calls) {
      auto row = rows.get(key);
      if (row.getString("path") != path || row.getArray("size") != JsonArray{16, 16}
          || row.getString("rgbaHex") != hexEncode(expectedRgba) || row.getArray("rustCalls") != calls)
        throw StarException("BehaviorLab: assetpath native image/receipt mismatch");
    };
    requireRow("named", "/behaviorlab/assetpath-atlas.png:right?multiply=80ff80", namedCalls);
    requireRow("alias", "/behaviorlab/assetpath-atlas.png:alias?multiply=80ff80", aliasCalls);
    String imagePath = "/behaviorlab/assetpath-result.png";
    if (visual.getString("imagePath") != imagePath || visual.getString("label") != "ASSETPATH"
        || visual.getArray("color") != JsonArray{32, 128, 96, 255}
        || visual.getArray("size") != JsonArray{16, 16} || !assets->assetExists(imagePath))
      throw StarException("BehaviorLab: assetpath visual metadata mismatch");
    auto image = assets->image(imagePath);
    if (image->size() != Vec2U(16, 16))
      throw StarException("BehaviorLab: assetpath result must be 16x16");
    for (unsigned y = 0; y != 16; ++y)
      for (unsigned x = 0; x != 16; ++x)
        if (image->get(x, y) != Vec4B(32, 128, 96, 255))
          throw StarException("BehaviorLab: assetpath processed result pixels mismatch");
    m_behaviorAssetPathProof = std::move(proof);
  }
  auto drawable = Drawable::makeImage("/behaviorlab/assetpath-result.png",
      2.0f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::prepareBehaviorJsonPatchFrame() {
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright)
    return;
  auto world = m_universeClient->worldClient();
  if (!world || !world->inWorld())
    return;
  if (m_behaviorJsonPatchProof.isNull()) {
    auto proof = jsonPatchBehaviorAssetProof();
    if (proof.isNull() || proof.getUInt("version") != 1)
      throw StarException("BehaviorLab: missing jsonpatch proof");
    auto assetsProof = proof.get("assets");
    String backend = "cpp";
#ifdef STAR_USE_RUST_JSON_PATCH
    backend = "rust";
#endif
    String const source = R"JP({"a/b":{"~é":[64,128]},"items":[{"id":"a","n":1},{"id":"b","n":2}],"visual":{"rgb":[],"scale":1,"label":"BEFORE"},"trash":7}
)JP";
    String const patch1 = R"JP([{"op":"test","path":"/a~1b/~0é/0","value":64},{"op":"copy","from":"/a~1b/~0é/0","path":"/visual/rgb/-"},{"op":"add","path":"/visual/rgb/-","value":128},{"op":"replace","path":"/visual/scale","value":4},{"op":"move","from":"/trash","path":"/moved"},{"op":"remove","path":"/moved"},{"op":"merge","path":"/visual","value":{"rgb":[64,128,192],"label":"PATCH","scale":null}},{"op":"test","path":"/items","search":{"id":"a"}},{"op":"add","path":"/items","search":{"id":"b"},"value":{"id":"x","n":9}},{"op":"replace","path":"/items","search":{"id":"x"},"value":{"id":"x","n":10}},{"op":"merge","path":"/items","search":{"id":"x"},"value":{"extra":true,"n":null}},{"op":"copy","from":"/items","path":"/selected","search":{"id":"x"}},{"op":"move","from":"/items","path":"/picked","search":{"id":"b"}},{"op":"remove","path":"/items","search":{"id":"a"}},{"op":"test","path":"/absent","inverse":true},[{"op":"add","path":"/visual/scale","value":99},{"op":"test","path":"/visual/scale","value":-1}],{"op":"add","path":"/after","value":true}]
)JP";
    String const patch2 = R"JP([{"op":"replace","path":"/visual/label","value":"BAD"},{"op":"test","path":"/visual/scale","value":-1}]
)JP";
    auto expected = Json::parse(R"JP({"a/b":{"~é":[64,128]},"items":[{"id":"x","n":10,"extra":true}],"visual":{"rgb":[64,128,192],"scale":4,"label":"PATCH"},"selected":{"id":"x","n":10,"extra":true},"picked":{"id":"b","n":2},"after":true})JP");
    if (assetsProof.getString("backend") != backend
        || assetsProof.getString("sourceHex") != hexEncode(source.utf8Bytes())
        || assetsProof.getArray("patchesHex") != JsonArray{hexEncode(patch1.utf8Bytes()), hexEncode(patch2.utf8Bytes())}
        || assetsProof.get("value") != expected)
      throw StarException("BehaviorLab: jsonpatch backend/source/full native value mismatch");
    // Assets invokes APPLY, not public PATCH. Internal FIND and handlers are counted.
    JsonPatchLabCounts predictions{};
    if (backend == "rust") {
      predictions[0] = {{0, 20, 7, 5, 2, 4, 3, 2, 2, 2}};
      predictions[1] = {{0, 18, 7, 3, 2, 4, 3, 2, 2, 2}};
      predictions[2] = {{0, 2, 0, 2, 0, 0, 0, 0, 0, 0}};
    }
    if (assetsProof.get("calls") != jsonPatchLabJson(predictions))
      throw StarException("BehaviorLab: jsonpatch semantic receipt mismatch");
    auto visual = proof.get("visual");
    auto observed = assetsProof.get("value").get("visual");
    String const imagePath = "/behaviorlab/jsonpatch-result.png";
    auto assets = m_root->assets();
    if (visual.getString("imagePath") != imagePath
        || visual.getArray("color") != JsonArray{64, 128, 192, 255}
        || visual.get("scale") != observed.get("scale")
        || visual.get("label") != observed.get("label") || !assets->assetExists(imagePath))
      throw StarException("BehaviorLab: jsonpatch visual metadata mismatch");
    auto image = assets->image(imagePath);
    if (image->size() != Vec2U(16, 16))
      throw StarException("BehaviorLab: jsonpatch image must be 16x16");
    for (unsigned y = 0; y != 16; ++y)
      for (unsigned x = 0; x != 16; ++x)
        if (image->get(x, y) != Vec4B(64, 128, 192, 255))
          throw StarException("BehaviorLab: jsonpatch pixels differ from native RGB");
    m_behaviorJsonPatchProof = std::move(proof);
  }
  auto observedScale = m_behaviorJsonPatchProof.get("visual").getFloat("scale");
  auto drawable = Drawable::makeImage("/behaviorlab/jsonpatch-result.png",
      observedScale * 0.5f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::prepareBehaviorJsonPathFrame() {
  auto world = m_universeClient->worldClient();
  if (!world || !world->inWorld())
    return;
  if (m_behaviorJsonPathProof.isNull()) {
    auto proof = jsonPathBehaviorAssetProof();
    if (proof.isNull() || proof.getUInt("version") != 1)
      throw StarException("BehaviorLab: missing jsonpath proof");
    auto assetProof = proof.get("assets");
    auto script = proof.get("script");
    auto visual = proof.get("visual");
    String backend = "cpp";
#ifdef STAR_USE_RUST_JSON_PATH
    backend = "rust";
#endif
    String source = "{\"a/b\":{\"~é\":[64,128]},\"visual\":{\"rgb\":[],\"scale\":4,\"label\":\"JSONPATH\"}}\n";
    String patch = "[{\"op\":\"copy\",\"from\":\"/a~1b/~0é/0\",\"path\":\"/visual/rgb/-\"},{\"op\":\"copy\",\"from\":\"/a~1b/~0é/1\",\"path\":\"/visual/rgb/-\"},{\"op\":\"add\",\"path\":\"/visual/rgb/-\",\"value\":192}]\n";
    if (assetProof.getString("backend") != backend
        || assetProof.getString("sourceHex") != hexEncode(source.utf8Bytes())
        || assetProof.getString("patchHex") != hexEncode(patch.utf8Bytes()))
      throw StarException("BehaviorLab: jsonpath backend/source mismatch");
    auto requireCalls = [&](Json const& row, uint64_t pointer, uint64_t query) {
      auto expected = backend == "rust" ? JsonArray{Json(pointer), Json(query)} : JsonArray{0, 0};
      if (row.getArray("rustCalls") != expected)
        throw StarException("BehaviorLab: jsonpath receipt prediction mismatch");
    };
    auto rgb = assetProof.get("rgb"), scale = assetProof.get("scale"), label = assetProof.get("label");
    if (rgb.getString("path") != "/behaviorlab/jsonpath-input.json:visual.rgb"
        || scale.getString("path") != "/behaviorlab/jsonpath-input.json:visual.scale"
        || label.getString("path") != "/behaviorlab/jsonpath-input.json:visual.label"
        || rgb.getArray("value") != JsonArray{64, 128, 192}
        || scale.getUInt("value") != 4 || label.getString("value") != "JSONPATH")
      throw StarException("BehaviorLab: jsonpath asset values mismatch");
    requireCalls(rgb, 21, 2);
    requireCalls(scale, 0, 2);
    requireCalls(label, 0, 2);
    auto query = script.get("query"), missing = script.get("missing"), malformed = script.get("malformed");
    if (query.getString("path") != "é[0].雪" || query.getUInt("value") != 9
        || missing.getString("path") != "missing" || missing.getUInt("value") != 77
        || malformed.getString("path") != "é[0x].雪" || malformed.getBool("accepted")
        || !malformed.getBool("nativeErrorMatched"))
      throw StarException("BehaviorLab: jsonpath script values mismatch");
    requireCalls(query, 0, 3);
    requireCalls(missing, 0, 1);
    requireCalls(malformed, 0, 2);
    String const imagePath = "/behaviorlab/jsonpath-result.png";
    auto assets = m_root->assets();
    if (visual.getString("imagePath") != imagePath
        || visual.getArray("color") != JsonArray{64, 128, 192, 255}
        || visual.getUInt("scale") != scale.getUInt("value")
        || visual.getString("label") != label.getString("value") || !assets->assetExists(imagePath))
      throw StarException("BehaviorLab: jsonpath visual metadata mismatch");
    auto image = assets->image(imagePath);
    if (image->size() != Vec2U(16, 16))
      throw StarException("BehaviorLab: jsonpath image must be 16x16");
    for (unsigned y = 0; y != 16; ++y)
      for (unsigned x = 0; x != 16; ++x)
        if (image->get(x, y) != Vec4B(64, 128, 192, 255))
          throw StarException("BehaviorLab: jsonpath pixels differ from queried RGB");
    m_behaviorJsonPathProof = std::move(proof);
  }
  auto observedScale = m_behaviorJsonPathProof.get("visual").getFloat("scale");
  auto drawable = Drawable::makeImage("/behaviorlab/jsonpath-result.png",
      observedScale * 0.5f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::prepareBehaviorShellFrame() {
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || m_renderData.isFullbright)
    return;
  if (m_behaviorShellProof.isNull()) {
    auto world = m_universeClient->worldClient();
    auto processor = m_mainInterface->commandProcessor();
    auto count = []() -> uint64_t {
#ifdef STAR_USE_RUST_SHELL
      return star_shell_call_count();
#else
      return 0;
#endif
    };
    String backend = "cpp";
    uint64_t expectedCalls = 0;
#ifdef STAR_USE_RUST_SHELL
    backend = "rust";
    expectedCalls = 1;
#endif
    // Login can overwrite the isolated player's initial admin flag. Scope this
    // local-only command capability to the fixture, never a server/admin packet.
    struct RestoreAdmin {
      PlayerPtr player;
      bool previous;
      ~RestoreAdmin() { player->setAdmin(previous); }
    } restoreAdmin{m_player, m_player->isAdmin()};
    m_player->setAdmin(true);
    if (!m_player->isAdmin())
      throw StarException("BehaviorLab: shell fixture is not admin");
    Vec2F const position(64, 48);
    float original = world->gravity(position);
    if (!std::isfinite(original) || original == 0.25f)
      throw StarException("BehaviorLab: shell fixture needs distinct finite original gravity");
    String const arguments[2] = {R"("\u0030.25")", R"("0.25")"};
    String const setters[2] = {"/setgravity " + arguments[0], "/setgravity " + arguments[1]};
    // Unknown processor commands may broadcast chat. Only these literal
    // builtins are permitted; never route this fixture through chat submission.
    auto invoke = [&](String const& command) {
      if (command != setters[0] && command != setters[1]
          && command != "/gravity" && command != "/resetgravity")
        throw StarException("BehaviorLab: shell command is not allowlisted");
      return processor->handleCommand(command, false);
    };
    JsonArray commands;
    for (unsigned i = 0; i != 2; ++i) {
      ShellParser parser;
      auto before = count();
      auto tokens = parser.tokenizeToStringList(arguments[i]);
      auto tokenCalls = count() - before;
      before = count();
      auto responses = invoke(setters[i]);
      auto commandCalls = count() - before;
      float gravity = world->gravity(position);
      uint32_t bits;
      std::memcpy(&bits, &gravity, sizeof(bits));
      if (tokens != StringList{"0.25"} || tokenCalls != expectedCalls
          || responses != StringList{"Gravity set to 0.25 (This is client-side!)"}
          || commandCalls != expectedCalls || bits != 0x3e800000u) {
        invoke("/resetgravity");
        throw StarException("BehaviorLab: shell command/token/gravity/receipt mismatch");
      }
      JsonArray tokenHex;
      for (auto const& token : tokens)
        tokenHex.append(hexEncode(token.utf8().data(), token.utf8Size()));
      commands.append(JsonObject{{"commandHex", hexEncode(setters[i].utf8().data(), setters[i].utf8Size())},
          {"tokenHex", tokenHex}, {"tokenCalls", tokenCalls}, {"responses", jsonFromStringList(responses)},
          {"gravity", gravity}, {"gravityBits", "3e800000"}, {"rustCalls", commandCalls}});
    }
    auto before = count();
    auto queryResponses = invoke("/gravity");
    auto queryCalls = count() - before;
    float queried = world->gravity(position);
    before = count();
    auto restoreResponses = invoke("/resetgravity");
    auto restoreCalls = count() - before;
    float restored = world->gravity(position);
    if (queryResponses != StringList{"0.25"} || queryCalls != 0 || queried != 0.25f
        || restoreResponses != StringList{"Gravity reset"} || restoreCalls != 0 || restored != original)
      throw StarException("BehaviorLab: shell gravity query/restoration mismatch");
    auto image = m_root->assets()->image("/behaviorlab/shell-result.png");
    if (image->size() != Vec2U(16, 16))
      throw StarException("BehaviorLab: shell image dimensions differ");
    for (unsigned y = 0; y != 16; ++y)
      for (unsigned x = 0; x != 16; ++x)
        if (image->get(x, y) != Vec4B(224, 160, 32, 255))
          throw StarException("BehaviorLab: shell image pixels differ");
    m_behaviorShellProof = JsonObject{{"version", 1}, {"backend", backend}, {"admin", true},
        {"queryPosition", JsonArray{64, 48}}, {"originalGravity", original}, {"commands", commands},
        {"query", JsonObject{{"responses", jsonFromStringList(queryResponses)}, {"gravity", queried}, {"rustCalls", queryCalls}}},
        {"restore", JsonObject{{"responses", jsonFromStringList(restoreResponses)}, {"gravity", restored}, {"rustCalls", restoreCalls}}},
        {"visual", JsonObject{{"gravity", queried}, {"imagePath", "/behaviorlab/shell-result.png"},
            {"label", "SHELL"}, {"color", JsonArray{224, 160, 32, 255}}}}};
  }
  auto gravity = m_behaviorShellProof.get("visual").getFloat("gravity");
  auto drawable = Drawable::makeImage("/behaviorlab/shell-result.png", gravity * 8.0f / TilePixels, true, Vec2F(64, 48));
  drawable.fullbright = true;
  m_renderData.foregroundOverlays.append(std::move(drawable));
}

void ClientApplication::renderBehaviorStringViewFrame() {
  m_behaviorStringViewProof = Json();
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || !m_behaviorLightingCompleted || m_renderData.isFullbright)
    return;
  auto world = m_universeClient->worldClient();
  if (!world || !world->inWorld())
    return;

  String const pathString = "/behaviorlab/string-view.png?setcolor=123456";
  String const input = "^shadow=#123456,noshadow;VIEW";
  auto assets = m_root->assets();
  m_guiContext->setTextStyle(TextStyle(), 1.0f);
  m_guiContext->setDefaultFont();
  m_guiContext->setFontSize(16, 1.0f);
  m_guiContext->setFontColor(Vec4B(255, 255, 255, 255));
  m_guiContext->setFontMode(FontMode::Normal);
  m_guiContext->setFontProcessingDirectives("");
  StringViewLab::Recorder recorder;
  TextProcessLab::Recorder font;
  ImageConstPtr image;
  {
    // One logical fixture call, two scopes. Caller identity comes from app init,
    // not TLS. Short directives parse eagerly even when the image is cached.
    StringViewLab::Arm arm(recorder, std::this_thread::get_id() == m_behaviorMainThread);
    AssetPath path = [&]() {
      StringViewLab::Scope scope(0);
      AssetPath parsed(pathString);
      scope.complete();
      return parsed;
    }();
    image = assets->image(path);
    {
      TextProcessLab::Scope fontScope(font);
      m_guiContext->renderText(input,
          TextPositioning(Vec2F(m_guiContext->windowSize()) * 0.5f + Vec2F(-35, 70),
              HorizontalAnchor::LeftAnchor, VerticalAnchor::TopAnchor));
      font.completed = true;
    }
  }
  m_guiContext->clearTextStyle();

  // Counts are frozen by complete(), and Arm has ended before observation or
  // serialization. This metadata cannot earn consumer credit during capture.
  auto hex = [](unsigned char const* bytes, size_t size) {
    std::string result;
    static char const digits[] = "0123456789abcdef";
    for (size_t i = 0; i < size; ++i) {
      result += digits[bytes[i] >> 4];
      result += digits[bytes[i] & 15];
    }
    return String(std::move(result));
  };
  JsonArray events;
  for (size_t i = 0; i < font.eventCount; ++i) {
    auto const& event = font.events[i];
    events.append(JsonObject{{"kind", event.kind == 0 ? "text" : "command"},
        {"hex", hex(event.bytes.data(), event.size)}});
  }
  JsonArray glyphs;
  for (size_t i = 0; i < font.glyphCount; ++i) {
    auto const& glyph = font.glyphs[i];
    glyphs.append(JsonObject{{"codepoint", glyph.codepoint},
        {"rgba", JsonArray{glyph.rgba[0], glyph.rgba[1], glyph.rgba[2], glyph.rgba[3]}}});
  }
  m_behaviorStringViewProof = recorder.toJson()
      .set("assetPath", pathString)
      .set("imageRead", "normal-assets-cache-permitted")
      .set("image", StringViewLab::imageJson(*image))
      .set("font", JsonObject{{"input", input}, {"completed", font.completed}, {"valid", font.valid},
          {"events", std::move(events)}, {"glyphs", std::move(glyphs)}});
}

void ClientApplication::renderBehaviorTextScanFrame() {
  m_behaviorTextScanProof = Json();
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame() || !m_behaviorLightingCompleted || m_renderData.isFullbright)
    return;
  auto world = m_universeClient->worldClient();
  if (!world || !world->inWorld())
    return;

  // Only this normal GUI draw is observed. Measurement, wrapping, and other UI
  // must not manufacture parser receipts or glyph/color evidence.
  m_guiContext->setTextStyle(TextStyle(), 1.0f);
  m_guiContext->setDefaultFont();
  auto counts = []() {
    std::array<uint64_t, 3> result{};
#ifdef STAR_USE_RUST_TEXT_SCAN
    for (uint32_t i = 0; i < result.size(); ++i)
      result[i] = star_text_scan_call_count(i);
#endif
    return result;
  };
  String const input = "^red;TEXT^reset;";
  TextProcessLab::Recorder recorder;
  auto before = counts();
  {
    TextProcessLab::Scope scope(recorder);
    m_guiContext->renderText(input,
        TextPositioning(Vec2F(m_guiContext->windowSize()) * 0.5f + Vec2F(-35, 70),
            HorizontalAnchor::LeftAnchor, VerticalAnchor::TopAnchor));
    recorder.completed = true;
  }
  auto after = counts();
  m_guiContext->clearTextStyle();

  auto hex = [](unsigned char const* bytes, size_t size) {
    std::string result;
    static char const digits[] = "0123456789abcdef";
    for (size_t i = 0; i < size; ++i) {
      result += digits[bytes[i] >> 4];
      result += digits[bytes[i] & 15];
    }
    return String(std::move(result));
  };
  JsonArray events;
  for (size_t i = 0; i < recorder.eventCount; ++i) {
    auto const& event = recorder.events[i];
    events.append(JsonObject{{"kind", event.kind == 0 ? "text" : "command"},
        {"hex", hex(event.bytes.data(), event.size)}});
  }
  JsonArray glyphs;
  for (size_t i = 0; i < recorder.glyphCount; ++i) {
    auto const& glyph = recorder.glyphs[i];
    glyphs.append(JsonObject{{"codepoint", glyph.codepoint},
        {"rgba", JsonArray{glyph.rgba[0], glyph.rgba[1], glyph.rgba[2], glyph.rgba[3]}}});
  }
  JsonArray calls;
  for (size_t i = 0; i < before.size(); ++i)
    calls.append(after[i] - before[i]);
  String backend = "cpp";
  JsonArray expectedCalls{0, 0, 0};
#ifdef STAR_USE_RUST_TEXT_SCAN
  backend = "rust";
  expectedCalls = JsonArray{1, 1, 2};
#endif
  JsonArray const expectedEvents{
      JsonObject{{"kind", "command"}, {"hex", "726564"}},
      JsonObject{{"kind", "text"}, {"hex", "54455854"}},
      JsonObject{{"kind", "command"}, {"hex", "7265736574"}}};
  bool valid = recorder.valid && recorder.completed && events == expectedEvents && calls == expectedCalls
      && recorder.glyphCount == 4;
  std::array<uint32_t, 4> const expectedCodepoints{{84, 69, 88, 84}};
  for (size_t i = 0; i < recorder.glyphCount; ++i)
    valid = valid && i < expectedCodepoints.size() && recorder.glyphs[i].codepoint == expectedCodepoints[i]
        && recorder.glyphs[i].rgba == Vec4B(255, 73, 66, 255);
  if (!valid)
    throw StarException("BehaviorLab: text native callback/glyph/color/receipt mismatch");
  m_behaviorTextScanProof = JsonObject{{"version", 1}, {"backend", backend},
      {"inputHex", hex(reinterpret_cast<unsigned char const*>(input.utf8Ptr()), input.utf8Size())},
      {"calls", std::move(calls)},
      {"events", std::move(events)}, {"glyphs", std::move(glyphs)}, {"completed", recorder.completed}};
}

void ClientApplication::renderBehaviorScenario() {
  if (!m_behaviorReady || BehaviorLab::hasPendingFrame())
    return;
  // A deadline can cross BETWEEN overlay preparation and framebuffer queuing.
  // A second clock read must not authorize capturing the previous phase's proof.
  if (BehaviorLab::staticVectorScene() && !BehaviorLab::staticVectorFramePrepared(m_behaviorStage))
    return;
  if (BehaviorLab::idMapScene() && !BehaviorLab::idMapFramePrepared(m_behaviorStage))
    return;
  if (BehaviorLab::weightedPoolScene() && !BehaviorLab::weightedPoolFramePrepared(m_behaviorStage))
    return;
  if (BehaviorLab::ttlScene() && !BehaviorLab::ttlFramePrepared(m_behaviorStage))
    return;
  auto world = m_universeClient->worldClient();
  if (!world || !world->inWorld() || !m_behaviorLightingCompleted || m_renderData.isFullbright)
    return;
  auto lamp = as<Object>(world->entity(m_behaviorLightId));
  if (!lamp || lamp->lightSources().empty())
    return;
  if (BehaviorLab::staticVectorScene() && lamp->position() != Vec2F(116, 33))
    throw StarException("BehaviorLab: StaticVector lamp replicated at unexpected position");
  auto light = lamp->lightSources().first();
  bool playerOutsideView = !m_worldPainter->camera().worldTileRect().padded(4).contains(Vec2I::floor(m_player->position()));
  if (!playerOutsideView)
    throw StarException("BehaviorLab: drawable viewport unexpectedly includes animated player");
  if (m_behaviorRaycastRoom && m_behaviorRaycastState.isNull())
    return;
  m_behaviorCapture = m_behaviorRaycastRoom
      ? StringList{"ray-clear", "ray-blocked", "ray-restored"}.at(m_behaviorStage)
      : StringList{"lit-room", "occluder-added", "occluder-restored"}.at(m_behaviorStage);
  uint64_t calls = 0;
  String backend = "cpp";
#ifdef STAR_USE_RUST_LIGHTING
  backend = "rust";
  calls = star_lighting_call_count();
#endif
  // Preserve the exact CPU upload bits for diagnosing shader-visible rounding.
  // These diagnostics never mask pixels or weaken semantic state comparisons.
  JsonArray lightmapBits;
  auto& lightmap = m_renderData.lightMap;
  for (size_t i = 0; i < (size_t)lightmap.width() * lightmap.height() * 3; ++i) {
    uint32_t bits;
    std::memcpy(&bits, lightmap.data() + i, sizeof(bits));
    lightmapBits.append(bits);
  }
  Json lightmapDiagnostic = JsonObject{{"size", jsonFromVec2U(lightmap.size())},
      {"minPosition", jsonFromVec2I(m_renderData.lightMinPosition)},
      {"layout", "row-major-rgb-f32-bits"}, {"bits", std::move(lightmapBits)}};
  Json metadata = JsonObject{
      {"lightingDiagnostics", std::move(lightmapDiagnostic)},
      {"scenario", BehaviorLab::idMapScene() ? "id-map-room" : BehaviorLab::weightedPoolScene() ? "weighted-pool-room" : BehaviorLab::ttlScene() ? "ttl-room" : m_behaviorLruRoom ? "lru-room" : m_behaviorPathEmbedRoom ? "path-embed-room" : m_behaviorStringViewRoom ? "stringview-room" : m_behaviorBufferRoom ? "buffer-room" : m_behaviorDataStreamRoom ? "datastream-room" : m_behaviorHostAddressRoom ? "host-address-room" : m_behaviorOptionParserRoom ? "option-parser-room" : m_behaviorZstdRoom ? "zstd-room" : m_behaviorCompressionRoom ? "compression-room" : m_behaviorTextScanRoom ? "text-room" : m_behaviorJsonPatchRoom ? "jsonpatch-room" : m_behaviorRandomMwcRoom ? "random-room" : m_behaviorAssetPathRoom ? "assetpath-room" : m_behaviorJsonPathRoom ? "jsonpath-room" : m_behaviorShellRoom ? "shell-room" : m_behaviorUnicodeRoom ? "unicode-room" : m_behaviorBytesRoom ? "bytes-room" : m_behaviorVlqRoom ? "vlq-room" : m_behaviorSha256Room ? "sha256-room" : m_behaviorEncodingRoom ? "encoding-room" : m_behaviorRaycastRoom ? "raycast-room" : "lighting-room"}, {"stage", m_behaviorCapture}, {"stageIndex", m_behaviorStage},
      {"worldState", JsonObject{
          {"worldId", printWorldId(m_universeClient->clientContext()->playerWorldId())},
          {"worldSize", jsonFromVec2U(world->geometry().size())},
          {"cameraPosition", jsonFromVec2F(m_worldPainter->camera().centerWorldPosition())},
          {"cameraPixelRatio", m_worldPainter->camera().pixelRatio()},
          {"materialId", m_behaviorMaterial}, {"lightObject", m_behaviorLightObject},
          {"lightEntityReplicated", true}, {"lightPosition", jsonFromVec2F(light.position)},
          {"lightColor", jsonFromVec3F(light.color)},
          {"occluderPresent", m_behaviorStage == 1},
          {"observedOccluderMaterial", world->material(Vec2I(62, 48), TileLayer::Foreground)}
      }},
      {"inWorld", world->inWorld()},
      {"worldId", printWorldId(m_universeClient->clientContext()->playerWorldId())},
      {"worldSize", jsonFromVec2U(world->geometry().size())},
      {"playerPosition", jsonFromVec2F(m_player->position())},
      {"cameraPosition", jsonFromVec2F(m_worldPainter->camera().centerWorldPosition())},
      {"cameraPixelRatio", m_worldPainter->camera().pixelRatio()},
      {"playerOutsideView", playerOutsideView}, {"uiHidden", true},
      {"stabilization", JsonObject{{"sky", "barren-black"}, {"stars", false}, {"debris", false},
          {"spawning", false}, {"lightFlicker", false}, {"objectAnimation", false}}},
      {"lightingBackend", backend}, {"rustLightingCalls", calls},
      {"lightingCompleted", m_behaviorLightingCompleted}, {"fullbright", m_renderData.isFullbright},
      {"material", "smoothmetal"}, {"materialId", m_behaviorMaterial},
      {"lightObject", m_behaviorLightObject}, {"lightEntityId", m_behaviorLightId},
      {"lightPosition", jsonFromVec2F(light.position)}, {"lightColor", jsonFromVec3F(light.color)},
      {"lightType", LightTypeNames.getRight(light.type)},
      {"lightEntityReplicated", (bool)world->entity(m_behaviorLightId)},
      {"changedTileMin", JsonArray{62, 33}}, {"changedTileMax", JsonArray{m_behaviorRaycastRoom ? 70 : 62, 59}},
      {"occluderPresent", m_behaviorStage == 1},
      {"observedOccluderMaterial", world->material(Vec2I(62, 48), TileLayer::Foreground)},
      {"action", m_behaviorStage == 0 ? "room-populated" : m_behaviorStage == 1 ? "foreground-occluder-added" : "foreground-occluder-removed"},
      {"replicatedSettledUpdates", m_behaviorSettledFrames}, {"updateIndex", m_behaviorFrames},
      {"seed", BehaviorLab::configuration().getUInt("seed", 42)}
  };
#ifdef STAR_USE_RUST_UUID
  metadata = metadata.set("rustUuidCalls", JsonArray{sb_uuid_count(0), sb_uuid_count(1), sb_uuid_count(2)});
#endif
#ifdef STAR_USE_RUST_NET_FIELD
  JsonArray floatMain, floatAll, floatLeaves;
  for (uint32_t mode = 0; mode != SB_NET_FLOAT_COUNT; ++mode) {
    floatMain.append(sb_net_float_count(0, mode));
    floatAll.append(sb_net_float_count(1, mode));
  }
  for (uint32_t op = 0; op != SB_NET_FLOAT_OP_COUNT; ++op)
    floatLeaves.append(sb_net_float_count(2, op));
  metadata = metadata.set("rustNetFloat", JsonObject{
      {"main", floatMain}, {"allThreads", floatAll}, {"attemptedLeaves", floatLeaves}});
#endif
#ifdef STAR_USE_RUST_NET_FIELD
  uint64_t scalarMain[SB_NET_SCALAR_COUNT], scalarAll[SB_NET_SCALAR_COUNT];
  for (uint32_t mode = 0; mode != SB_NET_SCALAR_COUNT; ++mode) {
    scalarMain[mode] = sb_net_scalar_count(0, mode);
    scalarAll[mode] = sb_net_scalar_count(1, mode);
  }
  JsonArray scalarMainJson, scalarAllJson;
  for (uint32_t mode = 0; mode != SB_NET_SCALAR_COUNT; ++mode) {
    scalarMainJson.append(scalarMain[mode]);
    scalarAllJson.append(scalarAll[mode]);
  }
  metadata = metadata.set("rustNetScalar", JsonObject{
      {"main", scalarMainJson}, {"allThreads", scalarAllJson}});
#endif
#ifdef STAR_USE_RUST_NET_GROUP
  uint64_t syncMain[SB_NET_SYNC_COUNT], syncAll[SB_NET_SYNC_COUNT], syncLeaves[SB_NET_SYNC_OP_COUNT];
  for (uint32_t mode = 0; mode != SB_NET_SYNC_COUNT; ++mode) {
    syncMain[mode] = sb_net_sync_count(0, mode);
    syncAll[mode] = sb_net_sync_count(1, mode);
  }
  for (uint32_t op = 0; op != SB_NET_SYNC_OP_COUNT; ++op)
    syncLeaves[op] = sb_net_sync_count(2, op);
  JsonArray syncMainJson, syncAllJson, syncLeafJson;
  for (uint32_t mode = 0; mode != SB_NET_SYNC_COUNT; ++mode) {
    syncMainJson.append(syncMain[mode]);
    syncAllJson.append(syncAll[mode]);
  }
  for (uint32_t op = 0; op != SB_NET_SYNC_OP_COUNT; ++op)
    syncLeafJson.append(syncLeaves[op]);
  metadata = metadata.set("rustNetSync", JsonObject{
      {"main", syncMainJson}, {"allThreads", syncAllJson}, {"attemptedLeaves", syncLeafJson}});
#endif
#ifdef STAR_USE_RUST_NET_DYNAMIC
  uint64_t dynamicMain[SB_NET_DYNAMIC_COUNT], dynamicAll[SB_NET_DYNAMIC_COUNT], dynamicLeaves[SB_NET_DYNAMIC_OP_COUNT];
  for (uint32_t mode = 0; mode != SB_NET_DYNAMIC_COUNT; ++mode) {
    dynamicMain[mode] = sb_net_dynamic_count(0, mode);
    dynamicAll[mode] = sb_net_dynamic_count(1, mode);
  }
  for (uint32_t op = 0; op != SB_NET_DYNAMIC_OP_COUNT; ++op)
    dynamicLeaves[op] = sb_net_dynamic_count(2, op);
  JsonArray dynamicMainJson, dynamicAllJson, dynamicLeafJson;
  for (uint32_t mode = 0; mode != SB_NET_DYNAMIC_COUNT; ++mode) {
    dynamicMainJson.append(dynamicMain[mode]);
    dynamicAllJson.append(dynamicAll[mode]);
  }
  for (uint32_t op = 0; op != SB_NET_DYNAMIC_OP_COUNT; ++op)
    dynamicLeafJson.append(dynamicLeaves[op]);
  metadata = metadata.set("rustNetDynamic", JsonObject{
      {"main", dynamicMainJson}, {"allThreads", dynamicAllJson}, {"attemptedLeaves", dynamicLeafJson}});
#endif
#ifdef STAR_USE_RUST_NET_GROUP
  JsonArray rulesMain, rulesAll;
  for (uint32_t mode = 0; mode != SB_NET_RULES_COUNT; ++mode) {
    rulesMain.append(sb_net_rules_count(0, mode));
    rulesAll.append(sb_net_rules_count(1, mode));
  }
  metadata = metadata.set("rustNetRules", JsonObject{
      {"main", rulesMain}, {"allThreads", rulesAll}});
#endif
#ifdef STAR_USE_RUST_NET_GROUP
  JsonArray compatMain, compatAll;
  for (uint32_t mode = 0; mode != SB_NET_COMPAT_COUNT; ++mode) {
    compatMain.append(sb_net_compat_count(0, mode));
    compatAll.append(sb_net_compat_count(1, mode));
  }
  metadata = metadata.set("rustNetCompat", JsonObject{
      {"main", compatMain}, {"allThreads", compatAll}});
#endif
#ifdef STAR_USE_RUST_NET_GROUP
  JsonArray versionMain, versionAll;
  for (uint32_t mode = 0; mode != SB_NET_VERSION_COUNT; ++mode) {
    versionMain.append(sb_net_version_count(0, mode));
    versionAll.append(sb_net_version_count(1, mode));
  }
  metadata = metadata.set("rustNetVersion", JsonObject{
      {"main", versionMain}, {"allThreads", versionAll}});
#endif
#ifdef STAR_USE_RUST_NET_GROUP
  JsonArray overrideMain, overrideAll, overrideLeaves;
  for (uint32_t mode = 0; mode != SB_NET_OVERRIDE_COUNT; ++mode) {
    overrideMain.append(sb_net_override_count(0, mode));
    overrideAll.append(sb_net_override_count(1, mode));
  }
  for (uint32_t op = 0; op != SB_NET_OVERRIDE_OP_COUNT; ++op)
    overrideLeaves.append(sb_net_override_count(2, op));
  metadata = metadata.set("rustNetOverride", JsonObject{
      {"main", overrideMain}, {"allThreads", overrideAll}, {"attemptedLeaves", overrideLeaves}});
#endif
#ifdef STAR_USE_RUST_NET_GROUP
  JsonArray netMapMain, netMapAll, netMapLeaves;
  for (uint32_t mode = 0; mode != SB_NET_MAP_COUNT; ++mode) {
    netMapMain.append(sb_net_map_count(0, mode));
    netMapAll.append(sb_net_map_count(1, mode));
  }
  for (uint32_t op = 0; op != SB_NET_MAP_OP_COUNT; ++op)
    netMapLeaves.append(sb_net_map_count(2, op));
  metadata = metadata.set("rustNetMap", JsonObject{
      {"main", netMapMain}, {"allThreads", netMapAll}, {"attemptedLeaves", netMapLeaves}});
#endif
#ifdef STAR_USE_RUST_NET_GROUP
  JsonArray topMain, topAll, topLeaves;
  for (uint32_t mode = 0; mode != SB_NET_TOP_COUNT; ++mode) {
    topMain.append(sb_net_top_count(0, mode));
    topAll.append(sb_net_top_count(1, mode));
  }
  for (uint32_t op = 0; op != SB_NET_TOP_OP_COUNT; ++op)
    topLeaves.append(sb_net_top_count(2, op));
  metadata = metadata.set("rustNetTop", JsonObject{
      {"main", topMain}, {"allThreads", topAll}, {"attemptedLeaves", topLeaves}});
#endif
#ifdef STAR_USE_RUST_NET_GROUP
  uint64_t groupMain[SB_NET_GROUP_COUNT], groupAll[SB_NET_GROUP_COUNT], groupLeaves[SB_NET_GROUP_OP_COUNT];
  for (uint32_t mode = 0; mode != SB_NET_GROUP_COUNT; ++mode) {
    groupMain[mode] = sb_net_group_count(0, mode);
    groupAll[mode] = sb_net_group_count(1, mode);
  }
  for (uint32_t op = 0; op != SB_NET_GROUP_OP_COUNT; ++op)
    groupLeaves[op] = sb_net_group_count(2, op);
  JsonArray groupMainJson, groupAllJson, groupLeafJson;
  for (uint32_t mode = 0; mode != SB_NET_GROUP_COUNT; ++mode) {
    groupMainJson.append(groupMain[mode]);
    groupAllJson.append(groupAll[mode]);
  }
  for (uint32_t op = 0; op != SB_NET_GROUP_OP_COUNT; ++op)
    groupLeafJson.append(groupLeaves[op]);
  metadata = metadata.set("rustNetGroup", JsonObject{
      {"main", groupMainJson}, {"allThreads", groupAllJson}, {"attemptedLeaves", groupLeafJson}});
#endif
#ifdef STAR_USE_RUST_NET_FIELD
  uint64_t fieldMain[SB_NET_FIELD_COUNT], fieldAll[SB_NET_FIELD_COUNT], fieldLeaves[SB_NET_FIELD_OP_COUNT];
  for (uint32_t mode = 0; mode != SB_NET_FIELD_COUNT; ++mode) {
    fieldMain[mode] = sb_net_field_count(0, mode);
    fieldAll[mode] = sb_net_field_count(1, mode);
  }
  for (uint32_t op = 0; op != SB_NET_FIELD_OP_COUNT; ++op)
    fieldLeaves[op] = sb_net_field_count(2, op);
  JsonArray fieldMainJson, fieldAllJson, fieldLeafJson;
  for (uint32_t mode = 0; mode != SB_NET_FIELD_COUNT; ++mode) {
    fieldMainJson.append(fieldMain[mode]);
    fieldAllJson.append(fieldAll[mode]);
  }
  for (uint32_t op = 0; op != SB_NET_FIELD_OP_COUNT; ++op)
    fieldLeafJson.append(fieldLeaves[op]);
  metadata = metadata.set("rustNetField", JsonObject{
      {"main", fieldMainJson}, {"allThreads", fieldAllJson}, {"attemptedLeaves", fieldLeafJson}});
#endif
#ifdef STAR_USE_RUST_NET_SIGNAL
  uint64_t signalMain[SB_NET_SIGNAL_COUNT], signalAll[SB_NET_SIGNAL_COUNT], signalLeaves[SB_NET_SIGNAL_OP_COUNT];
  for (uint32_t mode = 0; mode != SB_NET_SIGNAL_COUNT; ++mode) {
    signalMain[mode] = sb_net_signal_count(0, mode);
    signalAll[mode] = sb_net_signal_count(1, mode);
  }
  for (uint32_t op = 0; op != SB_NET_SIGNAL_OP_COUNT; ++op)
    signalLeaves[op] = sb_net_signal_count(2, op);
  JsonArray signalMainJson, signalAllJson, signalLeafJson;
  for (uint32_t mode = 0; mode != SB_NET_SIGNAL_COUNT; ++mode) {
    signalMainJson.append(signalMain[mode]);
    signalAllJson.append(signalAll[mode]);
  }
  for (uint32_t op = 0; op != SB_NET_SIGNAL_OP_COUNT; ++op)
    signalLeafJson.append(signalLeaves[op]);
  metadata = metadata.set("rustNetSignal", JsonObject{
      {"main", signalMainJson}, {"allThreads", signalAllJson}, {"attemptedLeaves", signalLeafJson}});
#endif
#ifdef STAR_USE_RUST_TIME
  uint64_t timeMain[SB_TIME_COUNT], timeAll[SB_TIME_COUNT], timeDomains[SB_TIME_COUNT];
  for (uint32_t op = 0; op != SB_TIME_COUNT; ++op) {
    timeMain[op] = sb_time_count(0, op);
    timeAll[op] = sb_time_count(1, op);
    timeDomains[op] = sb_time_count(2, op);
  }
  JsonArray timeMainJson, timeAllJson, timeDomainJson;
  for (uint32_t op = 0; op != SB_TIME_COUNT; ++op) {
    timeMainJson.append(timeMain[op]);
    timeAllJson.append(timeAll[op]);
    timeDomainJson.append(timeDomains[op]);
  }
  metadata = metadata.set("rustTime", JsonObject{
      {"main", timeMainJson}, {"allThreads", timeAllJson}, {"unsupportedAllThreads", timeDomainJson}});
#endif
#ifdef STAR_USE_RUST_WORKER_POOL
  uint64_t workerMain[SB_WORKER_POOL_COUNT], workerAll[SB_WORKER_POOL_COUNT];
  uint64_t workerLeaves[SB_WORKER_POOL_OP_COUNT];
  for (uint32_t mode = 0; mode != SB_WORKER_POOL_COUNT; ++mode) {
    workerMain[mode] = sb_worker_pool_count(0, mode);
    workerAll[mode] = sb_worker_pool_count(1, mode);
  }
  for (uint32_t op = 0; op != SB_WORKER_POOL_OP_COUNT; ++op)
    workerLeaves[op] = sb_worker_pool_count(2, op);
  JsonArray workerMainJson, workerAllJson, workerLeafJson;
  for (uint32_t mode = 0; mode != SB_WORKER_POOL_COUNT; ++mode) {
    workerMainJson.append(workerMain[mode]);
    workerAllJson.append(workerAll[mode]);
  }
  for (uint32_t op = 0; op != SB_WORKER_POOL_OP_COUNT; ++op)
    workerLeafJson.append(workerLeaves[op]);
  metadata = metadata.set("rustWorkerPool", JsonObject{
      {"main", workerMainJson}, {"allThreads", workerAllJson}, {"leafAllThreads", workerLeafJson}});
#endif
#ifdef STAR_USE_RUST_PERIODIC
  uint64_t periodicCalls[2][SB_PERIODIC_COUNT];
  for (uint32_t kind = 0; kind != 2; ++kind)
    for (uint32_t op = 0; op != SB_PERIODIC_COUNT; ++op)
      periodicCalls[kind][op] = sb_periodic_count(kind, op);
  JsonArray periodicMain, periodicAll;
  for (uint32_t op = 0; op != SB_PERIODIC_COUNT; ++op) {
    periodicMain.append(periodicCalls[0][op]);
    periodicAll.append(periodicCalls[1][op]);
  }
  metadata = metadata.set("rustPeriodic", JsonObject{{"main", periodicMain}, {"allThreads", periodicAll}});
#endif
#ifdef STAR_USE_RUST_MAP
  uint64_t mapMainLoops[SB_MAP_COUNT], mapAllLoops[SB_MAP_COUNT];
  uint64_t mapMainSelect[SB_MAP_SELECT_COUNT], mapAllSelect[SB_MAP_SELECT_COUNT];
  for (uint32_t mode = 0; mode != SB_MAP_COUNT; ++mode) {
    mapMainLoops[mode] = sb_map_count(mode);
    mapAllLoops[mode] = sb_map_global_count(0, mode);
  }
  for (uint32_t mode = 0; mode != SB_MAP_SELECT_COUNT; ++mode) {
    mapMainSelect[mode] = sb_map_select_count(mode);
    mapAllSelect[mode] = sb_map_global_count(1, mode);
  }
  JsonArray mapLoops, mapSelections, allMapLoops, allMapSelections;
  for (uint32_t mode = 0; mode != SB_MAP_COUNT; ++mode) {
    mapLoops.append(mapMainLoops[mode]);
    allMapLoops.append(mapAllLoops[mode]);
  }
  for (uint32_t mode = 0; mode != SB_MAP_SELECT_COUNT; ++mode) {
    mapSelections.append(mapMainSelect[mode]);
    allMapSelections.append(mapAllSelect[mode]);
  }
  metadata = metadata.set("rustMap", JsonObject{
      {"main", JsonObject{{"loops", mapLoops}, {"selections", mapSelections}}},
      {"allThreads", JsonObject{{"loops", allMapLoops}, {"selections", allMapSelections}}}});
#endif
#ifdef STAR_USE_RUST_FLAT_HASH_TABLE
  uint64_t flatHashCalls[2][SB_FLAT_HASH_COUNT];
  for (uint32_t kind = 0; kind != 2; ++kind)
    for (uint32_t mode = 0; mode != SB_FLAT_HASH_COUNT; ++mode)
      flatHashCalls[kind][mode] = sb_flat_hash_count(kind, mode);
  JsonArray flatHashMain, flatHashAll;
  for (uint32_t mode = 0; mode != SB_FLAT_HASH_COUNT; ++mode) {
    flatHashMain.append(flatHashCalls[0][mode]);
    flatHashAll.append(flatHashCalls[1][mode]);
  }
  metadata = metadata.set("rustFlatHashTable", JsonObject{{"main", flatHashMain}, {"allThreads", flatHashAll}});
#endif
#ifdef STAR_USE_RUST_SET
  JsonArray setLoops, setSelections, allSetLoops, allSetSelections;
  for (uint32_t mode = 0; mode != SB_SET_COUNT; ++mode) {
    setLoops.append(sb_set_count(mode));
    allSetLoops.append(sb_set_global_count(0, mode));
  }
  for (uint32_t mode = 0; mode != SB_SET_SELECT_COUNT; ++mode) {
    setSelections.append(sb_set_select_count(mode));
    allSetSelections.append(sb_set_global_count(1, mode));
  }
  metadata = metadata.set("rustSetMain", JsonObject{{"loops", setLoops}, {"selections", setSelections}});
  metadata = metadata.set("rustSetAllThreads", JsonObject{{"loops", allSetLoops}, {"selections", allSetSelections}});
#endif
#ifdef STAR_USE_RUST_ORDERED_SET
  JsonArray orderedSetCalls;
  for (uint32_t mode = 0; mode != SB_ORDERED_SET_COUNT; ++mode)
    orderedSetCalls.append(sb_ordered_set_count(mode));
  metadata = metadata.set("rustOrderedSetCalls", orderedSetCalls);
  JsonArray orderedSetSelections;
  for (uint32_t mode = 0; mode != SB_ORDERED_SET_SELECT_COUNT; ++mode)
    orderedSetSelections.append(sb_ordered_set_select_count(mode));
  metadata = metadata.set("rustOrderedSetSelections", orderedSetSelections);
#endif
  if (biMapUniqueIdProbe()) {
    Json proof;
    if (!m_universeServer->executeForClient(world->connection(), [&](WorldServer* server, PlayerPtr player) {
      proof = observeBiMapLamp(server, player, m_behaviorLightId, m_behaviorStage);
    })) throw StarException("BehaviorLab: lost BiMap fixture world before observation");
    metadata = metadata.set("biMapProof", proof);
  }
  if (m_behaviorStringViewRoom) {
    if (m_behaviorStringViewProof.isNull())
      throw StarException("BehaviorLab: StringView frame has no completed consumer proof");
    metadata = metadata.set("stringViewProof", m_behaviorStringViewProof);
  }
  if (m_behaviorTextScanRoom) {
    if (m_behaviorTextScanProof.isNull())
      throw StarException("BehaviorLab: text frame has no completed native render proof");
    metadata = metadata.set("textScanProof", m_behaviorTextScanProof);
  }
  if (m_behaviorRaycastRoom)
    metadata = metadata.set("raycastState", m_behaviorRaycastState);
  if (m_behaviorEncodingRoom) {
    if (m_behaviorEncodingProof.isNull())
      throw StarException("BehaviorLab: encoding frame has no asset/draw proof");
    metadata = metadata.set("encodingProof", m_behaviorEncodingProof);
  }
  if (m_behaviorSha256Room) {
    if (m_behaviorSha256Proof.isNull())
      throw StarException("BehaviorLab: SHA256 frame has no completed asset/database proof");
    metadata = metadata.set("sha256Proof", m_behaviorSha256Proof);
  }
  if (m_behaviorVlqRoom) {
    if (m_behaviorVlqProof.isNull())
      throw StarException("BehaviorLab: VLQ frame has no completed proof");
    metadata = metadata.set("vlqProof", m_behaviorVlqProof);
  }
  if (m_behaviorBytesRoom) {
    if (m_behaviorBytesProof.isNull())
      throw StarException("BehaviorLab: bytes frame has no completed proof");
    metadata = metadata.set("bytesProof", m_behaviorBytesProof);
  }
  if (m_behaviorShellRoom) {
    if (m_behaviorShellProof.isNull())
      throw StarException("BehaviorLab: shell proof missing");
    metadata = metadata.set("shellProof", m_behaviorShellProof);
  }
  if (m_behaviorUnicodeRoom) {
    if (m_behaviorUnicodeProof.isNull())
      throw StarException("BehaviorLab: unicode frame has no completed proof");
    metadata = metadata.set("unicodeProof", m_behaviorUnicodeProof);
  }
  if (m_behaviorJsonPatchRoom) {
    if (m_behaviorJsonPatchProof.isNull())
      throw StarException("BehaviorLab: jsonpatch frame has no completed proof");
    metadata = metadata.set("jsonPatchProof", m_behaviorJsonPatchProof);
  }
  if (m_behaviorJsonPathRoom) {
    if (m_behaviorJsonPathProof.isNull())
      throw StarException("BehaviorLab: jsonpath proof missing");
    metadata = metadata.set("jsonPathProof", m_behaviorJsonPathProof);
  }
  if (m_behaviorAssetPathRoom) {
    if (m_behaviorAssetPathProof.isNull())
      throw StarException("BehaviorLab: assetpath frame has no completed proof");
    metadata = metadata.set("assetPathProof", m_behaviorAssetPathProof);
  }
  if (m_behaviorOptionParserRoom) {
    if (m_behaviorOptionParserProof.isNull())
      throw StarException("BehaviorLab: option parser frame has no completed proof");
    metadata = metadata.set("optionParserProof", m_behaviorOptionParserProof);
  }
  if (m_behaviorBufferRoom) {
    if (m_behaviorBufferProof.isNull()) throw StarException("BehaviorLab: missing Buffer proof");
    metadata = metadata.set("bufferProof", m_behaviorBufferProof);
    if (m_behaviorFileProof.isNull()) throw StarException("BehaviorLab: missing File proof");
    metadata = metadata.set("fileProof", m_behaviorFileProof);
  }
  if (m_behaviorDataStreamRoom) {
    if (m_behaviorDataStreamProof.isNull())
      throw StarException("BehaviorLab: missing DataStream proof");
    metadata = metadata.set("dataStreamProof", m_behaviorDataStreamProof);
  }
  if (m_behaviorHostAddressRoom) {
    if (m_behaviorHostAddressProof.isNull())
      throw StarException("BehaviorLab: HostAddress frame has no completed proof");
    metadata = metadata.set("hostAddressProof", m_behaviorHostAddressProof);
  }
  if (m_behaviorPathEmbedRoom) {
    bool baseHeld = bool(m_behaviorPathEmbedBaseImage);
    bool cropHeld = bool(m_behaviorPathEmbedCropImage);
    bool baseSame = baseHeld && m_behaviorPathEmbedBaseImage.get() == m_behaviorPathEmbedBaseIdentity;
    bool cropSame = cropHeld && m_behaviorPathEmbedCropImage.get() == m_behaviorPathEmbedCropIdentity;
    bool distinct = baseHeld && cropHeld && m_behaviorPathEmbedBaseImage.get() != m_behaviorPathEmbedCropImage.get();
    if (m_behaviorPathEmbedProof.isNull() || !m_behaviorPathEmbedSubmitted || !baseSame || !cropSame || !distinct
        || m_behaviorPathEmbedBaseAcquisitions != 1 || m_behaviorPathEmbedCropAcquisitions != 1)
      throw StarException("BehaviorLab: PathEmbed missing submitted drawable/original image ownership");
    // After WorldPainter: inspect the same original objects, never reacquire or
    // register a proxy to hide eviction, copying, or stale fixture state.
    auto proof = m_behaviorPathEmbedProof
        .set("images", JsonObject{{"base", PathEmbedLab::imageJson(*m_behaviorPathEmbedBaseImage, false)},
            {"crop", PathEmbedLab::imageJson(*m_behaviorPathEmbedCropImage, true)}})
        .set("ownership", JsonObject{{"baseHeld", baseHeld}, {"cropHeld", cropHeld},
            {"baseIdentityUnchanged", baseSame}, {"cropIdentityUnchanged", cropSame}, {"distinctImages", distinct},
            {"baseAcquisitions", m_behaviorPathEmbedBaseAcquisitions}, {"cropAcquisitions", m_behaviorPathEmbedCropAcquisitions}});
    metadata = metadata.set("pathEmbedProof", proof);
  }
  if (m_behaviorZstdRoom) {
    if (m_behaviorZstdProof.isNull())
      throw StarException("BehaviorLab: Zstd frame has no completed proof");
    metadata = metadata.set("zstdProof", m_behaviorZstdProof);
  }
  if (m_behaviorCompressionRoom) {
    if (m_behaviorCompressionProof.isNull())
      throw StarException("BehaviorLab: compression frame has no completed proof");
    metadata = metadata.set("compressionProof", m_behaviorCompressionProof);
  }
  if (m_behaviorRandomMwcRoom) {
    if (m_behaviorRandomMwcProof.isNull())
      throw StarException("BehaviorLab: random MWC frame has no completed proof");
    metadata = metadata.set("randomMwcProof", m_behaviorRandomMwcProof);
  }
  if (m_behaviorLruRoom)
    metadata = metadata.set("lruProof", BehaviorLab::lruProof());
  if (BehaviorLab::ttlScene())
    metadata = metadata.set("ttlProof", BehaviorLab::ttlProof());
  if (BehaviorLab::weightedPoolScene())
    metadata = metadata.set("weightedPoolProof", BehaviorLab::weightedPoolProof());
  if (BehaviorLab::idMapScene())
    metadata = metadata.set("idMapProof", BehaviorLab::idMapProof());
  if (BehaviorLab::staticVectorScene()) {
    metadata = metadata.set("staticVectorProof", BehaviorLab::staticVectorProof());
    metadata = metadata.set("scenario", "static-vector-room");
    metadata = metadata.set("changedTileMin", JsonArray{2, 33}).set("changedTileMax", JsonArray{126, 59});
    metadata = metadata.set("changedColumns", JsonArray{126, 2});
    auto observed = world->material(Vec2I(126, 48), TileLayer::Foreground);
    metadata = metadata.set("observedOccluderMaterial", observed);
    metadata = metadata.set("worldState", metadata.get("worldState").set("observedOccluderMaterial", observed));
    BehaviorLab::staticVectorQueued(m_behaviorCapture);
  }
  BehaviorLab::queueFrame(m_behaviorCapture, std::move(metadata));
  m_behaviorReady = false;
  m_behaviorPhase = 4;
}

void ClientApplication::updateCamera(float dt) {
  if (!m_universeClient->worldClient())
    return;

  WorldCamera& camera = m_worldPainter->camera();
  camera.update(dt);
  if (BehaviorLab::enabled() && m_behaviorPhase >= 1) {
    camera.setPixelRatio(2.0f);
    m_worldPainter->setCameraPosition(m_universeClient->worldClient()->geometry(),
        BehaviorLab::staticVectorScene() ? Vec2F(0, 48) : Vec2F(64, 48));
    m_universeClient->worldClient()->setClientWindow(camera.worldTileRect());
    return;
  }

  if (m_mainInterface->fixedCamera())
    return;

  auto assets = m_root->assets();

  const float triggerRadius = 100.0f;
  const float deadzone = 0.1f;
  const float panFactor = 1.5f;
  float cameraSpeedFactor = 30.0f / m_root->configuration()->get("cameraSpeedFactor").toFloat();
  cameraSpeedFactor /= (dt * 60.f);

  auto playerCameraPosition = m_player->cameraPosition();

  if (isActionTaken(InterfaceAction::CameraShift)) {
    m_snapBackCameraOffset = false;
    m_cameraOffsetDownTime += dt;
    Vec2F aim = m_universeClient->worldClient()->geometry().diff(m_mainInterface->cursorWorldPosition(), playerCameraPosition);

    float magnitude = aim.magnitude() / (triggerRadius / camera.pixelRatio());
    if (magnitude > deadzone) {
      float cameraXOffset = aim.x() / magnitude;
      float cameraYOffset = aim.y() / magnitude;
      magnitude = (magnitude - deadzone) / (1.0 - deadzone);
      if (magnitude > 1)
        magnitude = 1;
      cameraXOffset *= magnitude * 0.5f * camera.pixelRatio() * panFactor;
      cameraYOffset *= magnitude * 0.5f * camera.pixelRatio() * panFactor;
      m_cameraXOffset = (m_cameraXOffset * (cameraSpeedFactor - 1.0) + cameraXOffset) / cameraSpeedFactor;
      m_cameraYOffset = (m_cameraYOffset * (cameraSpeedFactor - 1.0) + cameraYOffset) / cameraSpeedFactor;
    }
  } else {
    if (m_cameraOffsetDownTime > 0.0f && m_cameraOffsetDownTime < 0.333333f)
      m_snapBackCameraOffset = true;
    if (m_snapBackCameraOffset) {
      m_cameraXOffset = (m_cameraXOffset * (cameraSpeedFactor - 1.0)) / cameraSpeedFactor;
      m_cameraYOffset = (m_cameraYOffset * (cameraSpeedFactor - 1.0)) / cameraSpeedFactor;
    }
    m_cameraOffsetDownTime = 0.f;
  }
  Vec2F newCameraPosition;

  newCameraPosition.setX(playerCameraPosition.x());
  newCameraPosition.setY(playerCameraPosition.y());

  auto baseCamera = newCameraPosition;

  const float cameraSmoothRadius = assets->json("/interface.config:cameraSmoothRadius").toFloat();
  const float cameraSmoothFactor = assets->json("/interface.config:cameraSmoothFactor").toFloat();

  auto cameraSmoothDistance = m_universeClient->worldClient()->geometry().diff(m_cameraPositionSmoother, newCameraPosition).magnitude();
  if (cameraSmoothDistance > cameraSmoothRadius) {
    auto cameraDelta = m_universeClient->worldClient()->geometry().diff(m_cameraPositionSmoother, newCameraPosition);
    m_cameraPositionSmoother = newCameraPosition + cameraDelta.normalized() * cameraSmoothRadius;
    m_cameraSmoothDelta = {};
  }

  auto cameraDelta = m_universeClient->worldClient()->geometry().diff(m_cameraPositionSmoother, newCameraPosition);
  if (cameraDelta.magnitude() > assets->json("/interface.config:cameraSmoothDeadzone").toFloat())
    newCameraPosition = newCameraPosition + cameraDelta * (cameraSmoothFactor - 1.0) / cameraSmoothFactor;
  m_cameraPositionSmoother = newCameraPosition;

  newCameraPosition.setX(newCameraPosition.x() + m_cameraXOffset / camera.pixelRatio());
  newCameraPosition.setY(newCameraPosition.y() + m_cameraYOffset / camera.pixelRatio());

  auto smoothDelta = newCameraPosition - baseCamera;

  m_worldPainter->setCameraPosition(m_universeClient->worldClient()->geometry(), baseCamera + (smoothDelta + m_cameraSmoothDelta) * 0.5f);
  m_cameraSmoothDelta = smoothDelta;

  m_universeClient->worldClient()->setClientWindow(camera.worldTileRect());
}

}

STAR_MAIN_APPLICATION(Star::ClientApplication);
