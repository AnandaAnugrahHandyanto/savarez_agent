/**
 * Integration tests: sidebar fold + reorder interaction.
 *
 * Tests the four scenarios:
 * (a) Fold disabled → reordering main items independent of plugin items
 * (b) Fold enabled → single unified list, cross-boundary reorder
 * (c) Toggle fold on then off → restores separate lists with saved orders
 * (d) Fresh install → fold-off with default ordering
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import type { SidebarOrderItem, DashboardSettings } from "@/contexts/dashboard-settings-context";
import {
  loadSettings,
  saveSettings,
  DEFAULT_SETTINGS,
  applySidebarOrder,
  applySavedOrder,
} from "@/contexts/dashboard-settings-context";

// ── localStorage mock ────────────────────────────────────────────────
let store: Record<string, string> = {};

const STORAGE_KEY = "hermes-dashboard-settings";

beforeEach(() => {
  store = {};
  vi.stubGlobal("localStorage", {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
  });
});

// ── Helpers ──────────────────────────────────────────────────────────
type TestNavItem = { id: string; path: string; label: string };

const CORE_ITEMS: TestNavItem[] = [
  { id: "sessions", path: "/sessions", label: "Sessions" },
  { id: "analytics", path: "/analytics", label: "Analytics" },
  { id: "models", path: "/models", label: "Models" },
];

const PLUGIN_ITEMS: TestNavItem[] = [
  { id: "my-plugin", path: "/my-plugin", label: "My Plugin" },
  { id: "another-plugin", path: "/another-plugin", label: "Another Plugin" },
];

function sidebarOrderItem(ids: string[]): SidebarOrderItem[] {
  return ids.map((id) => ({ id }));
}

// ═══════════════════════════════════════════════════════════════════════
// Scenario (a): Fold disabled — separate order lists
// ═══════════════════════════════════════════════════════════════════════
describe("Scenario (a): fold disabled — independent reordering", () => {
  it("reordering core items does NOT affect plugin order", () => {
    // Start with default settings (fold off, empty orders)
    const settings = loadSettings();
    expect(settings.sidebarItemOrder.pluginsFoldedIntoSidebar).toBe(false);

    // Save a custom core order: models, sessions, analytics
    const newCoreOrder = sidebarOrderItem(["/models", "/sessions", "/analytics"]);
    const updated: DashboardSettings = {
      ...settings,
      sidebarItemOrder: {
        ...settings.sidebarItemOrder,
        coreOrder: newCoreOrder,
      },
    };
    saveSettings(updated);

    // Load back and verify
    const loaded = loadSettings();
    expect(loaded.sidebarItemOrder.coreOrder).toEqual(newCoreOrder);
    // Plugin order should remain untouched (empty default)
    expect(loaded.sidebarItemOrder.pluginOrder).toEqual([]);
  });

  it("reordering plugin items does NOT affect core order", () => {
    const settings = loadSettings();

    // Save a custom plugin order: another-plugin, my-plugin
    const newPluginOrder = sidebarOrderItem(["/another-plugin", "/my-plugin"]);
    const updated: DashboardSettings = {
      ...settings,
      sidebarItemOrder: {
        ...settings.sidebarItemOrder,
        pluginOrder: newPluginOrder,
      },
    };
    saveSettings(updated);

    const loaded = loadSettings();
    expect(loaded.sidebarItemOrder.pluginOrder).toEqual(newPluginOrder);
    // Core order should remain untouched
    expect(loaded.sidebarItemOrder.coreOrder).toEqual([]);
  });

  it("applySidebarOrder keeps core and plugin groups independently sorted", () => {
    // Core: sessions, analytics, models -> reorder via coreOrder
    const coreOrder = sidebarOrderItem(["/models", "/analytics", "/Sessions"]);
    const sorted = applySidebarOrder(CORE_ITEMS, coreOrder);

    expect(sorted.map((i) => i.path)).toEqual(["/models", "/analytics", "/sessions"]);

    // Plugin order should not affect core at all
    const pluginOrder = sidebarOrderItem(["/another-plugin", "/my-plugin"]);
    const sortedPlugins = applySidebarOrder(PLUGIN_ITEMS, pluginOrder);

    expect(sortedPlugins.map((i) => i.path)).toEqual(["/another-plugin", "/my-plugin"]);
  });

  it("persisted separate orders survive a reload (round-trip)", () => {
    // Set both orders, fold=false
    const coreOrder = sidebarOrderItem(["/models", "/sessions"]);
    const pluginOrder = sidebarOrderItem(["/another-plugin", "/my-plugin"]);

    const settings: DashboardSettings = {
      ...DEFAULT_SETTINGS,
      sidebarItemOrder: {
        pluginsFoldedIntoSidebar: false,
        coreOrder,
        pluginOrder,
        unifiedOrder: [],
      },
    };
    saveSettings(settings);

    const loaded = loadSettings();
    expect(loaded.sidebarItemOrder.coreOrder).toEqual(coreOrder);
    expect(loaded.sidebarItemOrder.pluginOrder).toEqual(pluginOrder);
    expect(loaded.sidebarItemOrder.pluginsFoldedIntoSidebar).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Scenario (b): Fold enabled — unified list
// ═══════════════════════════════════════════════════════════════════════
describe("Scenario (b): fold enabled — unified list", () => {
  it("applySidebarOrder with unifiedOrder interleaves core and plugin items", () => {
    const unifiedOrder = sidebarOrderItem([
      "/my-plugin",
      "/sessions",
      "/analytics",
      "/another-plugin",
      "/models",
    ]);

    const merged = [...CORE_ITEMS, ...PLUGIN_ITEMS];
    const sorted = applySidebarOrder(merged, unifiedOrder);

    expect(sorted.map((i) => i.path)).toEqual([
      "/my-plugin",
      "/sessions",
      "/analytics",
      "/another-plugin",
      "/models",
    ]);
  });

  it("persists unifiedOrder and fold=true to localStorage", () => {
    const unifiedOrder = sidebarOrderItem(["/models", "/my-plugin", "/sessions", "/analytics", "/another-plugin"]);

    const settings: DashboardSettings = {
      ...DEFAULT_SETTINGS,
      sidebarItemOrder: {
        pluginsFoldedIntoSidebar: true,
        coreOrder: [],
        pluginOrder: [],
        unifiedOrder,
      },
    };
    saveSettings(settings);

    const loaded = loadSettings();
    expect(loaded.sidebarItemOrder.pluginsFoldedIntoSidebar).toBe(true);
    expect(loaded.sidebarItemOrder.unifiedOrder).toEqual(unifiedOrder);
  });

  it("items not in the saved unifiedOrder are appended at the end", () => {
    const unifiedOrder = sidebarOrderItem(["/sessions", "/my-plugin"]);
    const merged = [...CORE_ITEMS, ...PLUGIN_ITEMS];
    const sorted = applySidebarOrder(merged, unifiedOrder);

    // sessions first, my-plugin second, then the rest in natural order
    const resultPaths = sorted.map((i) => i.path);
    expect(resultPaths[0]).toBe("/sessions");
    expect(resultPaths[1]).toBe("/my-plugin");
    // Remaining items not in order should follow
    const remaining = resultPaths.slice(2);
    expect(remaining).toContain("/analytics");
    expect(remaining).toContain("/models");
    expect(remaining).toContain("/another-plugin");
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Scenario (c): Toggle fold on then off — restores separate lists
// ═══════════════════════════════════════════════════════════════════════
describe("Scenario (c): toggle fold on then off — restores separate lists", () => {
  it("folding ON merges items, folding OFF restores the previously saved separate orders", () => {
    // 1. Start with known separate orders
    const coreOrder = sidebarOrderItem(["/models", "/sessions", "/analytics"]);
    const pluginOrder = sidebarOrderItem(["/another-plugin", "/my-plugin"]);

    const initial: DashboardSettings = {
      ...DEFAULT_SETTINGS,
      sidebarItemOrder: {
        pluginsFoldedIntoSidebar: false,
        coreOrder,
        pluginOrder,
        unifiedOrder: [],
      },
    };
    saveSettings(initial);

    // 2. Toggle fold ON — save a unified order
    const unifiedOrder = sidebarOrderItem([
      "/models",
      "/my-plugin",
      "/sessions",
      "/another-plugin",
      "/analytics",
    ]);
    const folded: DashboardSettings = {
      ...loadSettings(),
      sidebarItemOrder: {
        pluginsFoldedIntoSidebar: true,
        coreOrder,        // preserve old core order
        pluginOrder,      // preserve old plugin order
        unifiedOrder,
      },
    };
    saveSettings(folded);

    let loaded = loadSettings();
    expect(loaded.sidebarItemOrder.pluginsFoldedIntoSidebar).toBe(true);
    expect(loaded.sidebarItemOrder.unifiedOrder).toEqual(unifiedOrder);

    // 3. Toggle fold OFF — saved orders should still be there
    const unfolded: DashboardSettings = {
      ...loadSettings(),
      sidebarItemOrder: {
        ...loadSettings().sidebarItemOrder,
        pluginsFoldedIntoSidebar: false,
      },
    };
    saveSettings(unfolded);

    loaded = loadSettings();
    expect(loaded.sidebarItemOrder.pluginsFoldedIntoSidebar).toBe(false);
    // The separate orders should still be what we saved earlier
    expect(loaded.sidebarItemOrder.coreOrder).toEqual(coreOrder);
    expect(loaded.sidebarItemOrder.pluginOrder).toEqual(pluginOrder);
  });

  it("when folding on THEN off, the unified order is discarded and separate orders are used", () => {
    // Set separate orders
    const coreOrder = sidebarOrderItem(["/analytics", "/sessions", "/models"]);
    const pluginOrder = sidebarOrderItem(["/my-plugin", "/another-plugin"]);

    saveSettings({
      ...DEFAULT_SETTINGS,
      sidebarItemOrder: {
        pluginsFoldedIntoSidebar: false,
        coreOrder,
        pluginOrder,
        unifiedOrder: [],
      },
    });

    // Fold on with a specific unified order
    const unifiedOrder = sidebarOrderItem([
      "/another-plugin",
      "/analytics",
      "/my-plugin",
      "/sessions",
      "/models",
    ]);
    saveSettings({
      ...loadSettings(),
      sidebarItemOrder: {
        pluginsFoldedIntoSidebar: true,
        coreOrder,
        pluginOrder,
        unifiedOrder,
      },
    });

    // Fold off
    saveSettings({
      ...loadSettings(),
      sidebarItemOrder: {
        ...loadSettings().sidebarItemOrder,
        pluginsFoldedIntoSidebar: false,
      },
    });

    // Now verify: separate orders control rendering
    const loaded = loadSettings();
    const displayCore = applySidebarOrder(CORE_ITEMS, loaded.sidebarItemOrder.coreOrder);
    const displayPlugin = applySidebarOrder(PLUGIN_ITEMS, loaded.sidebarItemOrder.pluginOrder);

    expect(displayCore.map((i) => i.path)).toEqual(["/analytics", "/sessions", "/models"]);
    expect(displayPlugin.map((i) => i.path)).toEqual(["/my-plugin", "/another-plugin"]);
  });

  it("fold state change preserves order on both sides through round-trip", () => {
    // Simulate: user sets separate orders -> toggles fold on -> toggles fold off
    // All via the save/load cycle

    // Step 1: User customizes separate orders
    saveSettings({
      ...loadSettings(),
      sidebarItemOrder: {
        ...loadSettings().sidebarItemOrder,
        coreOrder: sidebarOrderItem(["/models", "/analytics", "/sessions"]),
        pluginOrder: sidebarOrderItem(["/my-plugin"]),
      },
    });

    // Step 2: Toggle fold ON — provider saves unified order but keeps separate
    saveSettings({
      ...loadSettings(),
      sidebarItemOrder: {
        pluginsFoldedIntoSidebar: true,
        coreOrder: loadSettings().sidebarItemOrder.coreOrder,
        pluginOrder: loadSettings().sidebarItemOrder.pluginOrder,
        unifiedOrder: sidebarOrderItem(["/my-plugin", "/models", "/analytics", "/sessions", "/another-plugin"]),
      },
    });

    // Step 3: Toggle fold OFF
    saveSettings({
      ...loadSettings(),
      sidebarItemOrder: {
        ...loadSettings().sidebarItemOrder,
        pluginsFoldedIntoSidebar: false,
      },
    });

    // Step 4: Verify orders preserved
    const final_ = loadSettings();
    const coreItems = [{ path: "/sessions", label: "S" }, { path: "/analytics", label: "A" }, { path: "/models", label: "M" }];
    const pluginItems = [{ path: "/my-plugin", label: "MP" }, { path: "/another-plugin", label: "AP" }];

    const displayedCore = applySidebarOrder(coreItems, final_.sidebarItemOrder.coreOrder);
    const displayedPlugin = applySidebarOrder(pluginItems, final_.sidebarItemOrder.pluginOrder);

    expect(displayedCore.map((i) => i.path)).toEqual(["/models", "/analytics", "/sessions"]);
    expect(displayedPlugin.map((i) => i.path)).toEqual(["/my-plugin", "/another-plugin"]);
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Scenario (d): Fresh install — fold-off with default ordering
// ═══════════════════════════════════════════════════════════════════════
describe("Scenario (d): fresh install defaults", () => {
  it("returns default settings when localStorage is empty", () => {
    const settings = loadSettings();
    expect(settings).toEqual(DEFAULT_SETTINGS);
  });

  it("default fold state is OFF", () => {
    const settings = loadSettings();
    expect(settings.sidebarItemOrder.pluginsFoldedIntoSidebar).toBe(false);
  });

  it("default order lists are all empty", () => {
    const settings = loadSettings();
    expect(settings.sidebarItemOrder.coreOrder).toEqual([]);
    expect(settings.sidebarItemOrder.pluginOrder).toEqual([]);
    expect(settings.sidebarItemOrder.unifiedOrder).toEqual([]);
  });

  it("empty order means items render in natural (insertion) order", () => {
    // With no saved order, applySidebarOrder returns items as-is
    const result = applySidebarOrder(CORE_ITEMS, []);
    expect(result.map((i) => i.path)).toEqual(["/sessions", "/analytics", "/models"]);
  });

  it("all kanban columns and side-menu tabs default to visible", () => {
    const settings = loadSettings();
    for (const v of Object.values(settings.kanbanColumns)) {
      expect(v).toBe(true);
    }
    for (const v of Object.values(settings.sideMenuTabs)) {
      expect(v).toBe(true);
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════
// Edge cases and regressions
// ═══════════════════════════════════════════════════════════════════════
describe("Edge cases and regression guards", () => {
  it("applySidebarOrder handles items not present in saved order (new plugin installed)", () => {
    // User has saved order for [sessions, analytics]; models just got installed
    const saved = sidebarOrderItem(["/sessions", "/analytics"]);
    const result = applySidebarOrder(CORE_ITEMS, saved);

    expect(result[0].path).toBe("/sessions");
    expect(result[1].path).toBe("/analytics");
    // models should be appended at end (not in saved order)
    expect(result[2].path).toBe("/models");
  });

  it("applySavedOrder handles items not in the saved list", () => {
    const saved = sidebarOrderItem(["/sessions", "/analytics"]);
    const result = applySavedOrder(["/sessions", "/analytics", "/new-page"], saved);

    expect(result.map((i) => i.id)).toEqual(["/sessions", "/analytics", "/new-page"]);
  });

  it("saveSettings round-trips through JSON correctly", () => {
    const order = sidebarOrderItem(["/b", "/a", "/c"]);
    const settings: DashboardSettings = {
      kanbanColumns: DEFAULT_SETTINGS.kanbanColumns,
      sideMenuTabs: DEFAULT_SETTINGS.sideMenuTabs,
      sidebarItemOrder: {
        pluginsFoldedIntoSidebar: true,
        coreOrder: [],
        pluginOrder: [],
        unifiedOrder: order,
      },
    };
    saveSettings(settings);
    const raw = store[STORAGE_KEY];
    const parsed = JSON.parse(raw);
    expect(parsed.sidebarItemOrder.pluginsFoldedIntoSidebar).toBe(true);
    expect(parsed.sidebarItemOrder.unifiedOrder).toEqual([{ id: "/b" }, { id: "/a" }, { id: "/c" }]);
  });

  it("loadSettings gracefully handles corrupted JSON", () => {
    store[STORAGE_KEY] = "not valid json{{{";
    const settings = loadSettings();
    // Should return defaults without throwing
    expect(settings).toEqual(DEFAULT_SETTINGS);
  });

  it("saveSettings does not throw when localStorage is unavailable", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => null,
      setItem: () => { throw new Error("QuotaExceeded"); },
      removeItem: () => { throw new Error("QuotaExceeded"); },
    });
    // Should not throw
    expect(() => saveSettings(DEFAULT_SETTINGS)).not.toThrow();
  });

  it("partitioning: core items and plugin items remain distinct when fold is off", () => {
    // This tests the conceptual model used in App.tsx filteredSidebarNav
    // With fold off, core and plugin items are separate
    const settings = loadSettings();
    expect(settings.sidebarItemOrder.pluginsFoldedIntoSidebar).toBe(false);

    // After setting independent orders:
    saveSettings({
      ...settings,
      sidebarItemOrder: {
        ...settings.sidebarItemOrder,
        coreOrder: sidebarOrderItem(["/models", "/sessions"]),
        pluginOrder: sidebarOrderItem(["/my-plugin", "/another-plugin"]),
      },
    });

    const loaded = loadSettings();
    // Verify orders are independent — no cross-contamination
    const coreIds = loaded.sidebarItemOrder.coreOrder.map((o) => o.id);
    const pluginIds = loaded.sidebarItemOrder.pluginOrder.map((o) => o.id);

    expect(coreIds).not.toContain("/my-plugin");
    expect(pluginIds).not.toContain("/sessions");
  });
});
