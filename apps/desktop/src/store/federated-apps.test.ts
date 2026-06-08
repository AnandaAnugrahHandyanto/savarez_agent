import { beforeEach, describe, expect, it } from 'vitest'

import {
  $federatedApps,
  clearFederatedApps,
  createWire,
  exportState,
  exportStateSafe,
  type FederatedAppsState,
  getAppOperators,
  getAvailableOperators,
  getOperatorWires,
  getRoutingPath,
  getStateVersion,
  getTopologyGraph,
  hasPath,
  importState,
  registerApp,
  registerOperator,
  removeWire,
  unregisterApp,
  unregisterOperator,
  updateAppState,
  updateOperatorState,
  updateWireState
} from './federated-apps'

describe('federated-apps store', () => {
  beforeEach(() => {
    clearFederatedApps()
  })

  describe('state management', () => {
    it('should start with empty state', () => {
      const state = $federatedApps.get()
      expect(state.apps).toEqual({})
      expect(state.operators).toEqual({})
      expect(state.wires).toEqual({})
      expect(state.version).toBe(0)
    })

    it('should increment version on each mutation', () => {
      expect(getStateVersion()).toBe(0)

      registerApp({
        id: 'app-1',
        name: 'Test App',
        version: '1.0.0',
        protocol: 'internal',
        capabilities: { canHostOperators: true, canProxy: false, maxOperators: 10 },
        state: 'available',
        metadata: {}
      })
      expect(getStateVersion()).toBe(1)

      registerOperator({
        id: 'op-1',
        appId: 'app-1',
        name: 'Test Operator',
        type: 'llm',
        capabilities: { canStream: true, canBatch: false, canDelegate: true, supportsPriority: true, maxConcurrent: 5 },
        state: 'available',
        currentLoad: 0,
        queueDepth: 0,
        metadata: {}
      })
      expect(getStateVersion()).toBe(2)
    })
  })

  describe('app registration', () => {
    it('should register a new app', () => {
      const app = registerApp({
        id: 'app-1',
        name: 'Test App',
        version: '1.0.0',
        protocol: 'internal',
        capabilities: { canHostOperators: true, canProxy: false, maxOperators: 10 },
        state: 'available',
        metadata: { region: 'us-west' }
      })

      expect(app.id).toBe('app-1')
      expect(app.name).toBe('Test App')
      expect(app.registeredAt).toBeGreaterThan(0)
      expect(app.lastHeartbeatAt).toBe(app.registeredAt)

      const state = $federatedApps.get()
      expect(state.apps['app-1']).toEqual(app)
    })

    it('should unregister an app and cleanup its operators/wires', () => {
      // Setup
      registerApp({
        id: 'app-1',
        name: 'App 1',
        version: '1.0.0',
        protocol: 'internal',
        capabilities: { canHostOperators: true, canProxy: false, maxOperators: 10 },
        state: 'available',
        metadata: {}
      })
      registerApp({
        id: 'app-2',
        name: 'App 2',
        version: '1.0.0',
        protocol: 'ws',
        capabilities: { canHostOperators: true, canProxy: true, maxOperators: 5 },
        state: 'available',
        metadata: {}
      })

      registerOperator({
        id: 'op-1',
        appId: 'app-1',
        name: 'Operator 1',
        type: 'llm',
        capabilities: { canStream: true, canBatch: false, canDelegate: true, supportsPriority: true, maxConcurrent: 5 },
        state: 'available',
        currentLoad: 0,
        queueDepth: 0,
        metadata: {}
      })
      registerOperator({
        id: 'op-2',
        appId: 'app-2',
        name: 'Operator 2',
        type: 'tool',
        capabilities: { canStream: false, canBatch: true, canDelegate: false, supportsPriority: false, maxConcurrent: 10 },
        state: 'available',
        currentLoad: 0,
        queueDepth: 0,
        metadata: {}
      })

      createWire('wire-1', { appId: 'app-1', operatorId: 'op-1' }, { appId: 'app-2', operatorId: 'op-2' }, 'internal')

      // Verify setup
      expect(Object.keys($federatedApps.get().apps)).toHaveLength(2)
      expect(Object.keys($federatedApps.get().operators)).toHaveLength(2)
      expect(Object.keys($federatedApps.get().wires)).toHaveLength(1)

      // Unregister app-1
      const result = unregisterApp('app-1')
      expect(result).toBe(true)

      const state = $federatedApps.get()
      expect(state.apps['app-1']).toBeUndefined()
      expect(state.operators['op-1']).toBeUndefined()
      expect(state.wires['wire-1']).toBeUndefined() // Wire connected to app-1 removed

      // app-2 and op-2 should remain
      expect(state.apps['app-2']).toBeDefined()
      expect(state.operators['op-2']).toBeDefined()
    })

    it('should return false when unregistering non-existent app', () => {
      const result = unregisterApp('non-existent')
      expect(result).toBe(false)
    })

    it('should update app state and heartbeat', () => {
      registerApp({
        id: 'app-1',
        name: 'Test App',
        version: '1.0.0',
        protocol: 'internal',
        capabilities: { canHostOperators: true, canProxy: false, maxOperators: 10 },
        state: 'available',
        metadata: {}
      })

      const beforeUpdate = $federatedApps.get().apps['app-1'].lastHeartbeatAt

      // Wait a tiny bit to ensure timestamp difference
      const result = updateAppState('app-1', 'busy', { region: 'us-east' })
      expect(result).toBe(true)

      const app = $federatedApps.get().apps['app-1']
      expect(app.state).toBe('busy')
      expect(app.lastHeartbeatAt).toBeGreaterThan(beforeUpdate)
      expect(app.metadata.region).toBe('us-east')
    })

    it('should return false when updating non-existent app', () => {
      const result = updateAppState('non-existent', 'busy')
      expect(result).toBe(false)
    })
  })

  describe('operator management', () => {
    beforeEach(() => {
      registerApp({
        id: 'app-1',
        name: 'Test App',
        version: '1.0.0',
        protocol: 'internal',
        capabilities: { canHostOperators: true, canProxy: false, maxOperators: 10 },
        state: 'available',
        metadata: {}
      })
    })

    it('should register an operator', () => {
      const op = registerOperator({
        id: 'op-1',
        appId: 'app-1',
        name: 'Test Operator',
        type: 'llm',
        capabilities: { canStream: true, canBatch: false, canDelegate: true, supportsPriority: true, maxConcurrent: 5 },
        state: 'available',
        currentLoad: 0,
        queueDepth: 0,
        metadata: { model: 'gpt-4' }
      })

      expect(op.id).toBe('op-1')
      expect(op.appId).toBe('app-1')
      expect(op.lastActivityAt).toBeGreaterThan(0)

      const state = $federatedApps.get()
      expect(state.operators['op-1']).toEqual(op)
    })

    it('should unregister an operator and its wires', () => {
      registerOperator({
        id: 'op-1',
        appId: 'app-1',
        name: 'Operator 1',
        type: 'llm',
        capabilities: { canStream: true, canBatch: false, canDelegate: true, supportsPriority: true, maxConcurrent: 5 },
        state: 'available',
        currentLoad: 0,
        queueDepth: 0,
        metadata: {}
      })

      registerApp({
        id: 'app-2',
        name: 'App 2',
        version: '1.0.0',
        protocol: 'ws',
        capabilities: { canHostOperators: true, canProxy: true, maxOperators: 5 },
        state: 'available',
        metadata: {}
      })

      registerOperator({
        id: 'op-2',
        appId: 'app-2',
        name: 'Operator 2',
        type: 'tool',
        capabilities: { canStream: false, canBatch: true, canDelegate: false, supportsPriority: false, maxConcurrent: 10 },
        state: 'available',
        currentLoad: 0,
        queueDepth: 0,
        metadata: {}
      })

      createWire('wire-1', { appId: 'app-1', operatorId: 'op-1' }, { appId: 'app-2', operatorId: 'op-2' }, 'internal')

      expect(Object.keys($federatedApps.get().operators)).toHaveLength(2)
      expect(Object.keys($federatedApps.get().wires)).toHaveLength(1)

      const result = unregisterOperator('op-1')
      expect(result).toBe(true)

      const state = $federatedApps.get()
      expect(state.operators['op-1']).toBeUndefined()
      expect(state.wires['wire-1']).toBeUndefined() // Wire connected to op-1 removed
      expect(state.operators['op-2']).toBeDefined() // op-2 remains
    })

    it('should return false when updating non-existent operator', () => {
      const result = updateOperatorState('non-existent', { state: 'busy' })
      expect(result).toBe(false)
    })

    it('should update operator state', () => {
      registerOperator({
        id: 'op-1',
        appId: 'app-1',
        name: 'Test Operator',
        type: 'llm',
        capabilities: { canStream: true, canBatch: false, canDelegate: true, supportsPriority: true, maxConcurrent: 5 },
        state: 'available',
        currentLoad: 0,
        queueDepth: 0,
        metadata: {}
      })

      const beforeUpdate = $federatedApps.get().operators['op-1'].lastActivityAt

      const result = updateOperatorState('op-1', { state: 'busy', currentLoad: 75, queueDepth: 3 })
      expect(result).toBe(true)

      const op = $federatedApps.get().operators['op-1']
      expect(op.state).toBe('busy')
      expect(op.currentLoad).toBe(75)
      expect(op.queueDepth).toBe(3)
      expect(op.lastActivityAt).toBeGreaterThan(beforeUpdate)
    })

    it('should set error state with message', () => {
      registerOperator({
        id: 'op-1',
        appId: 'app-1',
        name: 'Test Operator',
        type: 'llm',
        capabilities: { canStream: true, canBatch: false, canDelegate: true, supportsPriority: true, maxConcurrent: 5 },
        state: 'available',
        currentLoad: 0,
        queueDepth: 0,
        metadata: {}
      })

      const result = updateOperatorState('op-1', { state: 'error', errorMessage: 'Connection failed' })
      expect(result).toBe(true)

      const op = $federatedApps.get().operators['op-1']
      expect(op.state).toBe('error')
      expect(op.errorMessage).toBe('Connection failed')
    })
  })

  describe('wire management', () => {
    beforeEach(() => {
      registerApp({
        id: 'app-1',
        name: 'App 1',
        version: '1.0.0',
        protocol: 'internal',
        capabilities: { canHostOperators: true, canProxy: false, maxOperators: 10 },
        state: 'available',
        metadata: {}
      })
      registerApp({
        id: 'app-2',
        name: 'App 2',
        version: '1.0.0',
        protocol: 'ws',
        capabilities: { canHostOperators: true, canProxy: true, maxOperators: 5 },
        state: 'available',
        metadata: {}
      })

      registerOperator({
        id: 'op-1',
        appId: 'app-1',
        name: 'Operator 1',
        type: 'llm',
        capabilities: { canStream: true, canBatch: false, canDelegate: true, supportsPriority: true, maxConcurrent: 5 },
        state: 'available',
        currentLoad: 0,
        queueDepth: 0,
        metadata: {}
      })
      registerOperator({
        id: 'op-2',
        appId: 'app-2',
        name: 'Operator 2',
        type: 'tool',
        capabilities: { canStream: false, canBatch: true, canDelegate: false, supportsPriority: false, maxConcurrent: 10 },
        state: 'available',
        currentLoad: 0,
        queueDepth: 0,
        metadata: {}
      })
    })

    it('should create a wire between operators', () => {
      const wire = createWire('wire-1', { appId: 'app-1', operatorId: 'op-1' }, { appId: 'app-2', operatorId: 'op-2' }, 'internal')

      expect(wire.id).toBe('wire-1')
      expect(wire.sourceAppId).toBe('app-1')
      expect(wire.sourceOperatorId).toBe('op-1')
      expect(wire.targetAppId).toBe('app-2')
      expect(wire.targetOperatorId).toBe('op-2')
      expect(wire.protocol).toBe('internal')
      expect(wire.direction).toBe('bidirectional')
      expect(wire.state).toBe('connecting')

      const state = $federatedApps.get()
      expect(state.wires['wire-1']).toEqual(wire)
    })

    it('should create unidirectional wire', () => {
      const wire = createWire(
        'wire-1',
        { appId: 'app-1', operatorId: 'op-1' },
        { appId: 'app-2', operatorId: 'op-2' },
        'ws',
        'unidirectional'
      )

      expect(wire.direction).toBe('unidirectional')
    })

    it('should remove a wire', () => {
      createWire('wire-1', { appId: 'app-1', operatorId: 'op-1' }, { appId: 'app-2', operatorId: 'op-2' }, 'internal')

      const result = removeWire('wire-1')
      expect(result).toBe(true)

      const state = $federatedApps.get()
      expect(state.wires['wire-1']).toBeUndefined()
    })

    it('should return false when removing non-existent wire', () => {
      const result = removeWire('non-existent')
      expect(result).toBe(false)
    })

    it('should update wire state and metrics', () => {
      createWire('wire-1', { appId: 'app-1', operatorId: 'op-1' }, { appId: 'app-2', operatorId: 'op-2' }, 'internal')

      const beforeUpdate = $federatedApps.get().wires['wire-1'].lastActivityAt

      const result = updateWireState('wire-1', { state: 'available', latencyMs: 15, throughputBps: 1024000 })
      expect(result).toBe(true)

      const wire = $federatedApps.get().wires['wire-1']
      expect(wire.state).toBe('available')
      expect(wire.latencyMs).toBe(15)
      expect(wire.throughputBps).toBe(1024000)
      expect(wire.lastActivityAt).toBeGreaterThan(beforeUpdate)
    })
  })

  describe('queries', () => {
    beforeEach(() => {
      registerApp({
        id: 'app-1',
        name: 'App 1',
        version: '1.0.0',
        protocol: 'internal',
        capabilities: { canHostOperators: true, canProxy: false, maxOperators: 10 },
        state: 'available',
        metadata: {}
      })
      registerApp({
        id: 'app-2',
        name: 'App 2',
        version: '1.0.0',
        protocol: 'ws',
        capabilities: { canHostOperators: true, canProxy: true, maxOperators: 5 },
        state: 'available',
        metadata: {}
      })

      registerOperator({
        id: 'op-1',
        appId: 'app-1',
        name: 'Operator 1',
        type: 'llm',
        capabilities: { canStream: true, canBatch: false, canDelegate: true, supportsPriority: true, maxConcurrent: 5 },
        state: 'available',
        currentLoad: 50,
        queueDepth: 0,
        metadata: {}
      })
      registerOperator({
        id: 'op-2',
        appId: 'app-1',
        name: 'Operator 2',
        type: 'tool',
        capabilities: { canStream: false, canBatch: true, canDelegate: false, supportsPriority: false, maxConcurrent: 10 },
        state: 'busy',
        currentLoad: 95,
        queueDepth: 5,
        metadata: {}
      })
      registerOperator({
        id: 'op-3',
        appId: 'app-2',
        name: 'Operator 3',
        type: 'gateway',
        capabilities: { canStream: true, canBatch: true, canDelegate: true, supportsPriority: true, maxConcurrent: 20 },
        state: 'available',
        currentLoad: 10,
        queueDepth: 0,
        metadata: {}
      })
    })

    it('should get operators for a specific app', () => {
      const ops = getAppOperators('app-1')
      expect(ops).toHaveLength(2)
      expect(ops.map(o => o.id).sort()).toEqual(['op-1', 'op-2'])
    })

    it('should get wires for a specific operator', () => {
      createWire('wire-1', { appId: 'app-1', operatorId: 'op-1' }, { appId: 'app-2', operatorId: 'op-3' }, 'internal')
      createWire('wire-2', { appId: 'app-1', operatorId: 'op-2' }, { appId: 'app-2', operatorId: 'op-3' }, 'internal')

      const wires = getOperatorWires('op-1')
      expect(wires).toHaveLength(1)
      expect(wires[0].id).toBe('wire-1')
    })

    it('should get topology graph', () => {
      createWire('wire-1', { appId: 'app-1', operatorId: 'op-1' }, { appId: 'app-2', operatorId: 'op-3' }, 'internal')

      const graph = getTopologyGraph()

      expect(graph.nodes).toHaveLength(5) // 2 apps + 3 operators
      expect(graph.edges).toHaveLength(1)
      expect(graph.edges[0].id).toBe('wire-1')
    })

    it('should get available operators', () => {
      const available = getAvailableOperators()

      // op-1 is available with load 50
      // op-2 is busy with load 95
      // op-3 is available with load 10
      expect(available).toHaveLength(2)
      expect(available.map(o => o.id).sort()).toEqual(['op-1', 'op-3'])
    })
  })

  describe('routing', () => {
    beforeEach(() => {
      registerApp({
        id: 'app-1',
        name: 'App 1',
        version: '1.0.0',
        protocol: 'internal',
        capabilities: { canHostOperators: true, canProxy: false, maxOperators: 10 },
        state: 'available',
        metadata: {}
      })
      registerApp({
        id: 'app-2',
        name: 'App 2',
        version: '1.0.0',
        protocol: 'ws',
        capabilities: { canHostOperators: true, canProxy: true, maxOperators: 5 },
        state: 'available',
        metadata: {}
      })
      registerApp({
        id: 'app-3',
        name: 'App 3',
        version: '1.0.0',
        protocol: 'http',
        capabilities: { canHostOperators: true, canProxy: true, maxOperators: 5 },
        state: 'available',
        metadata: {}
      })

      registerOperator({
        id: 'op-1',
        appId: 'app-1',
        name: 'Operator 1',
        type: 'llm',
        capabilities: { canStream: true, canBatch: false, canDelegate: true, supportsPriority: true, maxConcurrent: 5 },
        state: 'available',
        currentLoad: 0,
        queueDepth: 0,
        metadata: {}
      })
      registerOperator({
        id: 'op-2',
        appId: 'app-2',
        name: 'Operator 2',
        type: 'tool',
        capabilities: { canStream: false, canBatch: true, canDelegate: false, supportsPriority: false, maxConcurrent: 10 },
        state: 'available',
        currentLoad: 0,
        queueDepth: 0,
        metadata: {}
      })
      registerOperator({
        id: 'op-3',
        appId: 'app-3',
        name: 'Operator 3',
        type: 'gateway',
        capabilities: { canStream: true, canBatch: true, canDelegate: true, supportsPriority: true, maxConcurrent: 20 },
        state: 'available',
        currentLoad: 0,
        queueDepth: 0,
        metadata: {}
      })
    })

    it('should return true for same operator', () => {
      expect(hasPath('op-1', 'op-1')).toBe(true)
    })

    it('should find path between connected operators', () => {
      // op-1 -> op-2 -> op-3
      createWire('wire-1', { appId: 'app-1', operatorId: 'op-1' }, { appId: 'app-2', operatorId: 'op-2' }, 'internal')
      createWire('wire-2', { appId: 'app-2', operatorId: 'op-2' }, { appId: 'app-3', operatorId: 'op-3' }, 'internal')

      expect(hasPath('op-1', 'op-3')).toBe(true)
      expect(hasPath('op-1', 'op-2')).toBe(true)
    })

    it('should return false for unreachable operators', () => {
      createWire('wire-1', { appId: 'app-1', operatorId: 'op-1' }, { appId: 'app-2', operatorId: 'op-2' }, 'internal')
      // op-3 is not connected

      expect(hasPath('op-1', 'op-3')).toBe(false)
    })

    it('should return false when wire is not available', () => {
      createWire('wire-1', { appId: 'app-1', operatorId: 'op-1' }, { appId: 'app-2', operatorId: 'op-2' }, 'internal')
      updateWireState('wire-1', { state: 'error' })

      expect(hasPath('op-1', 'op-2')).toBe(false)
    })

    it('should get routing path', () => {
      // op-1 -> op-2 -> op-3
      createWire('wire-1', { appId: 'app-1', operatorId: 'op-1' }, { appId: 'app-2', operatorId: 'op-2' }, 'internal')
      createWire('wire-2', { appId: 'app-2', operatorId: 'op-2' }, { appId: 'app-3', operatorId: 'op-3' }, 'internal')

      const path = getRoutingPath('op-1', 'op-3')
      expect(path).toEqual(['op-1', 'op-2', 'op-3'])
    })

    it('should return null for no route', () => {
      const path = getRoutingPath('op-1', 'op-2')
      expect(path).toBeNull()
    })
  })

  describe('state persistence', () => {
    it('should export state', () => {
      registerApp({
        id: 'app-1',
        name: 'Test App',
        version: '1.0.0',
        protocol: 'internal',
        capabilities: { canHostOperators: true, canProxy: false, maxOperators: 10 },
        state: 'available',
        metadata: { key: 'value' }
      })

      const exported = exportState()
      expect(exported.apps['app-1']).toBeDefined()
      expect(exported.apps['app-1'].name).toBe('Test App')
    })

    it('should import state and bump version', () => {
      const stateToImport: FederatedAppsState = {
        apps: {
          'app-imported': {
            id: 'app-imported',
            name: 'Imported App',
            version: '2.0.0',
            protocol: 'ws',
            capabilities: { canHostOperators: true, canProxy: true, maxOperators: 20 },
            state: 'available',
            registeredAt: 1234567890,
            lastHeartbeatAt: 1234567890,
            metadata: {}
          }
        },
        operators: {},
        wires: {},
        version: 5
      }

      importState(stateToImport)

      const state = $federatedApps.get()
      expect(state.apps['app-imported']).toBeDefined()
      expect(state.apps['app-imported'].name).toBe('Imported App')
      expect(state.version).toBe(6) // Version bumped
    })

    it('should round-trip export/import', () => {
      registerApp({
        id: 'app-1',
        name: 'Test App',
        version: '1.0.0',
        protocol: 'internal',
        capabilities: { canHostOperators: true, canProxy: false, maxOperators: 10 },
        state: 'available',
        metadata: {}
      })

      const exported = exportState()
      clearFederatedApps()
      importState(exported)

      const state = $federatedApps.get()
      expect(state.apps['app-1']).toBeDefined()
      expect(state.apps['app-1'].name).toBe('Test App')
    })

    it('should sanitize sensitive fields in exportStateSafe', () => {
      registerApp({
        id: 'app-1',
        name: 'Test App',
        version: '1.0.0',
        protocol: 'ws',
        url: 'wss://example.com?token=secret123&api_key=supersecret',
        capabilities: { canHostOperators: true, canProxy: false, maxOperators: 10 },
        state: 'available',
        metadata: {}
      })

      // exportState should include url (for round-tripping)
      const exported = exportState()
      expect(exported.apps['app-1'].url).toBe('wss://example.com?token=secret123&api_key=supersecret')

      // exportStateSafe should strip url (for audit logging)
      const safeExported = exportStateSafe()
      expect(safeExported.apps['app-1'].url).toBeUndefined()
      expect(safeExported.apps['app-1'].name).toBe('Test App') // other fields preserved
      expect(safeExported.apps['app-1'].protocol).toBe('ws')
    })
  })
})
