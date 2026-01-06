import type {ReactNode} from 'react';
import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type FeatureItem = {
  title: string;
  description: ReactNode;
};

const FeatureList: FeatureItem[] = [
  {
    title: '🌐 Gateway VPS',
    description: (
      <>
        Public-facing ingress layer running on a cloud VPS. Handles authentication
        via Zitadel, SSL termination with Traefik, and tunnel management with Pangolin.
      </>
    ),
  },
  {
    title: '🏠 Private Homelab',
    description: (
      <>
        Zero open ports on your home network. Services connect securely through
        NEWT/WireGuard tunnels. Run Proxmox, AI workloads, and more without exposing
        your home IP.
      </>
    ),
  },
  {
    title: '🔐 Zero Trust Security',
    description: (
      <>
        Every request is authenticated via Zitadel OIDC. Role-based access control
        protects all services. Defense in depth with Cloudflare, Pangolin, and
        application-level auth.
      </>
    ),
  },
];

function Feature({title, description}: FeatureItem) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
