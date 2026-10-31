#include "StarJsonRpc.hpp"
#include "StarDataStreamDevices.hpp"
#include "StarLogging.hpp"
#ifdef STAR_USE_RUST_JSON_RPC
#include "StarJsonRpcHost.hpp"
#endif

namespace Star {

JsonRpcInterface::~JsonRpcInterface() {}

JsonRpc::JsonRpc() {
  m_requestId = 0;
}

void JsonRpc::registerHandler(String const& handler, JsonRpcRemoteFunction func) {
#ifdef STAR_USE_RUST_JSON_RPC
  JsonRpcDetail::run(SB_JSON_RPC_REGISTER,
      [&](uint32_t leaf, uint64_t, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_JSON_RPC_HAS_HANDLER: reply.a = m_handlers.contains(handler); break;
    case SB_JSON_RPC_THROW_DUPLICATE:
      throw JsonRpcException(strf("Handler by that name already exists '{}'", handler));
    case SB_JSON_RPC_ADD_HANDLER: m_handlers.add(handler, std::move(func)); break;
    default: JsonRpcDetail::invalidLeaf();
    }
  });
#else
  if (m_handlers.contains(handler))
    throw JsonRpcException(strf("Handler by that name already exists '{}'", handler));
  m_handlers.add(handler, std::move(func));
#endif
}

void JsonRpc::registerHandlers(JsonRpcHandlers const& handlers) {
#ifdef STAR_USE_RUST_JSON_RPC
  auto begin = handlers.begin(), end = handlers.end();
  JsonRpcDetail::run(SB_JSON_RPC_REGISTER_RANGE,
      [&](uint32_t leaf, uint64_t, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_JSON_RPC_MORE: if (begin != end) reply.a = 1; break;
    case SB_JSON_RPC_REGISTER_CURRENT: {
      auto const& pair = *begin;
      registerHandler(pair.first, pair.second);
      break;
    }
    case SB_JSON_RPC_ADVANCE: ++begin; break;
    default: JsonRpcDetail::invalidLeaf();
    }
  });
#else
  for (auto const& pair : handlers)
    registerHandler(pair.first, pair.second);
#endif
}

void JsonRpc::removeHandler(String const& handler) {
#ifdef STAR_USE_RUST_JSON_RPC
  JsonRpcDetail::run(SB_JSON_RPC_REMOVE,
      [&](uint32_t leaf, uint64_t, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_JSON_RPC_HAS_HANDLER: reply.a = m_handlers.contains(handler); break;
    case SB_JSON_RPC_REMOVE_HANDLER: m_handlers.remove(handler); break;
    case SB_JSON_RPC_THROW_MISSING:
      throw JsonRpcException(strf("No such handler by the name '{}'", handler));
    default: JsonRpcDetail::invalidLeaf();
    }
  });
#else
  if (!m_handlers.contains(handler))
    throw JsonRpcException(strf("No such handler by the name '{}'", handler));

  m_handlers.remove(handler);
#endif
}

void JsonRpc::clearHandlers() {
#ifdef STAR_USE_RUST_JSON_RPC
  JsonRpcDetail::run(SB_JSON_RPC_CLEAR, [&](uint32_t leaf, uint64_t, SbNetGroupReply&) {
    if (leaf != SB_JSON_RPC_CLEAR_HANDLERS) JsonRpcDetail::invalidLeaf();
    m_handlers.clear();
  });
#else
  m_handlers.clear();
#endif
}

RpcPromise<Json> JsonRpc::invokeRemote(String const& handler, Json const& arguments) {
#ifdef STAR_USE_RUST_JSON_RPC
  uint64_t id = JsonRpcDetail::run(SB_JSON_RPC_INVOKE,
      [&](uint32_t leaf, uint64_t value, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_JSON_RPC_GET_ID: reply.a = m_requestId; break;
    case SB_JSON_RPC_SET_ID: m_requestId = value; break;
    default: JsonRpcDetail::invalidLeaf();
    }
  }).a;
#else
  uint64_t id = m_requestId++;
#endif
  JsonObject request;
#ifdef STAR_USE_RUST_JSON_RPC
  JsonRpcDetail::run(SB_JSON_RPC_ENQUEUE,
      [&](uint32_t leaf, uint64_t value, SbNetGroupReply&) {
    if (leaf != SB_JSON_RPC_APPEND_REQUEST) JsonRpcDetail::invalidLeaf();
    m_pending.append(JsonObject{
        {"command", "request"},
        {"id", value},
        {"handler", handler},
        {"arguments", arguments}
      });
  }, id);
#else
  m_pending.append(JsonObject{
      {"command", "request"},
      {"id", id},
      {"handler", handler},
      {"arguments", arguments}
    });
#endif

  auto pair = RpcPromise<Json>::createPair();
#ifdef STAR_USE_RUST_JSON_RPC
  JsonRpcDetail::run(SB_JSON_RPC_TRACK, [&](uint32_t leaf, uint64_t, SbNetGroupReply&) {
    if (leaf != SB_JSON_RPC_ADD_PROMISE) JsonRpcDetail::invalidLeaf();
    m_pendingResponse.add(id, pair.second);
  });
#else
  m_pendingResponse.add(id, pair.second);
#endif

  return pair.first;
}

bool JsonRpc::sendPending() const {
#ifdef STAR_USE_RUST_JSON_RPC
  return JsonRpcDetail::run(SB_JSON_RPC_PENDING, [&](uint32_t leaf, uint64_t, SbNetGroupReply& reply) {
    if (leaf != SB_JSON_RPC_EMPTY_PENDING) JsonRpcDetail::invalidLeaf();
    reply.a = m_pending.empty();
  }).a != 0;
#else
  return !m_pending.empty();
#endif
}

ByteArray JsonRpc::send() {
#ifdef STAR_USE_RUST_JSON_RPC
  if (!JsonRpcDetail::run(SB_JSON_RPC_SEND, [&](uint32_t leaf, uint64_t, SbNetGroupReply& reply) {
        if (leaf != SB_JSON_RPC_EMPTY_PENDING) JsonRpcDetail::invalidLeaf();
        reply.a = m_pending.empty();
      }).a)
    return {};
#else
  if (m_pending.empty())
    return {};
#endif

  DataStreamBuffer buffer;
#ifdef STAR_USE_RUST_JSON_RPC
  JsonRpcDetail::run(SB_JSON_RPC_SEND_DATA, [&](uint32_t leaf, uint64_t, SbNetGroupReply&) {
    switch (leaf) {
    case SB_JSON_RPC_WRITE_PENDING: buffer.writeContainer(m_pending); break;
    case SB_JSON_RPC_CLEAR_PENDING: m_pending.clear(); break;
    default: JsonRpcDetail::invalidLeaf();
    }
  });
#else
  buffer.writeContainer(m_pending);
  m_pending.clear();
#endif

  return buffer.takeData();
}

void JsonRpc::receive(ByteArray const& inbuffer) {
#ifdef STAR_USE_RUST_JSON_RPC
  if (!JsonRpcDetail::run(SB_JSON_RPC_RECEIVE, [&](uint32_t leaf, uint64_t, SbNetGroupReply& reply) {
        if (leaf != SB_JSON_RPC_EMPTY_INPUT) JsonRpcDetail::invalidLeaf();
        reply.a = inbuffer.empty();
      }).a)
    return;
#else
  if (inbuffer.empty())
    return;
#endif

  DataStreamBuffer buffer(inbuffer);
  List<Json> inbound;
  buffer.readContainer(inbound);

#ifdef STAR_USE_RUST_JSON_RPC
  auto begin = inbound.begin(), end = inbound.end();
  JsonRpcDetail::run(SB_JSON_RPC_BATCH,
      [&](uint32_t leaf, uint64_t, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_JSON_RPC_MORE: if (begin != end) reply.a = 1; break;
    case SB_JSON_RPC_PROCESS_CURRENT: {
      auto request = *begin;
      receiveItem(request);
      break;
    }
    case SB_JSON_RPC_ADVANCE: ++begin; break;
    default: JsonRpcDetail::invalidLeaf();
    }
  });
#else
  for (auto request : inbound) {
    if (request.get("command") == "request") {
      try {
        auto handlerName = request.getString("handler");
        if (!m_handlers.contains(handlerName))
          throw JsonRpcException(strf("Unknown handler '{}'", handlerName));
        m_pending.append(JsonObject{
            {"command", "response"},
            {"id", request.get("id")},
            {"result", m_handlers[handlerName](request.get("arguments"))}
          });
      } catch (std::exception& e) {
        Logger::error("Exception while handling variant rpc request handler call. {}", outputException(e, false));
        JsonObject response;
        response["command"] = "fail";
        response["id"] = request.get("id");
        m_pending.append(JsonObject{
            {"command", "fail"},
            {"id", request.get("id")}
          });
      }

    } else if (request.get("command") == "response") {
      try {
        auto responseHandler = m_pendingResponse.take(request.getUInt("id"));
        responseHandler.fulfill(request.get("result"));
      } catch (std::exception& e) {
        Logger::error("Exception while handling variant rpc response handler call. {}", outputException(e, true));
      }

    } else if (request.get("command") == "fail") {
      try {
        auto responseHandler = m_pendingResponse.take(request.getUInt("id"));
        responseHandler.fulfill({});
      } catch (std::exception& e) {
        Logger::error("Exception while handling variant rpc failure handler call. {}", outputException(e, true));
      }
    }
  }
#endif
}

#ifdef STAR_USE_RUST_JSON_RPC
void JsonRpc::receiveItem(Json& request) {
  JsonRpcDetail::run(SB_JSON_RPC_ITEM,
      [&](uint32_t leaf, uint64_t, SbNetGroupReply& reply) {
    switch (leaf) {
    case SB_JSON_RPC_IS_REQUEST:
      if (request.get("command") == "request") reply.a = 1;
      break;
    case SB_JSON_RPC_IS_RESPONSE:
      if (request.get("command") == "response") reply.a = 1;
      break;
    case SB_JSON_RPC_IS_FAIL:
      if (request.get("command") == "fail") reply.a = 1;
      break;
    case SB_JSON_RPC_HANDLE_REQUEST: {
      try {
        auto handlerName = request.getString("handler");
        JsonRpcDetail::run(SB_JSON_RPC_REQUEST,
            [&](uint32_t operation, uint64_t, SbNetGroupReply& result) {
          switch (operation) {
          case SB_JSON_RPC_HAS_HANDLER: result.a = m_handlers.contains(handlerName); break;
          case SB_JSON_RPC_THROW_UNKNOWN:
            throw JsonRpcException(strf("Unknown handler '{}'", handlerName));
          case SB_JSON_RPC_APPEND_RESPONSE:
            m_pending.append(JsonObject{
                {"command", "response"},
                {"id", request.get("id")},
                {"result", m_handlers[handlerName](request.get("arguments"))}
              });
            break;
          default: JsonRpcDetail::invalidLeaf();
          }
        });
      } catch (std::exception& e) {
        Logger::error("Exception while handling variant rpc request handler call. {}", outputException(e, false));
        // Preserve even this unused object's allocation/failure/destruction prefix.
        JsonObject response;
        response["command"] = "fail";
        response["id"] = request.get("id");
        m_pending.append(JsonObject{
            {"command", "fail"},
            {"id", request.get("id")}
          });
      }
      break;
    }
    case SB_JSON_RPC_HANDLE_RESPONSE: {
      try {
        auto responseHandler = m_pendingResponse.take(request.getUInt("id"));
        responseHandler.fulfill(request.get("result"));
      } catch (std::exception& e) {
        Logger::error("Exception while handling variant rpc response handler call. {}", outputException(e, true));
      }
      break;
    }
    case SB_JSON_RPC_HANDLE_FAIL: {
      try {
        auto responseHandler = m_pendingResponse.take(request.getUInt("id"));
        responseHandler.fulfill({});
      } catch (std::exception& e) {
        Logger::error("Exception while handling variant rpc failure handler call. {}", outputException(e, true));
      }
      break;
    }
    default: JsonRpcDetail::invalidLeaf();
    }
  });
}
#endif
}
