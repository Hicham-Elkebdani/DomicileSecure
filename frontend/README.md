# DomicileSecure — Frontend

Interface web : Next.js 16 (App Router), React 19, TypeScript strict, Tailwind CSS 4, TanStack Query, Recharts.

## Démarrer

```bash
cp .env.example .env.local     # Windows : Copy-Item .env.example .env.local
npm install
npm run dev                    # http://localhost:3000 (API attendue sur :8000)
```

| Script | Rôle |
|---|---|
| `npm run dev` | Serveur de développement |
| `npm run build` | Build de production (`output: "standalone"`) |
| `npm run start` | Servir le build |
| `npm run lint` | ESLint (règles Next.js + React Hooks) |
| `npm run typecheck` | Vérification TypeScript |

## Pages

| Route | Contenu |
|---|---|
| `/login` | Connexion |
| `/` | Tableau de bord : indicateurs, activité sur 7 jours (graphique + vue tableau), résumé, alertes récentes |
| `/alerts` | Alertes filtrables ; « traitée » ou « fausse alerte » |
| `/events` | Journal de l'activité (une ligne par passage) |
| `/persons` | Membres, invités, visiteurs détectés ; enrôlement des visages |
| `/cameras` | État des caméras et des portes ; identifiant à copier pour le worker |
| `/summary` | Résumé du jour et historique |
| `/settings` | Notifications push sur cet appareil |

## Organisation

```
src/
├── app/                    # routes (App Router) ; (app)/ = pages protégées
├── components/
│   ├── ui/                 # boutons, cartes, formulaires, modale, toasts…
│   ├── layout/             # coquille (navigation, état temps réel)
│   ├── dashboard/          # graphique d'activité, tuiles
│   └── alerts/             # liste d'alertes, badge de gravité
└── lib/
    ├── api/                # client HTTP, types (miroir des schémas Pydantic), endpoints
    ├── auth/               # contexte d'authentification
    ├── realtime/           # WebSocket (reconnexion, invalidation du cache)
    └── push/               # abonnement Web Push
public/sw.js                # service worker (notifications)
```

- **Un seul fichier connaît les URL** : `lib/api/endpoints.ts`.
- **Temps réel** : les messages WebSocket invalident les requêtes TanStack concernées ; pas d'état dupliqué.
- **Accessibilité** : la gravité est toujours indiquée par icône et libellé, pas seulement par la couleur ; le graphique a une vue tableau ; il y a un mode sombre et une version mobile.
