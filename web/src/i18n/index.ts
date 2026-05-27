import { en } from "./en";
import type { Translations } from "./types";

export { I18nProvider, useI18n, LOCALE_META } from "./context";
export type { Locale, Translations } from "./types";

type DashboardTranslations = NonNullable<Translations["dashboard"]>;

export function dashboardText(t: Translations): DashboardTranslations {
  const fallback = en.dashboard as DashboardTranslations;
  const override: Partial<DashboardTranslations> = t.dashboard ?? {};

  return {
    auth: { ...fallback.auth, ...override.auth },
    chat: {
      ...fallback.chat,
      ...override.chat,
      states: { ...fallback.chat.states, ...override.chat?.states },
    },
    toolCall: { ...fallback.toolCall, ...override.toolCall },
    modelPicker: { ...fallback.modelPicker, ...override.modelPicker },
    models: {
      ...fallback.models,
      ...override.models,
      auxTasks: {
        ...fallback.models.auxTasks,
        ...override.models?.auxTasks,
      },
    },
    modelInfo: { ...fallback.modelInfo, ...override.modelInfo },
    oauth: { ...fallback.oauth, ...override.oauth },
    analytics: { ...fallback.analytics, ...override.analytics },
    cron: { ...fallback.cron, ...override.cron },
  };
}
