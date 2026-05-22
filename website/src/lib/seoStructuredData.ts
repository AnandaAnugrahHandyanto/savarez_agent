export const SITE_ORIGIN = 'https://hermes-agent.nousresearch.com';
export const DOCS_BASE_PATH = '/docs/';
export const DOCS_CANONICAL_URL = `${SITE_ORIGIN}${DOCS_BASE_PATH}`;
export const SITE_NAME = 'Hermes Agent Documentation';
export const PRODUCT_NAME = 'Hermes Agent';
export const ORGANIZATION_NAME = 'Nous Research';
export const GITHUB_REPOSITORY_URL = 'https://github.com/NousResearch/hermes-agent';
export const ORGANIZATION_URL = 'https://nousresearch.com';

export function docsUrl(path = ''): string {
  const normalizedPath = path.replace(/^\/+/, '');
  return normalizedPath ? `${DOCS_CANONICAL_URL}${normalizedPath}` : DOCS_CANONICAL_URL;
}

export function docsImageUrl(path: string): string {
  return docsUrl(`img/${path.replace(/^\/+/, '')}`);
}

export function serializeJsonLd(data: unknown): string {
  return JSON.stringify(data).replace(/</g, '\\u003c');
}

export function buildDocsHomeJsonLd() {
  const docsHomeUrl = docsUrl();
  const organizationId = `${ORGANIZATION_URL}/#organization`;
  const softwareId = `${docsHomeUrl}#software`;

  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Organization',
        '@id': organizationId,
        name: ORGANIZATION_NAME,
        url: ORGANIZATION_URL,
        sameAs: [GITHUB_REPOSITORY_URL],
      },
      {
        '@type': 'SoftwareApplication',
        '@id': softwareId,
        name: PRODUCT_NAME,
        applicationCategory: 'DeveloperApplication',
        operatingSystem: 'Linux, macOS, Windows, Android',
        url: GITHUB_REPOSITORY_URL,
        codeRepository: GITHUB_REPOSITORY_URL,
        license: `${GITHUB_REPOSITORY_URL}/blob/main/LICENSE`,
        publisher: {'@id': organizationId},
      },
      {
        '@type': 'WebSite',
        '@id': `${docsHomeUrl}#website`,
        name: SITE_NAME,
        url: docsHomeUrl,
        description:
          'Documentation for Hermes Agent, the self-improving AI agent built by Nous Research.',
        publisher: {'@id': organizationId},
        about: {'@id': softwareId},
        inLanguage: 'en',
      },
    ],
  };
}

export interface SkillCatalogItem {
  name: string;
  description?: string;
  category?: string;
  categoryLabel?: string;
  docsPath?: string;
}

export function buildSkillsHubJsonLd(skills: SkillCatalogItem[]) {
  const skillsHubUrl = docsUrl('skills/');
  const itemListId = `${skillsHubUrl}#skill-catalog`;
  const representativeSkills = skills.slice(0, 25).map((skill, index) => {
    const itemUrl = skill.docsPath
      ? docsUrl(`user-guide/skills/${skill.docsPath}`)
      : skillsHubUrl;

    return {
      '@type': 'ListItem',
      position: index + 1,
      url: itemUrl,
      item: {
        '@type': 'DefinedTerm',
        name: skill.name,
        description: skill.description,
        inDefinedTermSet: itemListId,
        termCode: skill.category,
      },
    };
  });

  return {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'CollectionPage',
        '@id': `${skillsHubUrl}#collection-page`,
        name: 'Hermes Agent Skills Hub',
        url: skillsHubUrl,
        description:
          'Searchable catalog of built-in, optional, and community skills for Hermes Agent.',
        isPartOf: {'@id': `${docsUrl()}#website`},
        mainEntity: {'@id': itemListId},
      },
      {
        '@type': 'ItemList',
        '@id': itemListId,
        name: 'Hermes Agent skill catalog',
        url: skillsHubUrl,
        numberOfItems: skills.length,
        itemListElement: representativeSkills,
      },
    ],
  };
}
