// primitives.tsx — small reusable building blocks for Lattice UI
import React, { useState, useRef, useEffect, useLayoutEffect } from 'react';

export function cn(...parts: (string | boolean | undefined | null)[]): string {
  return parts.filter(Boolean).join(' ');
}

interface TooltipProps {
  label: string;
  side?: 'top' | 'bottom' | 'left' | 'right';
  delay?: number;
  children: React.ReactNode;
}

/* Tooltip — portal-less, positions itself via getBoundingClientRect */
export function Tooltip({ label, side = 'bottom', delay = 350, children }: TooltipProps) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const wrapRef = useRef<HTMLSpanElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const show = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      const el = wrapRef.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const y = side === 'top' ? r.top - 8 :
                side === 'bottom' ? r.bottom + 8 :
                side === 'left' ? r.left - 8 : r.right + 8;
      setPos({ x: cx, y });
      setOpen(true);
    }, delay);
  };
  const hide = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setOpen(false);
  };

  return (
    <span
      ref={wrapRef}
      onMouseEnter={show}
      onMouseLeave={hide}
      onFocus={show}
      onBlur={hide}
      style={{ display: 'inline-flex' }}
    >
      {children}
      {open && (
        <span className={`tt tt-${side}`} style={{ left: pos.x, top: pos.y }}>
          {label}
        </span>
      )}
    </span>
  );
}

interface ActionProps {
  label: string;
  side?: 'top' | 'bottom' | 'left' | 'right';
  onClick?: () => void;
  active?: boolean;
  danger?: boolean;
  size?: number;
  children: React.ReactNode;
  [key: string]: any;
}

/* Action — accessible icon button with built-in tooltip and sr-only label */
export function Action({ label, side = 'bottom', onClick, active, danger, size = 26, children, ...rest }: ActionProps) {
  return (
    <Tooltip label={label} side={side}>
      <button
        type="button"
        onClick={onClick}
        className={cn('icon-btn', active && 'is-active', danger && 'is-danger')}
        style={{ width: size, height: size }}
        {...rest}
      >
        <span className="sr-only">{label}</span>
        {children}
      </button>
    </Tooltip>
  );
}

/* useMediaQuery — fixed (no `matches` in deps) */
export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() =>
    typeof window !== 'undefined' ? window.matchMedia(query).matches : false
  );
  useEffect(() => {
    const m = window.matchMedia(query);
    const onChange = () => setMatches(m.matches);
    setMatches(m.matches);
    m.addEventListener('change', onChange);
    return () => m.removeEventListener('change', onChange);
  }, [query]);
  return matches;
}

/* useClickOutside — generic */
export function useClickOutside(
  ref: React.RefObject<HTMLElement | null>,
  onOutside: (e: MouseEvent) => void,
  when = true
) {
  useEffect(() => {
    if (!when) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onOutside(e);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [ref, onOutside, when]);
}

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  width?: number;
}

/* Modal — shared shell with backdrop, escape, focus trap-lite */
export function Modal({ open, onClose, title, children, width = 560 }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal" style={{ maxWidth: width }}>
        <div className="modal-hd">
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
              <path d="M4 4l8 8M12 4l-8 8" />
            </svg>
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

interface InlineEditableProps {
  value: string;
  onChange: (val: string) => void;
  placeholder?: string;
  type?: string;
}

/* InlineEditable — click to edit, blur to save */
export function InlineEditable({ value, onChange, placeholder = '—', type = 'text' }: InlineEditableProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { setDraft(value); }, [value]);
  useLayoutEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const commit = () => {
    setEditing(false);
    if (draft !== value) onChange(draft);
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        className="inline-edit"
        type={type}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === 'Enter') commit();
          if (e.key === 'Escape') { setDraft(value); setEditing(false); }
        }}
      />
    );
  }
  return (
    <button className="inline-display" onClick={() => setEditing(true)}>
      <span>{value || <em style={{ color: 'var(--muted-2)' }}>{placeholder}</em>}</span>
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M11 2l3 3-8 8H3v-3l8-8z" />
      </svg>
    </button>
  );
}
