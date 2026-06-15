export interface ModelOptionProvider {
  name: string;
  slug: string;
  models?: string[];
  total_models?: number;
  is_current?: boolean;
  warning?: string;
}

export interface ModelOptionsResponse {
  model?: string;
  provider?: string;
  providers?: ModelOptionProvider[];
}

export interface ExpensiveModelConfirmResponse {
  confirm_message?: string;
  confirm_required?: boolean;
  warning?: string;
}

export interface ConfigSetResponse extends ExpensiveModelConfirmResponse {
  value?: string;
}

export interface ApplyModelSelectionArgs {
  gw: { request<T>(method: string, params?: Record<string, unknown>): Promise<T> };
  sessionId: string;
  providerSlug: string;
  model: string;
  persistGlobal: boolean;
  confirmExpensiveModel?: boolean;
}

export async function applyModelSelection({
  gw,
  sessionId,
  providerSlug,
  model,
  persistGlobal,
  confirmExpensiveModel = false,
}: ApplyModelSelectionArgs): Promise<ExpensiveModelConfirmResponse | void> {
  const global = persistGlobal ? " --global" : "";
  const result = await gw.request<ConfigSetResponse>("config.set", {
    confirm_expensive_model: confirmExpensiveModel,
    key: "model",
    session_id: sessionId,
    value: `${model} --provider ${providerSlug}${global}`,
  });

  if (result?.confirm_required) {
    return {
      confirm_required: true,
      confirm_message:
        result.confirm_message ||
        result.warning ||
        "This model has unusually high known pricing.",
      warning: result.warning,
    };
  }
}

export function modelShortName(model?: string, provider?: string): string {
  if (!model) return provider ? `${provider}/…` : "model";
  const slash = model.lastIndexOf("/");
  return slash >= 0 ? model.slice(slash + 1) : model;
}
