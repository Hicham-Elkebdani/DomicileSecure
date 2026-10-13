# Sécurité et vie privée

Un système de sécurité manipule des **données biométriques** et donne des indices sur la présence des habitants. La sécurité est une exigence fonctionnelle, pas une option.

## Mesures en place

### Authentification et accès
- Mots de passe hachés avec **Argon2** (`pwdlib`), 10 caractères minimum.
- **JWT** signés (HS256), courte durée (`ACCESS_TOKEN_EXPIRE_MINUTES`, 60 min par défaut), avec `exp`, `iat`, `nbf` et `type` vérifiés.
- Même message et même temps de réponse pour « e-mail inconnu » et « mauvais mot de passe » (hachage factice) : on ne peut pas deviner quels comptes existent.
- **Limitation de débit** sur `/auth/login` : 5 essais par minute et par IP.
- Rôles membre / administrateur ; pas d'inscription publique.
- Worker authentifié par **clé API** comparée en temps constant (`hmac.compare_digest`), limitée aux routes `/ingest/*`.
- WebSocket authentifié par le **premier message** (le jeton n'apparaît pas dans les URL ni dans les logs).

### Configuration
- Tous les secrets sont dans `.env`, jamais dans Git (`.gitignore`) ; `scripts/generate_secrets.py` génère des valeurs fortes.
- En `ENVIRONMENT=production`, l'API **refuse de démarrer** avec les secrets par défaut, un JWT de moins de 32 caractères ou `CORS_ORIGINS=*`.
- Swagger et OpenAPI sont désactivés en production.

### Entrées et sorties
- Validation stricte de chaque entrée (Pydantic) : types, longueurs, dates avec fuseau, cohérence type/label, taille des lots.
- Photos : types MIME autorisés (JPEG/PNG/WebP), taille maximale, décodage vérifié.
- Requêtes SQL exclusivement via l'ORM (pas d'injection SQL).
- En-têtes de sécurité (API et frontend) : `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`.
- Erreurs internes : message générique pour le client, trace complète dans les logs avec l'identifiant de requête.
- Abonnements push : seules les URL `https://` sont acceptées.

### Vie privée (loi marocaine 09-08, RGPD / UK GDPR)
- **Aucune photo conservée** : seule la signature (128 nombres) est stockée.
- **Aucune vidéo transmise** : le worker envoie des observations, pas des images.
- **Droit à l'effacement** : `DELETE /persons/{id}` supprime la personne et ses signatures ; `DELETE /persons/{id}/faces` supprime uniquement les signatures.
- URL RTSP (avec identifiants) seulement dans le `.env` du worker, jamais en base ; masquées dans les logs.
- Enrôlement uniquement avec le **consentement** des personnes (rappel affiché dans l'interface).
- `data/` et `artifacts/` exclus de Git.

## Checklist avant la production

- [ ] `ENVIRONMENT=production`, secrets régénérés, `.env` en `chmod 600` et propriétaire = utilisateur du service.
- [ ] HTTPS obligatoire (Nginx + Let's Encrypt), HSTS activé.
- [ ] PostgreSQL avec un utilisateur dédié aux droits minimaux, sauvegardes chiffrées.
- [ ] `CORS_ORIGINS` limité au domaine du frontend.
- [ ] Workers et caméras sur un réseau isolé (VLAN), caméras sans accès Internet.
- [ ] Mises à jour des dépendances (`pip-audit`, `npm audit`, Dependabot).
- [ ] Logs JSON centralisés et alertes sur les erreurs 5xx.

## Améliorations prévues

| Priorité | Amélioration |
|---|---|
| Haute | Jeton dans un cookie `httpOnly` + `SameSite=Strict` et jeton de rafraîchissement, au lieu de `localStorage` (limite l'impact d'une faille XSS) |
| Haute | Content-Security-Policy stricte sur le frontend |
| Moyenne | Limitation de débit partagée (Redis) si plusieurs instances d'API |
| Moyenne | Purge automatique (événements 90 j, visiteurs non identifiés 30 j) |
| Moyenne | Journal d'audit (qui a supprimé, promu ou consulté quoi) |
| Basse | Double authentification (TOTP) pour les administrateurs |
| Basse | Chiffrement des signatures faciales au repos |
