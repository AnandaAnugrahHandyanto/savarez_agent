# Desktop Renderer Boot Fix — D0.8

## 1. Resumo
- Status: fix aplicado e revalidado.
- GO/NO-GO: GO para seguir a D1 visual, com a ressalva de que o renderer precisa continuar sendo observado em Electron e não apenas no browser local.
- Erro original: `src/app/gateway/hooks/use-gateway-boot.ts` → `desktop variable redeclared` / `It can not be redeclared here`.
- Causa raiz: o hook carregava a bridge em uma variável local chamada `desktop`, e a correção controlada foi renomear a referência para `desktopBridge` para eliminar a colisão de binding no caminho de HMR/transform do renderer.
- Correção aplicada: rename mínimo e sem mudança de lógica de boot.

## 2. Arquivos alterados
Arquivo | Motivo | Risco
--- | --- | ---
src/app/gateway/hooks/use-gateway-boot.ts | Renomear a referência da bridge para `desktopBridge` e manter o boot flow intacto | Baixo

## 3. Validações
- type-check: passou (`npm run type-check` → exit 0)
- build: passou (`npm run build` → exit 0)
- lint global: falhou por problemas preexistentes no código-base, fora deste arquivo
- lint focado: passou (`npx eslint src/app/gateway/hooks/use-gateway-boot.ts` → exit 0)
- dev:renderer: sem o erro de transform/redeclaração após o fix
- dev:electron: iniciou, conectou ao Vite e expôs o renderer via remote debugging; a bridge ficou disponível no renderer do Electron

## 4. Estado pós-correção
- Erro de redeclaração: não observado na inspeção pós-fix.
- Hook-order: não reapareceu.
- IPC bridge: presente no Electron (`window.hermesDesktop === true` no renderer inspecionado).
- Overlay: ausente no renderer do Electron no momento da inspeção.
- Telas acessíveis: shell principal com nav de `Skills & Tools`, `Messaging`, `Artifacts`, `Agents`, `Cron` e perfil `default`; Settings foi tentado via botão de topo, mas não expôs um modal/dialog distinto.

## 5. Segurança Electron
- contextIsolation: preservado.
- nodeIntegration: não habilitado.
- preload: mantido.
- bridge: não houve bridge fake; `window.hermesDesktop` veio do preload real.
- observações: a bridge expõe um conjunto explícito de métodos; `window.electron` permaneceu ausente.

## 6. Próxima decisão
- Pode ir para D1 visual? Sim, com cuidado: a barreira atual do renderer foi removida e a bridge está disponível no Electron.
- Precisa voltar para IPC/preload? Não por enquanto; a inspeção atual aponta que o problema principal estava no renderer/HMR, não no preload.
