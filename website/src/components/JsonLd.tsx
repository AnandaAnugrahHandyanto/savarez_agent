import React from 'react';
import {serializeJsonLd} from '@site/src/lib/seoStructuredData';

interface JsonLdProps {
  data: unknown;
}

export default function JsonLd({data}: JsonLdProps): JSX.Element {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{__html: serializeJsonLd(data)}}
    />
  );
}
