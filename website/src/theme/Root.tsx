import Head from '@docusaurus/Head';
import type {ReactNode} from 'react';

type RootProps = {
  children: ReactNode;
};

function MaintenancePage() {
  return (
    <>
      <Head>
        <meta name="robots" content="noindex,nofollow" />
        <title>Maintenance | Hermes Agent</title>
      </Head>
      <main
        style={{
          minHeight: '100vh',
          display: 'grid',
          placeItems: 'center',
          padding: '2rem',
          background: '#07070d',
          color: '#e8e4dc',
          fontFamily:
            'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
          textAlign: 'center',
        }}
      >
        <section style={{maxWidth: '38rem'}}>
          <img
            src="/docs/img/logo.png"
            alt="Hermes Agent"
            style={{
              width: '4rem',
              height: '4rem',
              marginBottom: '1.5rem',
            }}
          />
          <p
            style={{
              margin: '0 0 0.75rem',
              color: '#FFD700',
              fontSize: '0.82rem',
              fontWeight: 700,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
            }}
          >
            Maintenance
          </p>
          <h1
            style={{
              margin: '0 0 1rem',
              fontSize: 'clamp(2rem, 4vw, 3.5rem)',
              lineHeight: 1.05,
            }}
          >
            Nous Hermes is in maintenance mode
          </h1>
          <p
            style={{
              margin: 0,
              color: '#b7b1a7',
              fontSize: '1.05rem',
              lineHeight: 1.7,
            }}
          >
            We are sorting out a few Hermes things and will bring the site back
            once the docs are ready.
          </p>
        </section>
      </main>
    </>
  );
}

export default function Root({children}: RootProps) {
  void children;
  return <MaintenancePage />;
}
