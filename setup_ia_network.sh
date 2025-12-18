#!/bin/bash
# Script pour configurer le réseau entre foxreviews et l'IA

echo "🔧 Configuration du réseau Docker pour connexion IA..."

# Étape 1 : Créer le réseau partagé s'il n'existe pas
if ! docker network ls | grep -q agent_network; then
    echo "📡 Création du réseau agent_network..."
    docker network create agent_network
else
    echo "✅ Le réseau agent_network existe déjà"
fi

# Étape 2 : Connecter le conteneur IA au réseau s'il ne l'est pas déjà
if ! docker network inspect agent_network | grep -q agent_app_local; then
    echo "🔗 Connexion du conteneur IA au réseau..."
    docker network connect agent_network agent_app_local
else
    echo "✅ Le conteneur IA est déjà connecté"
fi

# Étape 3 : Redémarrer les services foxreviews pour qu'ils rejoignent le réseau
echo "🔄 Redémarrage des services foxreviews..."
cd /home/ubuntu/foxreviews/backend
docker compose -f docker-compose.local.yml down
docker compose -f docker-compose.local.yml up -d

echo ""
echo "✅ Configuration terminée!"
echo ""
echo "📡 Test de connexion:"
echo "   docker exec foxreviews_local_django curl -I http://agent_app_local:8000/health"
echo ""
echo "🔗 URL de l'IA depuis Django: http://agent_app_local:8000"
