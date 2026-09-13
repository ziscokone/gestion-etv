# Document de Déploiement — VPS Test / Pré-prod ETV

> ⚠️ Environnement de **test**, distinct du VPS de production (`gestion-etv.cloud`,
> voir [DEPLOIEMENT_PRODUCTION.md](DEPLOIEMENT_PRODUCTION.md)). Sert à valider une
> mise à jour ou une nouvelle fonctionnalité, ou à s'entraîner sur la procédure de
> déploiement, **sans risque pour les vraies données clients**.
>
> Toutes les valeurs entre `<...>` sont des **placeholders** : à renseigner une fois
> le VPS créé chez Hostinger.

**Application :** Gestion Billetterie ETV (environnement de test)
**Accès :** IP publique uniquement, pas de nom de domaine, pas de HTTPS

---

## 1. Infrastructure

### Hébergeur
- **Fournisseur :** Hostinger
- **Offre :** KVM 1
- **Caractéristiques :** 1 vCPU, 4 Go RAM, 50 Go NVMe

### Serveur
| Composant | Détail |
|---|---|
| OS | Ubuntu 24.04 LTS |
| IP publique | `<IP_VPS_TEST>` |
| Accès | `ssh root@<IP_VPS_TEST>` |
| Domaine | Aucun — accès via `http://<IP_VPS_TEST>/` |
| HTTPS | Aucun (pas de domaine → pas de certificat Let's Encrypt possible) |

---

## 2. Différences volontaires avec la production

Ce VPS reprend la même stack que la production (Nginx + Gunicorn + PostgreSQL +
Redis) pour que les tests soient représentatifs, mais avec des écarts assumés,
liés à l'absence de domaine/HTTPS et au budget d'1 seul cœur :

| Point | Production | Ici (test) | Pourquoi |
|---|---|---|---|
| `DEBUG` | `False` | **`True`** | `config/settings.py` force `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE` et `CSRF_COOKIE_SECURE` à `True` dès que `DEBUG=False`. Sans HTTPS, ça provoquerait une boucle de redirection et empêcherait la connexion (cookies de session refusés en HTTP). `DEBUG=True` est donc **obligatoire** ici, pas juste une option — même logique que le poste gare hors-ligne (voir DEPLOIEMENT_GARE_HORS_LIGNE.md §1.5). |
| Workers Gunicorn | 9 | **3** | Formule `(2 × cœurs) + 1` appliquée à 1 vCPU au lieu de 4. |
| SSL / Certbot | Let's Encrypt | Aucun | Pas de nom de domaine sur ce VPS. |
| Backup automatique | Bot Telegram, tous les soirs | Aucun (optionnel) | Données de test, non critiques — voir §8 si tu veux quand même l'activer. |
| Pare-feu UFW | 22, 80, 443 | **22, 80** | Pas de port 443 puisqu'il n'y a pas de HTTPS. |

**Important :** parce que `DEBUG=True` affiche la stack trace complète au moindre
bug (utile en test, dangereux en public), et qu'il n'y a pas de HTTPS, **ne jamais
y mettre de vraies données clients/billets réels**. Ce VPS est un bac à sable.

---

## 3. Stack technique

| Composant | Rôle |
|---|---|
| Python 3.12 + venv | Runtime |
| Django 5.2 | Application |
| Gunicorn (3 workers) | Serveur WSGI |
| Nginx | Reverse proxy + fichiers statiques (HTTP uniquement) |
| PostgreSQL | Base de données |
| Redis | Cache / rate limiting |
| UFW | Pare-feu |

---

## 4. Structure des fichiers sur le VPS

```
/var/www/etv-test/                 ← Racine du projet (nom différent de la prod, exprès)
├── venv/
├── config/
├── apps/
├── static/
├── staticfiles/
├── media/
├── manage.py
├── requirements.txt
├── .env                          ← NE PAS VERSIONNER
└── etv-test.sock                 ← Socket Unix Gunicorn ↔ Nginx

/etc/nginx/sites-available/etv-test   ← Config Nginx
/etc/systemd/system/etv-test.service  ← Service Gunicorn systemd
```

---

## 5. Installation complète (première fois)

### 5.1 Connexion et mise à jour du système

```bash
ssh root@<IP_VPS_TEST>
apt update && apt upgrade -y
```

### 5.2 Paquets système

```bash
apt install -y python3 python3-venv python3-pip nginx postgresql postgresql-contrib redis-server git ufw
```

### 5.3 Pare-feu

```bash
ufw allow 22
ufw allow 80
ufw enable
```

### 5.4 Base de données PostgreSQL

```bash
sudo -u postgres psql -c "CREATE DATABASE etv_test_db;"
sudo -u postgres psql -c "CREATE USER etv_test_user WITH PASSWORD '<MOT_DE_PASSE_DB_TEST>';"
sudo -u postgres psql -c "ALTER ROLE etv_test_user SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE etv_test_db TO etv_test_user;"
sudo -u postgres psql -c "ALTER DATABASE etv_test_db OWNER TO etv_test_user;"
```

### 5.5 Récupération du code

```bash
mkdir -p /var/www/etv-test
cd /var/www/etv-test
git clone <URL_DEPOT_GITHUB_ETV> .
```

### 5.6 Environnement virtuel et dépendances

```bash
cd /var/www/etv-test
python3 -m venv venv
venv/bin/pip install --upgrade pip
venv/bin/pip install -r requirements.txt
venv/bin/pip install gunicorn
```

### 5.7 Fichier `.env`

Générer une clé secrète dédiée à ce VPS (ne jamais réutiliser celle de la prod) :

```bash
venv/bin/python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Créer `/var/www/etv-test/.env` :

```env
SECRET_KEY=<coller-la-valeur-generee-ci-dessus>
DEBUG=True
ALLOWED_HOSTS=<IP_VPS_TEST>
ADMIN_URL=etv-admin-panel/
DB_NAME=etv_test_db
DB_USER=etv_test_user
DB_PASSWORD=<MOT_DE_PASSE_DB_TEST>
DB_HOST=localhost
DB_PORT=5432
CACHE_URL=redis://localhost:6379/1
```

### 5.8 Migrations, fichiers statiques, superuser

```bash
cd /var/www/etv-test
venv/bin/python manage.py migrate
venv/bin/python manage.py collectstatic --noinput
venv/bin/python manage.py createsuperuser
```

### 5.9 Service systemd — `/etc/systemd/system/etv-test.service`

```ini
[Unit]
Description=Gunicorn ETV Billetterie (test/pre-prod)
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/var/www/etv-test
EnvironmentFile=/var/www/etv-test/.env
ExecStart=/var/www/etv-test/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/var/www/etv-test/etv-test.sock \
    config.wsgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable etv-test
systemctl start etv-test
systemctl status etv-test
```

### 5.10 Configuration Nginx — `/etc/nginx/sites-available/etv-test`

```nginx
server {
    listen 80;
    server_name <IP_VPS_TEST>;

    client_max_body_size 12M;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        alias /var/www/etv-test/staticfiles/;
    }

    location /media/ {
        alias /var/www/etv-test/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/etv-test/etv-test.sock;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/etv-test /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

### 5.11 Vérification

Ouvrir `http://<IP_VPS_TEST>/` dans un navigateur — l'écran de connexion doit
s'afficher. Admin Django sur `http://<IP_VPS_TEST>/etv-admin-panel/`.

---

## 6. Configurer une gare de test

Une fois connecté avec le compte superuser créé en §5.8 :

1. Aller sur `http://<IP_VPS_TEST>/etv-admin-panel/`.
2. Dans la section **Gares**, créer une gare de test (nom, code, ville — n'importe
   quelle valeur, ce sont des données jetables sur ce VPS).
3. Créer ensuite les données liées nécessaires aux tests voulus (lignes, tarifs,
   véhicules, personnel...) selon ce qui doit être testé.
4. Si le test porte sur la synchronisation hors-ligne (`apps.sync`), générer un
   jeton pour cette gare :
   ```bash
   cd /var/www/etv-test
   venv/bin/python manage.py create_gare_token <CODE_GARE>
   ```
   et suivre DEPLOIEMENT_GARE_HORS_LIGNE.md en pointant `SYNC_CENTRAL_URL` du
   poste gare vers `http://<IP_VPS_TEST>` (et non `https://gestion-etv.cloud`).

---

## 7. Procédure de mise à jour du code

Identique à la production (voir DEPLOIEMENT_PRODUCTION.md §11), adaptée au chemin
et au service de ce VPS :

```bash
cd /var/www/etv-test && \
git checkout . && \
git pull origin main && \
venv/bin/pip install -r requirements.txt && \
venv/bin/python manage.py migrate && \
venv/bin/python manage.py collectstatic --noinput && \
systemctl restart etv-test
```

---

## 8. Backup (optionnel)

Les données de ce VPS sont jetables par nature. Si un test long doit néanmoins
être protégé d'une perte accidentelle, un dump manuel suffit :

```bash
PGPASSWORD='<MOT_DE_PASSE_DB_TEST>' pg_dump -h localhost -U etv_test_user etv_test_db | gzip > /root/etv_test_$(date +%Y-%m-%d_%H-%M).sql.gz
```

Pas d'automatisation Telegram ici (voir DEPLOIEMENT_PRODUCTION.md §8 si ce VPS
devait un jour évoluer vers un usage plus permanent).

---

## 9. Réinitialiser complètement l'environnement de test

Utile pour repartir d'une base propre entre deux campagnes de test :

```bash
systemctl stop etv-test
sudo -u postgres psql -c "DROP DATABASE etv_test_db;"
sudo -u postgres psql -c "CREATE DATABASE etv_test_db OWNER etv_test_user;"
cd /var/www/etv-test
venv/bin/python manage.py migrate
venv/bin/python manage.py createsuperuser
systemctl start etv-test
```

---

## 10. Commandes de gestion courantes

```bash
systemctl status etv-test         # État Gunicorn
systemctl restart etv-test        # Redémarrer Gunicorn
journalctl -u etv-test -f         # Logs Gunicorn en temps réel
systemctl status nginx
journalctl -u nginx -f
```

---

## 11. Checklist avant de créer le VPS chez Hostinger

- [ ] Offre **KVM 1** (1 vCPU / 4 Go RAM / 50 Go NVMe), datacenter proche de tes
      utilisateurs de test.
- [ ] OS : **Ubuntu 24.04 LTS**.
- [ ] Noter l'IP publique et le mot de passe root dès la création.
- [ ] Revenir ici avec l'IP pour lancer la Partie 5.

---

*Document préparé le 09/09/2026 — à compléter avec l'IP réelle une fois le VPS créé chez Hostinger.*
