/**
 * SidebarReorder — drag-and-drop reorderable list for sidebar nav items.
 *
 * Uses @dnd-kit/sortable for reliable cross-platform drag-and-drop.
 * Icon picker uses CSS anchor positioning (same pattern as @nous-research/ui DropdownMenu).
 * Supports two modes:
 * - folded=false: two independent lists (core + plugin) with separate order
 * - folded=true: single unified list
 */

import { useState, useCallback, useEffect, useId, useRef } from "react";
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Menu, Pencil, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { ICON_REGISTRY, ICON_NAMES } from "@/lib/icon-registry";

interface ReorderItem {
  id: string;
  label: string;
  icon?: string;
  customLabel?: string;
}

interface ItemCustomization {
  label?: string;
  icon?: string;
}

/* ── Icon picker using CSS anchor positioning ───────────────────── */

type AnchorStyle = React.CSSProperties & Record<string, string | number>;

function IconPicker({
  currentIcon,
  onSelect,
}: {
  currentIcon?: string;
  onSelect: (icon: string) => void;
}) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const anchor = `--icon-picker-${id.replace(/:/g, "")}`;

  const panelStyle: AnchorStyle = {
    position: "fixed",
    positionAnchor: anchor,
    positionTryFallbacks: "flip-block, flip-inline",
    left: "calc(anchor(left) - 0.5rem)",
    top: "calc(anchor(top) - 0.5rem)",
  };

  useEffect(() => {
    if (!open) return;
    const ac = new AbortController();
    document.addEventListener(
      "mousedown",
      (e) => {
        if (!ref.current?.contains(e.target as Node)) {
          setOpen(false);
        }
      },
      { signal: ac.signal },
    );
    return () => ac.abort();
  }, [open]);

  const CurrentIcon = currentIcon ? ICON_REGISTRY[currentIcon] : null;

  return (
    <span className="relative inline-block align-top" ref={ref}>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setOpen(!open);
        }}
        style={{ anchorName: anchor } as AnchorStyle}
        className={cn(
          "flex h-6 w-6 items-center justify-center rounded transition-colors",
          "hover:bg-secondary/50",
          open && "bg-secondary/50",
        )}
        title="Change icon"
      >
        {CurrentIcon ? (
          <CurrentIcon className="h-4 w-4 text-text-tertiary" />
        ) : (
          <span className="text-[10px] text-text-tertiary">…</span>
        )}
      </button>

      {open && (
        <div
          className="z-50 grid grid-cols-6 gap-1 rounded-lg border border-border bg-background-base p-2 shadow-lg"
          style={panelStyle}
        >
          {ICON_NAMES.map((name) => {
            const Icon = ICON_REGISTRY[name];
            return (
              <button
                type="button"
                key={name}
                onClick={() => {
                  onSelect(name);
                  setOpen(false);
                }}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-md transition-colors",
                  "hover:bg-secondary/50",
                  currentIcon === name && "bg-midground/30 ring-1 ring-midground",
                )}
                title={name}
              >
                <Icon className="h-4 w-4" />
              </button>
            );
          })}
          <button
            type="button"
            onClick={() => {
              onSelect("");
              setOpen(false);
            }}
            className={cn(
              "col-span-6 mt-1 flex items-center justify-center gap-1 rounded-md px-2 py-1",
              "text-xs text-text-tertiary transition-colors hover:bg-secondary/30",
              !currentIcon && "bg-midground/30",
            )}
          >
            Reset to default
          </button>
        </div>
      )}
    </span>
  );
}

/* ── Sortable item ──────────────────────────────────────────────── */

function SortableItem({
  item,
  isOverlay = false,
  customization,
  onLabelChange,
  onIconChange,
}: {
  item: ReorderItem;
  isOverlay?: boolean;
  customization?: ItemCustomization;
  onLabelChange?: (id: string, label: string) => void;
  onIconChange?: (id: string, icon: string) => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.id });

  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.3 : 1,
    zIndex: isDragging ? 999 : undefined,
  };

  const displayLabel = customization?.label || item.customLabel || item.label;
  const displayIcon = customization?.icon || item.icon;

  const handleStartEdit = useCallback(() => {
    setEditValue(displayLabel);
    setEditing(true);
    setTimeout(() => inputRef.current?.focus(), 0);
  }, [displayLabel]);

  const handleSaveEdit = useCallback(() => {
    if (editValue.trim() && onLabelChange) {
      onLabelChange(item.id, editValue.trim());
    }
    setEditing(false);
  }, [editValue, item.id, onLabelChange]);

  const handleCancelEdit = useCallback(() => {
    setEditing(false);
  }, []);

  return (
    <li
      ref={setNodeRef}
      style={style}
      className={cn(
        "group flex items-center gap-2 px-4 py-2",
        "transition-colors hover:bg-secondary/30",
        "border-b border-border last:border-b-0",
        isDragging && "shadow-lg rounded bg-background-base",
        isOverlay && "shadow-2xl rounded bg-background-base ring-2 ring-midground/30",
      )}
    >
      {/* Drag handle — ONLY here gets pointer listeners */}
      <div
        {...attributes}
        {...listeners}
        className="cursor-grab active:cursor-grabbing select-none"
      >
        <Menu className="h-3.5 w-3.5 shrink-0 text-text-tertiary" />
      </div>

      {/* Icon picker */}
      {onIconChange && (
        <IconPicker
          currentIcon={displayIcon}
          onSelect={(icon) => onIconChange(item.id, icon)}
        />
      )}

      {/* Label */}
      {editing ? (
        <div className="flex flex-1 items-center gap-1">
          <input
            ref={inputRef}
            type="text"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSaveEdit();
              if (e.key === "Escape") handleCancelEdit();
            }}
            className="flex-1 rounded border border-border bg-background-base px-1 py-0.5 text-sm outline-none focus:border-midground"
            onClick={(e) => e.stopPropagation()}
          />
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleSaveEdit();
            }}
            className="rounded p-0.5 text-success hover:bg-secondary/30"
          >
            <Check className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleCancelEdit();
            }}
            className="rounded p-0.5 text-text-tertiary hover:bg-secondary/30"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : (
        <>
          <span className="flex-1 text-sm truncate">{displayLabel}</span>
          {onLabelChange && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleStartEdit();
              }}
              className={cn(
                "rounded p-0.5 text-text-tertiary opacity-0 transition-opacity",
                "hover:bg-secondary/30 hover:text-text-primary",
                "group-hover:opacity-100",
              )}
              title="Rename"
            >
              <Pencil className="h-3 w-3" />
            </button>
          )}
        </>
      )}
    </li>
  );
}

/* ── Overlay item (drag preview) ────────────────────────────────── */

function DragOverlayItem({
  item,
  customization,
}: {
  item: ReorderItem;
  customization?: ItemCustomization;
}) {
  const displayLabel = customization?.label || item.customLabel || item.label;

  return (
    <div
      className={cn(
        "flex items-center gap-2 px-4 py-2 cursor-grabbing select-none",
        "border-b border-border last:border-b-0",
        "shadow-2xl rounded bg-background-base ring-2 ring-midground/30",
      )}
    >
      <Menu className="h-3.5 w-3.5 shrink-0 text-text-tertiary" />
      <span className="text-sm truncate">{displayLabel}</span>
    </div>
  );
}

/* ── Sortable list ──────────────────────────────────────────────── */

function SidebarReorderList({
  items,
  onReorder,
  label,
  customizations,
  onLabelChange,
  onIconChange,
}: {
  items: ReorderItem[];
  onReorder: (items: ReorderItem[]) => void;
  label?: string;
  customizations?: Map<string, ItemCustomization>;
  onLabelChange?: (id: string, label: string) => void;
  onIconChange?: (id: string, icon: string) => void;
}) {
  const itemsRef = useRef(items);
  itemsRef.current = items;

  const [activeId, setActiveId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 3 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragStart = useCallback((event: DragStartEvent) => {
    setActiveId(String(event.active.id));
  }, []);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      setActiveId(null);
      const { active, over } = event;
      if (!over || active.id === over.id) return;

      const currentItems = itemsRef.current;
      const oldIndex = currentItems.findIndex((i) => i.id === active.id);
      const newIndex = currentItems.findIndex((i) => i.id === over.id);
      if (oldIndex === -1 || newIndex === -1) return;

      onReorder(arrayMove(currentItems, oldIndex, newIndex));
    },
    [onReorder],
  );

  const activeItem = activeId ? items.find((i) => i.id === activeId) : null;

  return (
    <div className="flex flex-col gap-1">
      {label && (
        <span className="px-4 pt-2 pb-1 text-xs font-medium tracking-[0.12em] text-text-tertiary uppercase">
          {label}
        </span>
      )}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={items.map((i) => i.id)}
          strategy={verticalListSortingStrategy}
        >
          <ul className="flex flex-col">
            {items.map((item) => (
              <SortableItem
                key={item.id}
                item={item}
                customization={customizations?.get(item.id)}
                onLabelChange={onLabelChange}
                onIconChange={onIconChange}
              />
            ))}
          </ul>
        </SortableContext>
        <DragOverlay dropAnimation={null}>
          {activeItem ? (
            <DragOverlayItem
              item={activeItem}
              customization={customizations?.get(activeItem.id)}
            />
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}

/* ── Main component ─────────────────────────────────────────────── */

interface SidebarReorderProps {
  coreItems: ReorderItem[];
  pluginItems: ReorderItem[];
  unifiedItems: ReorderItem[];
  folded: boolean;
  onCoreReorder: (items: ReorderItem[]) => void;
  onPluginReorder: (items: ReorderItem[]) => void;
  onUnifiedReorder: (items: ReorderItem[]) => void;
  onFoldToggle: (folded: boolean) => void;
  mainItemsLabel: string;
  pluginItemsLabel: string;
  unifiedItemsLabel: string;
  customizations?: Map<string, ItemCustomization>;
  onLabelChange?: (id: string, label: string, group: "core" | "plugin" | "unified") => void;
  onIconChange?: (id: string, icon: string, group: "core" | "plugin" | "unified") => void;
}

export function SidebarReorder({
  coreItems,
  pluginItems,
  unifiedItems,
  folded,
  onCoreReorder,
  onPluginReorder,
  onUnifiedReorder,
  onFoldToggle,
  mainItemsLabel,
  pluginItemsLabel,
  unifiedItemsLabel,
  customizations,
  onLabelChange,
  onIconChange,
}: SidebarReorderProps) {
  return (
    <div className="flex flex-col gap-3">
      {/* Fold toggle */}
      <label
        className={cn(
          "flex cursor-pointer items-center justify-between gap-4",
          "px-4 py-3 transition-colors hover:bg-secondary/30",
          "border-b border-border",
        )}
      >
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="text-sm font-medium">Fold plugins into sidebar</span>
          <span className="text-xs text-text-tertiary">
            When enabled, plugin items merge into the main nav and can be reordered together.
          </span>
        </div>
        <div
          role="switch"
          aria-checked={folded}
          tabIndex={0}
          onClick={() => onFoldToggle(!folded)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onFoldToggle(!folded);
            }
          }}
          className={cn(
            "relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center",
            "rounded-full border border-current/20 transition-colors",
            folded ? "bg-midground/30" : "bg-transparent",
          )}
        >
          <span
            className={cn(
              "inline-block h-4 w-4 rounded-full transition-transform",
              "bg-midground shadow-sm",
              folded ? "translate-x-[1.375rem]" : "translate-x-1",
            )}
          />
        </div>
      </label>

      {/* Reorder lists */}
      {folded ? (
        <SidebarReorderList
          items={unifiedItems}
          onReorder={onUnifiedReorder}
          label={unifiedItemsLabel}
          customizations={customizations}
          onLabelChange={onLabelChange ? (id, label) => onLabelChange(id, label, "unified") : undefined}
          onIconChange={onIconChange ? (id, icon) => onIconChange(id, icon, "unified") : undefined}
        />
      ) : (
        <>
          <SidebarReorderList
            items={coreItems}
            onReorder={onCoreReorder}
            label={mainItemsLabel}
            customizations={customizations}
            onLabelChange={onLabelChange ? (id, label) => onLabelChange(id, label, "core") : undefined}
            onIconChange={onIconChange ? (id, icon) => onIconChange(id, icon, "core") : undefined}
          />
          {pluginItems.length > 0 && (
            <SidebarReorderList
              items={pluginItems}
              onReorder={onPluginReorder}
              label={pluginItemsLabel}
              customizations={customizations}
              onLabelChange={onLabelChange ? (id, label) => onLabelChange(id, label, "plugin") : undefined}
              onIconChange={onIconChange ? (id, icon) => onIconChange(id, icon, "plugin") : undefined}
            />
          )}
        </>
      )}
    </div>
  );
}
