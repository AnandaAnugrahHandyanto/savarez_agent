import { useMemo, useState } from 'react';
import { ArrowRight, BrainCircuit, LockKeyhole, Sparkles, Wand2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';

export interface LoginScreenProps {
  defaultEmail?: string;
  onLogin: (payload: { email: string; password: string; remember: boolean }) => Promise<void>;
}

export function LoginScreen({ defaultEmail = 'renato.mott@gmail.com', onLogin }: LoginScreenProps) {
  const [email, setEmail] = useState(defaultEmail);
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const canSubmit = useMemo(() => email.trim().length > 0 && password.length > 0 && !busy, [busy, email, password]);

  return (
    <div className="relative h-[100dvh] overflow-y-auto overscroll-contain bg-[color:var(--color-background)] text-[color:var(--color-foreground)]">
      <div className="fixed inset-0 pointer-events-none bg-[radial-gradient(circle_at_12%_12%,rgba(251,191,36,0.16),transparent_28%),radial-gradient(circle_at_88%_16%,rgba(16,185,129,0.1),transparent_24%),radial-gradient(circle_at_50%_100%,rgba(59,130,246,0.08),transparent_30%)]" />
      <div className="fixed inset-0 pointer-events-none opacity-[0.04] mix-blend-multiply bg-[repeating-linear-gradient(90deg,transparent_0,transparent_27px,rgba(15,23,42,0.08)_28px),repeating-linear-gradient(0deg,transparent_0,transparent_27px,rgba(15,23,42,0.06)_28px)]" />

      <div className="relative mx-auto grid min-h-full max-w-7xl grid-cols-1 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="order-2 flex items-start px-4 py-6 sm:px-6 sm:py-10 lg:order-1 lg:items-center lg:px-12">
          <div className="max-w-xl">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-[1rem] border border-[color:var(--color-border)] bg-[color:var(--color-card)]/70 shadow-[0_16px_50px_rgba(0,0,0,0.18)]">
                <Sparkles className="h-5 w-5" />
              </div>
              <div>
                <p className="font-expanded text-[0.72rem] uppercase tracking-[0.3em] text-[color:var(--color-muted-foreground)]">
                  Hermes chat studio
                </p>
                <h1 className="mt-1 font-display text-3xl leading-tight sm:text-5xl">
                  Acesso privado com memória persistente
                </h1>
              </div>
            </div>

            <p className="max-w-lg text-base leading-relaxed text-[color:var(--color-muted-foreground)] sm:text-lg">
              Entre com sua conta para abrir chats por assunto, manter memórias entre sessões e usar o backend real com proteção de acesso.
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-3">
              {[
                ['Memória', 'global + por chat'],
                ['Multimodal', 'texto, imagem e áudio'],
                ['Persistência', 'login salvo neste dispositivo'],
              ].map(([title, desc]) => (
                <div key={title} className="rounded-[1.1rem] border border-[color:var(--color-border)] bg-[color:var(--color-card)]/55 p-4">
                  <Badge variant="outline" className="text-[0.56rem]">{title}</Badge>
                  <p className="mt-2 text-sm text-[color:var(--color-muted-foreground)]">{desc}</p>
                </div>
              ))}
            </div>

            <div className="mt-8 flex flex-wrap items-center gap-3 text-[0.78rem] uppercase tracking-[0.2em] text-[color:var(--color-muted-foreground)]">
              <Badge variant="success" className="text-[0.56rem]">login seguro</Badge>
              <span>backend público + sessão persistente</span>
            </div>
          </div>
        </section>

        <section className="order-1 flex items-start justify-center px-4 py-6 sm:px-6 sm:py-10 lg:order-2 lg:px-12">
          <div className="w-full max-w-md rounded-[2rem] border border-[color:var(--color-border)] bg-[color:var(--color-card)]/78 p-6 shadow-[0_24px_90px_rgba(0,0,0,0.24)] backdrop-blur-xl sm:p-8">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-[1rem] border border-[color:var(--color-border)] bg-background/40">
                <LockKeyhole className="h-4 w-4" />
              </div>
              <div>
                <p className="font-compressed text-[0.65rem] uppercase tracking-[0.24em] text-[color:var(--color-muted-foreground)]">
                  login
                </p>
                <h2 className="font-display text-2xl">Bem-vindo de volta</h2>
              </div>
            </div>

            <form
              className="space-y-4"
              onSubmit={async (event) => {
                event.preventDefault();
                if (!canSubmit) return;
                setBusy(true);
                setError('');
                try {
                  await onLogin({ email, password, remember });
                } catch (err) {
                  setError(err instanceof Error ? err.message : 'Falha no login');
                } finally {
                  setBusy(false);
                }
              }}
            >
              <label className="block space-y-2">
                <span className="text-[0.7rem] uppercase tracking-[0.2em] text-[color:var(--color-muted-foreground)]">E-mail</span>
                <Input
                  autoComplete="email"
                  inputMode="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="renato.mott@gmail.com"
                  className="h-11 rounded-[0.95rem]"
                />
              </label>

              <label className="block space-y-2">
                <span className="text-[0.7rem] uppercase tracking-[0.2em] text-[color:var(--color-muted-foreground)]">Senha</span>
                <Input
                  autoComplete="current-password"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Sua senha"
                  className="h-11 rounded-[0.95rem]"
                />
              </label>

              <label className="flex items-center gap-3 rounded-[1rem] border border-[color:var(--color-border)] bg-background/35 px-3 py-3 text-sm">
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(event) => setRemember(event.target.checked)}
                  className={cn(
                    'h-4 w-4 rounded border-[color:var(--color-border)] bg-transparent text-[color:var(--color-foreground)]',
                  )}
                />
                <div>
                  <p className="font-medium">Manter conectado</p>
                  <p className="text-[0.78rem] text-[color:var(--color-muted-foreground)]">Salva a sessão neste navegador.</p>
                </div>
              </label>

              {error && (
                <div className="rounded-[1rem] border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
                  {error}
                </div>
              )}

              <Button type="submit" className="h-11 w-full rounded-[1rem]" disabled={!canSubmit}>
                {busy ? 'entrando...' : 'entrar'}
                <ArrowRight className="h-4 w-4" />
              </Button>
            </form>

            <div className="mt-6 rounded-[1rem] border border-[color:var(--color-border)] bg-[color:var(--color-background)]/30 p-4 text-sm text-[color:var(--color-muted-foreground)]">
              <div className="mb-2 flex items-center gap-2 text-[0.7rem] uppercase tracking-[0.2em] text-[color:var(--color-foreground)]/80">
                <BrainCircuit className="h-4 w-4" />
                memória e acesso
              </div>
              <p>
                Depois do login, seus chats e memórias ficam persistidos localmente e a sessão autenticada fica pronta para reuso.
              </p>
              <div className="mt-3 flex items-center gap-2 text-[0.72rem] uppercase tracking-[0.18em]">
                <Wand2 className="h-3.5 w-3.5" />
                <span>recomenda-se usar no mesmo dispositivo</span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
