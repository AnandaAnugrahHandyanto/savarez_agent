export type Locale = 'en' | 'zh'

/** `isTransientTrailLine` 使用的语言相关匹配模式——纯常量，`.ts` 文件可安全导入 */
export const TRAIL_PATTERNS: Record<Locale, { draftPrefix: string; analyzeLabel: string }> = {
  en: { draftPrefix: 'drafting ', analyzeLabel: 'analyzing tool output…' },
  zh: { draftPrefix: '正在生成 ', analyzeLabel: '正在分析工具输出…' }
}
