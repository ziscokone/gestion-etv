# Procédure d'urgence — Désactivation 2FA par ligne de commande

Ce fichier explique comment désactiver la 2FA d'un compte depuis le serveur,
dans le cas où un utilisateur est bloqué (téléphone perdu, plus de codes de secours,
aucun autre super_admin disponible).

---

## CAS 1 — Déploiement sur Render

### Accéder au Shell Render
1. Va sur https://dashboard.render.com
2. Clique sur ton service (ex: `sgb-billeterie`)
3. Dans le menu de gauche → clique **"Shell"**
4. Une console s'ouvre directement dans le navigateur

### Commandes à taper

```bash
# Désactiver la 2FA d'un utilisateur précis
python manage.py two_factor_disable --username=nom_utilisateur

# Exemple concret pour le super admin "zkone"
python manage.py two_factor_disable --username=zkone
```

### Ce que ça fait
- Supprime le dispositif Google Authenticator lié au compte
- Supprime les codes de secours du compte
- L'utilisateur peut se reconnecter avec juste son mot de passe
- Il devra reconfigurer la 2FA à la prochaine connexion (obligatoire pour son rôle)

---

## CAS 2 — Déploiement sur VPS avec Docker

### Étape 1 — Se connecter au VPS via SSH
```bash
# Depuis ton ordinateur (Terminal / PowerShell)
ssh user@ip-de-ton-vps

# Exemple
ssh root@41.123.45.67
```

### Étape 2 — Voir les containers qui tournent
```bash
docker ps

# Résultat exemple :
# CONTAINER ID   IMAGE              COMMAND            STATUS
# a1b2c3d4e5f6   sgb-billeterie     "gunicorn ..."     Up 3 hours
# f6e5d4c3b2a1   postgres:15        "docker-entryp..."  Up 3 hours
```

### Étape 3 — Entrer dans le container Django
```bash
# Remplace "a1b2c3d4e5f6" par le vrai CONTAINER ID de ton app Django
docker exec -it a1b2c3d4e5f6 bash

# Tu es maintenant INSIDE le container, le prompt change :
# root@a1b2c3d4e5f6:/app#
```

### Étape 4 — Désactiver la 2FA
```bash
python manage.py two_factor_disable --username=nom_utilisateur

# Exemple
python manage.py two_factor_disable --username=zkone
```

### Étape 5 — Sortir du container
```bash
exit
```

---

## CAS 3 — Déploiement sur VPS SANS Docker

### Étape 1 — Se connecter au VPS via SSH
```bash
ssh user@ip-de-ton-vps
```

### Étape 2 — Aller dans le dossier du projet
```bash
cd /chemin/vers/gestion_billeterie
```

### Étape 3 — Activer l'environnement virtuel Python
```bash
source venv/bin/activate
```

### Étape 4 — Désactiver la 2FA
```bash
python manage.py two_factor_disable --username=nom_utilisateur
```

---

## CAS 4 — En local (développement)

```bash
# Dans le terminal, depuis le dossier du projet
cd /chemin/vers/gestion_billeterie
source venv/bin/activate
python manage.py two_factor_disable --username=nom_utilisateur
```

---

## Tableau récapitulatif

| Environnement    | Accès               | Commande Django                                    |
|------------------|---------------------|----------------------------------------------------|
| Render           | Dashboard → Shell   | `python manage.py two_factor_disable --username=X` |
| VPS + Docker     | SSH → docker exec   | `python manage.py two_factor_disable --username=X` |
| VPS sans Docker  | SSH → dossier projet| `python manage.py two_factor_disable --username=X` |
| Local            | Terminal            | `python manage.py two_factor_disable --username=X` |

La commande Django est **toujours la même**.
Seule la façon d'y accéder change selon l'environnement.

---

## Après avoir désactivé la 2FA

```
1. L'utilisateur se connecte avec juste son mot de passe
2. Django le redirige automatiquement vers la page de configuration 2FA
   (car son rôle l'oblige à avoir la 2FA)
3. Il scanne le nouveau QR Code avec son nouveau téléphone
4. Il entre le code pour confirmer
5. C'est fait — la 2FA est reconfigurée sur le nouveau téléphone
```

---

## Connaître le username d'un utilisateur

Si tu ne te souviens plus du username exact, tape cette commande :

```bash
python manage.py shell -c "
from apps.personnel.models import Utilisateur
for u in Utilisateur.objects.filter(role__in=['pdg','super_admin','manager']):
    print(f'{u.username:20} | {u.nom_complet:30} | {u.role}')
"
```

Résultat exemple :
```
zkone                | Koné Zakaria                  | super_admin
diallo.manager       | Diallo Seydou                 | manager
traore.pdg           | Traoré Aminata                | pdg
```

---

## IMPORTANT — Sécurité

- Ces commandes ne demandent **aucun mot de passe** une fois dans le shell
- C'est pourquoi l'accès SSH au VPS doit être **très bien sécurisé**
  (clé SSH uniquement, pas de mot de passe, port SSH non standard)
- Sur Render, seul toi (propriétaire du compte Render) peux accéder au Shell
- Ne partage **jamais** tes accès SSH ou ton compte Render
