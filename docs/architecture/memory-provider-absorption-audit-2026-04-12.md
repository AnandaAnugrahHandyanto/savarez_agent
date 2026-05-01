# Memory Provider 吸收盘查（2026-04-12）

## 结论
- **已完成一轮高价值吸收**：RetainDB / Mem0 / Hindsight 三条 provider 写入链路现在都具备了同类的 **normalized dedup + sensitive metadata stripping + fingerprint metadata** 能力。
- **RetainDB 进一步补齐**：不仅 `on_memory_write`，现在 `retaindb_remember` 工具路径也已对齐同样的去重/元数据标准，避免“工具写入有洞、镜像写入已修”的不一致。
- **验证已完成**：针对 RetainDB、Mem0、Hindsight、通用 provider 去重元数据测试已回归通过，当前相关测试 **144 passed**。

## 本轮已吸收内容

### 1. RetainDB
已补齐：
- provider 实例初始化时维护 `_last_sync_fingerprint` / `_last_write_fingerprint`
- `add_memory(...)` 支持传入 `metadata`
- `on_memory_write(...)` 写入前做：
  - metadata 清洗
  - fingerprint 生成
  - duplicate write skip
- `retaindb_remember` 工具路径已对齐：
  - 写入 `metadata`
  - 记录 `importance` / `requested_memory_type`
  - normalized duplicate skip

当前结果：RetainDB 不再只有 hook 路径安全，工具路径也对齐到统一 contract。

### 2. Mem0
已具备并已验证：
- `sync_turn(...)` 做 normalized turn fingerprint dedup
- `mem0_conclude` 做 metadata 清洗与 duplicate skip
- 显式 memory 写入带 `fingerprint/source/type`

当前判断：Mem0 这轮无需继续修主链路，已达到本轮目标。

### 3. Hindsight
已具备并已验证：
- `sync_turn(...)` 做 normalized turn dedup
- `hindsight_retain` 做 metadata 清洗、fingerprint 注入、duplicate skip
- 初始化会清空最近一次 fingerprint 状态

当前判断：Hindsight 本轮主链路也已补齐。

## 验收证据

### 测试命令
```bash
pytest tests/plugins/test_retaindb_plugin.py \
       tests/plugins/memory/test_provider_dedup_metadata.py \
       tests/plugins/memory/test_hindsight_provider.py \
       tests/plugins/memory/test_mem0_v2.py
```

### 结果
- `144 passed`

## 当前剩余缺口（按优先级）

### P0
- **无新增 P0**（memory provider 同类短板这轮已压平到可用状态）

### P1
1. **Honcho 主链路已补 session-level waterline / `last_saved_index` 等价能力**
   - 本轮已落地：
     - 远端已存在消息回填时初始化 `last_saved_index`
     - flush 时仅发送 waterline 之后的消息后缀
     - flush 成功后推进 waterline，失败时保留 waterline 以便 retry
   - 当前仍待继续提升：
     - 若未来 Honcho 原生支持服务端 session metadata，可再把 waterline 提升为远端持久字段，而不只停留在 Hermes 本地会话状态

2. **平台元数据剥离还未形成“全 provider 统一层”**
   - 现状：RetainDB / Mem0 / Hindsight / ByteRover / OpenViking / Honcho 已出现相同模式
   - 问题：实现仍分散在各 provider，缺少共享 helper / contract / developer 文档标准化

3. **memory provider 官方文档需要继续升级为正式规范**
   - `website/docs/user-guide/features/memory-providers.md`
   - `website/docs/developer-guide/memory-provider-plugin.md`
   - 当前已补 dedup / stripping / fingerprint contract，但还没抽象成统一 helper 指南 + provider checklist

4. **observer / peerPerspective / agentPeerMap 仍是团队级 P1，不属于本轮 provider 修复已解决范围**
   - 这部分仍需继续做 Hermes-native schema + context contract

## 建议下一步
1. 把 provider dedup / metadata stripping 抽成共享 helper，减少多处复制实现
2. 更新 memory provider user/developer docs，把这套 contract 写成正式规范
3. 继续转向 Honcho：补 `lastSavedIndex` / flush idempotency / reconnect retry 验证
4. 完成后再回刷 capability matrix 与总吸收盘查文档
