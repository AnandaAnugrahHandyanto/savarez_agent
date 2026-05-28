// composer.tsx — upgraded composer component
import React, { useState, useRef, useEffect } from 'react';
import { Tooltip } from './primitives';
import { cn } from './primitives';

const PLACEHOLDERS = [
  'Como posso ajudar você hoje?',
  'Resume um documento, escreve um email, planeja um sprint…',
  'Cole um stack trace que eu trio…',
  'Refatore esse componente React…',
  'Qual o resumo das notas da semana passada?',
];

const ATTACH_KINDS: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  image: { label: 'Image', color: '#5B8CFF', icon: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round">
      <rect x="2" y="3" width="12" height="10" rx="1.5"/><circle cx="6" cy="7" r="1.2"/><path d="M2 11l3.5-3 3 2.5L11 8l3 3"/>
    </svg>) },
  pdf: { label: 'PDF', color: '#D94A6B', icon: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round">
      <path d="M4 2h5l3 3v9a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M9 2v3h3"/>
    </svg>) },
  doc: { label: 'Doc', color: '#2EA47A', icon: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round">
      <path d="M4 2h5l3 3v9a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M9 2v3h3M5.5 8h5M5.5 10.5h5M5.5 6h2"/>
    </svg>) },
  file: { label: 'File', color: '#8B5CF6', icon: (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round">
      <path d="M4 2h5l3 3v9a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z"/><path d="M9 2v3h3"/>
    </svg>) },
};

function kindFor(file: File): string {
  if (!file) return 'file';
  if (file.type.startsWith('image/')) return 'image';
  if (file.type === 'application/pdf') return 'pdf';
  if (file.type.includes('word') || /\.(docx?|md|txt|rtf)$/i.test(file.name)) return 'doc';
  return 'file';
}

function ComposerIcon({ name }: { name: string }) {
  const M: Record<string, React.ReactNode> = {
    paperclip: <path d="M10.5 5L5.6 9.9a2 2 0 002.8 2.8L13.5 7.5a3.5 3.5 0 00-4.95-4.95L3.4 7.7a5 5 0 007.07 7.07"/>,
    at:        <g><circle cx="8" cy="8" r="2.5"/><path d="M10.5 8v1.5a1.5 1.5 0 003 0V8a5.5 5.5 0 10-2 4.24"/></g>,
    sparkle:   <path d="M8 2v2.5M8 11.5V14M2 8h2.5M11.5 8H14M4 4l1.8 1.8M10.2 10.2L12 12M12 4l-1.8 1.8M4 12l1.8-1.8"/>,
    globe:     <g><circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c2 2 2 10 0 12M8 2c-2 2-2 10 0 12"/></g>,
    mic:       <g><rect x="6" y="2" width="4" height="8" rx="2"/><path d="M3.5 7.5a4.5 4.5 0 009 0M8 12v2"/></g>,
    send:      <path d="M14 2L7.5 8.5M14 2l-5 12-2-5.5L2 6.5 14 2z"/>,
    chev:      <path d="M4 6l4 4 4-4"/>,
    stop:      <rect x="4" y="4" width="8" height="8" rx="1.5"/>,
    x:         <path d="M4 4l8 8M12 4l-8 8"/>,
  };
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor"
         strokeWidth={name === 'stop' ? 0 : 1.5} strokeLinecap="round" strokeLinejoin="round"
         style={{ fill: name === 'stop' ? 'currentColor' : 'none' }}>
      {M[name]}
    </svg>
  );
}

interface Attachment {
  id: string;
  file: File;
  url: string | null;
  kind: string;
}

interface ComposerProps {
  value: string;
  onChange: (v: string) => void;
  onSend: (payload?: any) => void;
  disabled?: boolean;
  tokens?: string;
  model?: string;
  onPickModel?: (rect: DOMRect) => void;
  rotatePlaceholder?: boolean;
  staticPlaceholder?: string;
}

export function Composer({ value, onChange, onSend, disabled, tokens, model, onPickModel, rotatePlaceholder = false, staticPlaceholder = 'Reply…' }: ComposerProps) {
  const taRef = useRef<HTMLTextAreaElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(false);
  const [phIdx, setPhIdx] = useState(0);
  const [think, setThink] = useState(false);
  const [deep, setDeep] = useState(false);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [listening, setListening] = useState(false);
  const recogRef = useRef<any>(null);
  const baseTextRef = useRef('');

  const expanded = focused || value.length > 0 || attachments.length > 0;

  useEffect(() => {
    if (!rotatePlaceholder || expanded) return;
    const id = setInterval(() => setPhIdx((i) => (i + 1) % PLACEHOLDERS.length), 3800);
    return () => clearInterval(id);
  }, [expanded, rotatePlaceholder]);

  useEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = '44px';
    if (!ta.value) return;
    ta.style.height = Math.min(220, ta.scrollHeight) + 'px';
  }, [value]);

  useEffect(() => {
    return () => attachments.forEach((a) => a.url && URL.revokeObjectURL(a.url));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!disabled && (value.trim() || attachments.length)) {
        const att = attachments.slice();
        setAttachments([]);
        onSend({ think, deep, attachments: att });
      }
    }
  };

  const onPickFiles = (filesList: FileList | null) => {
    const files = Array.from(filesList || []);
    const next = files.map((f) => ({
      id: 'att-' + Math.random().toString(36).slice(2, 9),
      file: f,
      url: f.type.startsWith('image/') ? URL.createObjectURL(f) : null,
      kind: kindFor(f),
    }));
    setAttachments((cur) => [...cur, ...next]);
  };

  const removeAttachment = (id: string) => {
    setAttachments((cur) => {
      const target = cur.find((a) => a.id === id);
      if (target?.url) URL.revokeObjectURL(target.url);
      return cur.filter((a) => a.id !== id);
    });
  };

  const SR = typeof window !== 'undefined' && ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
  const canMic = !!SR;
  const toggleMic = () => {
    if (!canMic) return;
    if (listening) {
      recogRef.current?.stop();
      return;
    }
    baseTextRef.current = value ? value + (value.endsWith(' ') ? '' : ' ') : '';
    const r = new SR();
    r.continuous = true; r.interimResults = true; r.lang = 'en-US';
    r.onresult = (ev: any) => {
      let txt = '';
      for (let i = ev.resultIndex; i < ev.results.length; i++) txt += ev.results[i][0].transcript;
      onChange(baseTextRef.current + txt);
    };
    r.onend = () => setListening(false);
    r.onerror = () => setListening(false);
    recogRef.current = r;
    r.start();
    setListening(true);
  };

  const canSend = !disabled && (value.trim().length > 0 || attachments.length > 0);

  return (
    <div className="composer-wrap">
      <div style={{ width: '100%', maxWidth: 760 }}>
        <div className={cn('composer', expanded && 'is-expanded', focused && 'is-focused')}>

          {attachments.length > 0 && (
            <div className="comp-attach">
              {attachments.map((a) => {
                const K = ATTACH_KINDS[a.kind];
                return (
                  <div key={a.id} className="att-chip" style={{ '--att': K.color } as any}>
                    {a.url ? (
                      <img src={a.url} alt="" className="att-thumb" />
                    ) : (
                      <span className="att-icon">{K.icon}</span>
                    )}
                    <span className="att-meta">
                      <span className="att-name">{a.file.name}</span>
                      <span className="att-sub">{K.label} · {(a.file.size / 1024).toFixed(0)} KB</span>
                    </span>
                    <button className="att-x" onClick={() => removeAttachment(a.id)} aria-label="Remove">
                      <ComposerIcon name="x" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          <textarea
            ref={taRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={onKey}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder={rotatePlaceholder ? PLACEHOLDERS[phIdx] : staticPlaceholder}
            rows={1}
            aria-label="Message"
          />

          <div className="comp-foot">
            <input ref={fileRef} type="file" multiple hidden onChange={(e) => { onPickFiles(e.target.files); (e.target as HTMLInputElement).value = ''; }} />

            <Tooltip label="Attach files" side="top">
              <button className="comp-chip" onClick={() => fileRef.current?.click()}>
                <ComposerIcon name="paperclip" />
              </button>
            </Tooltip>

            <Tooltip label="Mention" side="top">
              <button className="comp-chip">
                <ComposerIcon name="at" />
              </button>
            </Tooltip>

            <Tooltip label={think ? 'Thinking mode on' : 'Thinking mode'} side="top">
              <button className={cn('comp-chip toggle', think && 'is-on')} onClick={() => setThink((v) => !v)}>
                <ComposerIcon name="sparkle" /> <span>Think</span>
              </button>
            </Tooltip>

            <Tooltip label={deep ? 'Deep search on' : 'Deep search'} side="top">
              <button className={cn('comp-chip toggle', deep && 'is-on')} onClick={() => setDeep((v) => !v)}>
                <ComposerIcon name="globe" /> <span>Deep Search</span>
              </button>
            </Tooltip>

            <div className="comp-spacer" />

            <span className="comp-tokens">{tokens} tk</span>

            <Tooltip label="Switch model" side="top">
              <button className="comp-chip model"
                      onClick={(e) => onPickModel?.(e.currentTarget.getBoundingClientRect())}>
                <span>{model}</span> <ComposerIcon name="chev" />
              </button>
            </Tooltip>

            {canMic && (
              <Tooltip label={listening ? 'Stop listening' : 'Voice input'} side="top">
                <button className={cn('icon-btn mic', listening && 'is-listening')}
                        onClick={toggleMic}
                        style={{ width: 30, height: 30 }}>
                  <ComposerIcon name="mic" />
                </button>
              </Tooltip>
            )}

            <Tooltip label={disabled ? 'Stop' : 'Send  ⌘↵'} side="top">
              <button className={cn('send', !canSend && 'disabled')}
                      onClick={() => {
                        if (disabled) { onSend({ stop: true }); return; }
                        if (!canSend) return;
                        const att = attachments.slice();
                        setAttachments([]);
                        onSend({ think, deep, attachments: att });
                      }}>
                <ComposerIcon name={disabled ? 'stop' : 'send'} />
              </button>
            </Tooltip>
          </div>
        </div>
        <div className="comp-hint">
          <span className="kbd-inline">↵</span> send · <span className="kbd-inline">⇧↵</span> newline · <span className="kbd-inline">⌘K</span> palette
        </div>
      </div>
    </div>
  );
}
