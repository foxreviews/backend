# Accès externe à la base de données via VPN (WireGuard) — Read/Write

Objectif : permettre à des utilisateurs externes d’accéder à la **même base PostgreSQL de production** (lecture + écriture) **depuis un réseau externe**, **sans entrer dans un conteneur Docker**, tout en évitant d’exposer PostgreSQL publiquement sur Internet.

Approche recommandée :
- Le serveur héberge un VPN **WireGuard**.
- PostgreSQL reste accessible **uniquement** via le réseau VPN.
- On crée des **comptes DB dédiés** (pas le compte applicatif) avec des privilèges contrôlés.

> Note : ce document décrit une mise en place “classique” sur un hôte Linux (Ubuntu/Debian). Si ton serveur est sur un autre OS, adapte les commandes firewall.

---

## 1) Pré-requis

- Accès root/sudo au serveur de production
- Un port UDP disponible pour WireGuard (ex: `51820/udp`)
- Un plan d’adressage VPN (ex: `10.8.0.0/24`)
- Un client WireGuard côté utilisateur externe (Windows/macOS/Linux)

---

## 2) Installer WireGuard sur le serveur

### A. Installation

```bash
sudo apt-get update
sudo apt-get install -y wireguard
```

### B. Génération des clés

```bash
# `umask` est une commande builtin du shell (pas un package à installer).
# Si tu es déjà root, ne mets pas `sudo`.
umask 077
wg genkey | tee /etc/wireguard/server.key | wg pubkey > /etc/wireguard/server.pub
```

---

## 3) Configuration du VPN serveur (`/etc/wireguard/wg0.conf`)

Exemple :

```ini
[Interface]
Address = 10.8.0.1/24
ListenPort = 51820
PrivateKey = <COLLER_CONTENU_/etc/wireguard/server.key>

# Active le forwarding et applique des règles firewall au démarrage
PostUp = sysctl -w net.ipv4.ip_forward=1
PostDown = sysctl -w net.ipv4.ip_forward=0
```

Ajoute ensuite un bloc `[Peer]` par utilisateur externe (voir section 4).

Démarrage :

```bash
sudo systemctl enable wg-quick@wg0
sudo systemctl start wg-quick@wg0
sudo wg show
```

---

## 4) Ajouter un utilisateur VPN (peer)

Sur le serveur (créer une paire de clés pour un peer) :

```bash
umask 077
wg genkey | tee /etc/wireguard/client1.key | wg pubkey > /etc/wireguard/client1.pub
```

Choisis une IP VPN fixe pour ce client (ex: `10.8.0.10/32`) et ajoute à `/etc/wireguard/wg0.conf` :

```ini
[Peer]
PublicKey = <CONTENU_/etc/wireguard/client1.pub>
AllowedIPs = 10.8.0.10/32
```

⚠️ Important : dans `[Peer] PublicKey`, il faut **la clé publique** du client (`client1.pub`), **jamais** la clé privée (`client1.key`).

Si tu as déjà un `client1.key` mais pas le `.pub`, tu peux le dériver ainsi :

```bash
wg pubkey < /etc/wireguard/client1.key | sudo tee /etc/wireguard/client1.pub
```

Recharge la conf :

```bash
sudo systemctl restart wg-quick@wg0
```

### Config côté client (Windows/macOS/Linux)

Le client WireGuard aura un fichier du type :

```ini
[Interface]
PrivateKey = <CONTENU_CLIENT_PRIVKEY>
Address = 10.8.0.10/32
DNS = 1.1.1.1

[Peer]
PublicKey = <CONTENU_/etc/wireguard/server.pub>
Endpoint = <IP_PUBLIQUE_DU_SERVEUR>:51820
AllowedIPs = 10.8.0.0/24
PersistentKeepalive = 25
```

---

## 5) Publier PostgreSQL sur l’hôte (uniquement pour le VPN)

Aujourd’hui, le service `postgres` dans docker-compose **n’expose pas** de port vers l’hôte, donc personne à l’extérieur ne peut joindre `5432`.

Tu as 2 options :

### Option 5.1 (simple) — publier `5432` et restreindre via firewall (recommandé)

- Tu ajoutes un mapping de port `5432:5432`.
- Puis tu **bloques** ce port sur Internet et tu l’autorises **uniquement** depuis le subnet VPN (ex: `10.8.0.0/24`).

### Option 5.2 (plus stricte) — publier uniquement sur une IP locale/VPN

Possible mais plus fragile (l’IP VPN doit exister avant le démarrage Docker, et selon les environnements ça complique l’ordonnancement).

---

## 6) Firewall : autoriser uniquement le VPN

### A. Autoriser WireGuard

- Ouvre `51820/udp` vers le serveur.

Exemples UFW :

```bash
sudo ufw allow 51820/udp
```

### B. Autoriser PostgreSQL uniquement depuis le VPN

```bash
sudo ufw allow from 10.8.0.0/24 to any port 5432 proto tcp
sudo ufw deny 5432/tcp
sudo ufw status verbose
```

> Important : l’ordre des règles compte selon ton firewall. L’idée = allow VPN subnet, deny tout le reste.

---

## 7) Créer un compte PostgreSQL externe (read-write)

Ne partage pas le compte applicatif de production. Crée un compte dédié.

### A. Connexion admin (depuis l’hôte)

Une fois le port publié et le VPN up, tu peux te connecter depuis le serveur via `docker compose exec` (sans ouvrir Internet) :

```bash
docker compose -f docker-compose.production.yml exec postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

### B. SQL : rôle RW “données”

Adapte :
- le nom de DB (`foxreviews`)
- le schema (souvent `public`)
- et surtout le mot de passe

```sql
-- 1) Créer un rôle dédié
CREATE ROLE external_rw LOGIN PASSWORD 'CHANGE_ME_STRONG_PASSWORD';

-- 2) Autoriser la connexion
GRANT CONNECT ON DATABASE foxreviews TO external_rw;

-- 3) Droits sur le schéma
GRANT USAGE ON SCHEMA public TO external_rw;

-- 4) Droits DML sur toutes les tables existantes
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO external_rw;

-- 5) Droits sur les séquences (si INSERT avec serial/identity)
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO external_rw;

-- 6) Par défaut, appliquer ces droits aux futures tables/séquences
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO external_rw;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO external_rw;
```

### C. (Optionnel) Limiter les dégâts

Si tu veux éviter qu’un client externe fasse des opérations trop lourdes :

```sql
ALTER ROLE external_rw SET statement_timeout = '30s';
ALTER ROLE external_rw SET idle_in_transaction_session_timeout = '60s';
```

---

## 8) Paramètres de connexion que l’utilisateur externe doit utiliser

Une fois connecté au VPN WireGuard :

- **Host** : `10.8.0.1` (IP VPN du serveur)
- **Port** : `5432`
- **Database** : `foxreviews`
- **User** : `external_rw`
- **Password** : (celui que tu as défini)

Test côté client :

```bash
psql "postgresql://external_rw:<PASSWORD>@10.8.0.1:5432/foxreviews"
```

---

## 9) Checklist sécurité (à faire avant ouverture)

- Remplacer le mot de passe placeholder dans `.envs/.production/.postgres` (`POSTGRES_PASSWORD=production`) par une valeur forte
- Ne pas utiliser `POSTGRES_USER` applicatif pour l’accès externe
- Firewall : vérifier que `5432/tcp` n’est accessible **que** depuis `10.8.0.0/24`
- Créer 1 compte DB par partenaire (audit + rotation)
- Sauvegardes OK (tu as déjà un volume `production_postgres_data_backups`)

---

## 10) Dépannage rapide

- Vérifier WireGuard :
  - `sudo wg show`
  - Si tu vois `Handshake did not complete`, c'est presque toujours : firewall UDP fermé (OVH et/ou UFW), mauvais endpoint (IP/port), ou clés public/privées inversées.
- Vérifier que WireGuard écoute sur le serveur :
  - `sudo systemctl status wg-quick@wg0`
  - `sudo ss -lunp | grep 51820`
- Vérifier firewall UFW :
  - `sudo ufw status verbose | grep 51820`
  - `sudo ufw allow 51820/udp`
- Vérifier firewall OVH (si activé) :
  - Autoriser `51820/udp` en INBOUND vers l'IP publique du serveur.
- Vérifier la paire de clés :
  - Côté serveur : `[Peer] PublicKey` = clé publique du client
  - Côté client : `[Peer] PublicKey` = clé publique du serveur
- Vérifier que le port 5432 est publié sur l’hôte :
  - `ss -lntp | grep 5432`
- Vérifier depuis un client VPN :
  - `Test-NetConnection 10.8.0.1 -Port 5432` (PowerShell)
- Logs Postgres (container) :
  - `docker compose -f docker-compose.production.yml logs postgres --tail 200`
