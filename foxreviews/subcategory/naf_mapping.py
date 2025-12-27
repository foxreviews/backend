"""
Mapping COMPLET entre codes NAF (INSEE) et SousCategories FOX-Reviews.

Ce fichier contient TOUS les 732 codes NAF de la nomenclature INSEE.
Source: https://www.insee.fr/fr/information/2406147

Structure:
    NAF_TO_SUBCATEGORY = {
        "code_naf": "slug_sous_categorie",
        ...
    }

Usage:
    from foxreviews.subcategory.naf_mapping import get_subcategory_from_naf

    sous_cat = get_subcategory_from_naf("43.22A")  # Returns SousCategorie or None
"""

import re

from django.core.cache import cache

# =============================================================================
# MAPPING NAF COMPLET → SOUS-CATÉGORIES
# =============================================================================
# Tous les 732 codes NAF de la nomenclature INSEE Rev. 2
# Organisé par Section (A-U)
# =============================================================================

NAF_TO_SUBCATEGORY = {
    # =========================================================================
    # SECTION A - AGRICULTURE, SYLVICULTURE ET PÊCHE (01-03)
    # =========================================================================
    # Division 01 - Culture et production animale
    "01.11Z": "agriculteur",  # Culture de céréales (sauf riz)
    "01.12Z": "agriculteur",  # Culture du riz
    "01.13Z": "maraicher",  # Culture de légumes, melons, racines et tubercules
    "01.14Z": "agriculteur",  # Culture de la canne à sucre
    "01.15Z": "agriculteur",  # Culture du tabac
    "01.16Z": "agriculteur",  # Culture de plantes à fibres
    "01.19Z": "agriculteur",  # Autres cultures non permanentes
    "01.21Z": "viticulteur",  # Culture de la vigne
    "01.22Z": "agriculteur",  # Culture de fruits tropicaux et subtropicaux
    "01.23Z": "agriculteur",  # Culture d'agrumes
    "01.24Z": "agriculteur",  # Culture de fruits à pépins et à noyau
    "01.25Z": "agriculteur",  # Culture d'autres fruits d'arbres ou d'arbustes
    "01.26Z": "agriculteur",  # Culture de fruits oléagineux
    "01.27Z": "agriculteur",  # Culture de plantes à boissons
    "01.28Z": "agriculteur",  # Culture de plantes à épices, aromatiques
    "01.29Z": "agriculteur",  # Autres cultures permanentes
    "01.30Z": "jardinier",  # Reproduction de plantes
    "01.41Z": "eleveur",  # Élevage de vaches laitières
    "01.42Z": "eleveur",  # Élevage d'autres bovins et de buffles
    "01.43Z": "eleveur",  # Élevage de chevaux et d'autres équidés
    "01.44Z": "eleveur",  # Élevage de chameaux et d'autres camélidés
    "01.45Z": "eleveur",  # Élevage d'ovins et de caprins
    "01.46Z": "eleveur",  # Élevage de porcins
    "01.47Z": "aviculteur",  # Élevage de volailles
    "01.49Z": "eleveur",  # Élevage d'autres animaux
    "01.50Z": "agriculteur",  # Culture et élevage associés
    "01.61Z": "jardinier",  # Activités de soutien aux cultures
    "01.62Z": "eleveur",  # Activités de soutien à la production animale
    "01.63Z": "agriculteur",  # Traitement primaire des récoltes
    "01.64Z": "agriculteur",  # Traitement des semences
    "01.70Z": "autre-activite",  # Chasse, piégeage et services annexes

    # Division 02 - Sylviculture et exploitation forestière
    "02.10Z": "elagueur",  # Sylviculture et autres activités forestières
    "02.20Z": "elagueur",  # Exploitation forestière
    "02.30Z": "elagueur",  # Récolte de produits forestiers non ligneux
    "02.40Z": "elagueur",  # Services de soutien à l'exploitation forestière

    # Division 03 - Pêche et aquaculture
    "03.11Z": "autre-activite",  # Pêche en mer
    "03.12Z": "autre-activite",  # Pêche en eau douce
    "03.21Z": "autre-activite",  # Aquaculture en mer
    "03.22Z": "autre-activite",  # Aquaculture en eau douce

    # =========================================================================
    # SECTION B - INDUSTRIES EXTRACTIVES (05-09)
    # =========================================================================
    "05.10Z": "autre-activite",  # Extraction de houille
    "05.20Z": "autre-activite",  # Extraction de lignite
    "06.10Z": "autre-activite",  # Extraction de pétrole brut
    "06.20Z": "autre-activite",  # Extraction de gaz naturel
    "07.10Z": "autre-activite",  # Extraction de minerais de fer
    "07.21Z": "autre-activite",  # Extraction de minerais d'uranium et de thorium
    "07.29Z": "autre-activite",  # Extraction d'autres minerais de métaux non ferreux
    "08.11Z": "autre-activite",  # Extraction de pierres ornementales et de construction
    "08.12Z": "autre-activite",  # Exploitation de gravières et sablières
    "08.91Z": "autre-activite",  # Extraction des minéraux chimiques et d'engrais
    "08.92Z": "autre-activite",  # Extraction de tourbe
    "08.93Z": "autre-activite",  # Production de sel
    "08.99Z": "autre-activite",  # Autres activités extractives n.c.a.
    "09.10Z": "autre-activite",  # Activités de soutien à l'extraction d'hydrocarbures
    "09.90Z": "autre-activite",  # Activités de soutien aux autres industries extractives

    # =========================================================================
    # SECTION C - INDUSTRIE MANUFACTURIÈRE (10-33)
    # =========================================================================
    # Division 10 - Industries alimentaires
    "10.11Z": "autre-activite",  # Transformation et conservation de la viande de boucherie
    "10.12Z": "autre-activite",  # Transformation et conservation de la viande de volaille
    "10.13A": "autre-activite",  # Préparation industrielle de produits à base de viande
    "10.13B": "autre-activite",  # Charcuterie
    "10.20Z": "autre-activite",  # Transformation et conservation de poisson
    "10.31Z": "autre-activite",  # Transformation et conservation de pommes de terre
    "10.32Z": "autre-activite",  # Préparation de jus de fruits et légumes
    "10.39A": "autre-activite",  # Autre transformation et conservation de légumes
    "10.39B": "autre-activite",  # Transformation et conservation de fruits
    "10.41A": "autre-activite",  # Fabrication d'huiles et graisses brutes
    "10.41B": "autre-activite",  # Fabrication d'huiles et graisses raffinées
    "10.42Z": "autre-activite",  # Fabrication de margarine et graisses comestibles
    "10.51A": "autre-activite",  # Fabrication de lait liquide et de produits frais
    "10.51B": "autre-activite",  # Fabrication de beurre
    "10.51C": "autre-activite",  # Fabrication de fromage
    "10.51D": "autre-activite",  # Fabrication d'autres produits laitiers
    "10.52Z": "autre-activite",  # Fabrication de glaces et sorbets
    "10.61A": "autre-activite",  # Meunerie
    "10.61B": "autre-activite",  # Autres activités du travail des grains
    "10.62Z": "autre-activite",  # Fabrication de produits amylacés
    "10.71A": "boulangerie-patisserie",  # Fabrication industrielle de pain
    "10.71B": "boulangerie-patisserie",  # Cuisson de produits de boulangerie
    "10.71C": "boulangerie-patisserie",  # Boulangerie et boulangerie-pâtisserie
    "10.71D": "boulangerie-patisserie",  # Pâtisserie
    "10.72Z": "boulangerie-patisserie",  # Fabrication de biscuits, biscottes et pâtisseries
    "10.73Z": "autre-activite",  # Fabrication de pâtes alimentaires
    "10.81Z": "autre-activite",  # Fabrication de sucre
    "10.82Z": "autre-activite",  # Fabrication de cacao, chocolat et de produits de confiserie
    "10.83Z": "autre-activite",  # Transformation du thé et du café
    "10.84Z": "autre-activite",  # Fabrication de condiments et assaisonnements
    "10.85Z": "traiteur",  # Fabrication de plats préparés
    "10.86Z": "autre-activite",  # Fabrication d'aliments homogénéisés et diététiques
    "10.89Z": "autre-activite",  # Fabrication d'autres produits alimentaires n.c.a.
    "10.91Z": "autre-activite",  # Fabrication d'aliments pour animaux de ferme
    "10.92Z": "autre-activite",  # Fabrication d'aliments pour animaux de compagnie

    # Division 11 - Fabrication de boissons
    "11.01Z": "autre-activite",  # Production de boissons alcooliques distillées
    "11.02A": "viticulteur",  # Fabrication de vins effervescents
    "11.02B": "viticulteur",  # Vinification
    "11.03Z": "autre-activite",  # Fabrication de cidre et de vins de fruits
    "11.04Z": "autre-activite",  # Production d'autres boissons fermentées non distillées
    "11.05Z": "autre-activite",  # Fabrication de bière
    "11.06Z": "autre-activite",  # Fabrication de malt
    "11.07A": "autre-activite",  # Industrie des eaux de table
    "11.07B": "autre-activite",  # Production de boissons rafraîchissantes

    # Division 12 - Fabrication de produits à base de tabac
    "12.00Z": "autre-activite",  # Fabrication de produits à base de tabac

    # Division 13 - Fabrication de textiles
    "13.10Z": "autre-activite",  # Préparation de fibres textiles et filature
    "13.20Z": "autre-activite",  # Tissage
    "13.30Z": "autre-activite",  # Ennoblissement textile
    "13.91Z": "autre-activite",  # Fabrication d'étoffes à mailles
    "13.92Z": "autre-activite",  # Fabrication d'articles textiles, sauf habillement
    "13.93Z": "autre-activite",  # Fabrication de tapis et moquettes
    "13.94Z": "autre-activite",  # Fabrication de ficelles, cordes et filets
    "13.95Z": "autre-activite",  # Fabrication de non-tissés, sauf habillement
    "13.96Z": "autre-activite",  # Fabrication d'autres textiles techniques et industriels
    "13.99Z": "autre-activite",  # Fabrication d'autres textiles n.c.a.

    # Division 14 - Industrie de l'habillement
    "14.11Z": "autre-activite",  # Fabrication de vêtements en cuir
    "14.12Z": "autre-activite",  # Fabrication de vêtements de travail
    "14.13Z": "autre-activite",  # Fabrication de vêtements de dessus
    "14.14Z": "autre-activite",  # Fabrication de vêtements de dessous
    "14.19Z": "autre-activite",  # Fabrication d'autres vêtements et accessoires
    "14.20Z": "autre-activite",  # Fabrication d'articles en fourrure
    "14.31Z": "autre-activite",  # Fabrication d'articles chaussants à mailles
    "14.39Z": "autre-activite",  # Fabrication d'autres articles à mailles

    # Division 15 - Industrie du cuir et de la chaussure
    "15.11Z": "autre-activite",  # Apprêt et tannage des cuirs
    "15.12Z": "autre-activite",  # Fabrication d'articles de voyage, de maroquinerie
    "15.20Z": "autre-activite",  # Fabrication de chaussures

    # Division 16 - Travail du bois
    "16.10A": "menuisier",  # Sciage et rabotage du bois, hors imprégnation
    "16.10B": "menuisier",  # Imprégnation du bois
    "16.21Z": "menuisier",  # Fabrication de placage et de panneaux de bois
    "16.22Z": "menuisier",  # Fabrication de parquets assemblés
    "16.23Z": "menuisier-charpentier",  # Fabrication de charpentes et d'autres menuiseries
    "16.24Z": "menuisier",  # Fabrication d'emballages en bois
    "16.29Z": "menuisier",  # Fabrication d'objets divers en bois

    # Division 17 - Industrie du papier et du carton
    "17.11Z": "autre-activite",  # Fabrication de pâte à papier
    "17.12Z": "autre-activite",  # Fabrication de papier et de carton
    "17.21A": "autre-activite",  # Fabrication de carton ondulé
    "17.21B": "autre-activite",  # Fabrication de cartonnages
    "17.21C": "autre-activite",  # Fabrication d'emballages en papier
    "17.22Z": "autre-activite",  # Fabrication d'articles en papier à usage sanitaire
    "17.23Z": "autre-activite",  # Fabrication d'articles de papeterie
    "17.24Z": "autre-activite",  # Fabrication de papiers peints
    "17.29Z": "autre-activite",  # Fabrication d'autres articles en papier ou en carton

    # Division 18 - Imprimerie et reproduction d'enregistrements
    "18.11Z": "autre-activite",  # Imprimerie de journaux
    "18.12Z": "autre-activite",  # Autre imprimerie (labeur)
    "18.13Z": "autre-activite",  # Activités de pré-presse
    "18.14Z": "autre-activite",  # Reliure et activités connexes
    "18.20Z": "autre-activite",  # Reproduction d'enregistrements

    # Division 19 - Cokéfaction et raffinage
    "19.10Z": "autre-activite",  # Cokéfaction
    "19.20Z": "autre-activite",  # Raffinage du pétrole

    # Division 20 - Industrie chimique
    "20.11Z": "autre-activite",  # Fabrication de gaz industriels
    "20.12Z": "autre-activite",  # Fabrication de colorants et de pigments
    "20.13A": "autre-activite",  # Enrichissement et retraitement de matières nucléaires
    "20.13B": "autre-activite",  # Fabrication d'autres produits chimiques inorganiques
    "20.14Z": "autre-activite",  # Fabrication d'autres produits chimiques organiques
    "20.15Z": "autre-activite",  # Fabrication de produits azotés et d'engrais
    "20.16Z": "autre-activite",  # Fabrication de matières plastiques de base
    "20.17Z": "autre-activite",  # Fabrication de caoutchouc synthétique
    "20.20Z": "autre-activite",  # Fabrication de pesticides et d'autres produits agrochimiques
    "20.30Z": "autre-activite",  # Fabrication de peintures, vernis, encres et mastics
    "20.41Z": "autre-activite",  # Fabrication de savons, détergents et produits d'entretien
    "20.42Z": "autre-activite",  # Fabrication de parfums et de produits de toilette
    "20.51Z": "autre-activite",  # Fabrication de produits explosifs
    "20.52Z": "autre-activite",  # Fabrication de colles
    "20.53Z": "autre-activite",  # Fabrication d'huiles essentielles
    "20.59Z": "autre-activite",  # Fabrication d'autres produits chimiques n.c.a.
    "20.60Z": "autre-activite",  # Fabrication de fibres artificielles ou synthétiques

    # Division 21 - Industrie pharmaceutique
    "21.10Z": "autre-activite",  # Fabrication de produits pharmaceutiques de base
    "21.20Z": "autre-activite",  # Fabrication de préparations pharmaceutiques

    # Division 22 - Fabrication de produits en caoutchouc et en plastique
    "22.11Z": "autre-activite",  # Fabrication et rechapage de pneumatiques
    "22.19Z": "autre-activite",  # Fabrication d'autres articles en caoutchouc
    "22.21Z": "autre-activite",  # Fabrication de plaques, feuilles, tubes en plastique
    "22.22Z": "autre-activite",  # Fabrication d'emballages en matières plastiques
    "22.23Z": "autre-activite",  # Fabrication d'éléments en plastique pour la construction
    "22.29A": "autre-activite",  # Fabrication de pièces techniques à base de plastique
    "22.29B": "autre-activite",  # Fabrication de produits de consommation en plastique

    # Division 23 - Fabrication d'autres produits minéraux non métalliques
    "23.11Z": "autre-activite",  # Fabrication de verre plat
    "23.12Z": "autre-activite",  # Façonnage et transformation du verre plat
    "23.13Z": "autre-activite",  # Fabrication de verre creux
    "23.14Z": "autre-activite",  # Fabrication de fibres de verre
    "23.19Z": "autre-activite",  # Fabrication et façonnage d'autres articles en verre
    "23.20Z": "autre-activite",  # Fabrication de produits réfractaires
    "23.31Z": "carreleur",  # Fabrication de carreaux en céramique
    "23.32Z": "autre-activite",  # Fabrication de briques, tuiles et produits de construction
    "23.41Z": "autre-activite",  # Fabrication d'articles céramiques à usage domestique
    "23.42Z": "autre-activite",  # Fabrication d'appareils sanitaires en céramique
    "23.43Z": "autre-activite",  # Fabrication d'isolateurs et pièces isolantes en céramique
    "23.44Z": "autre-activite",  # Fabrication d'autres produits céramiques à usage technique
    "23.49Z": "autre-activite",  # Fabrication d'autres produits céramiques
    "23.51Z": "autre-activite",  # Fabrication de ciment
    "23.52Z": "autre-activite",  # Fabrication de chite et plâtre
    "23.61Z": "macon",  # Fabrication d'éléments en béton pour la construction
    "23.62Z": "macon",  # Fabrication d'éléments en plâtre pour la construction
    "23.63Z": "macon",  # Fabrication de béton prêt à l'emploi
    "23.64Z": "autre-activite",  # Fabrication de mortiers et bétons secs
    "23.65Z": "autre-activite",  # Fabrication d'ouvrages en fibre-ciment
    "23.69Z": "autre-activite",  # Fabrication d'autres ouvrages en béton, en ciment ou en plâtre
    "23.70Z": "autre-activite",  # Taille, façonnage et finissage de pierres
    "23.91Z": "autre-activite",  # Fabrication de produits abrasifs
    "23.99Z": "autre-activite",  # Fabrication d'autres produits minéraux non métalliques

    # Division 24 - Métallurgie
    "24.10Z": "autre-activite",  # Sidérurgie
    "24.20Z": "autre-activite",  # Fabrication de tubes, tuyaux, profilés et accessoires en acier
    "24.31Z": "autre-activite",  # Étirage à froid de barres
    "24.32Z": "autre-activite",  # Laminage à froid de feuillards
    "24.33Z": "autre-activite",  # Profilage à froid par formage ou pliage
    "24.34Z": "autre-activite",  # Tréfilage à froid
    "24.41Z": "autre-activite",  # Production de métaux précieux
    "24.42Z": "autre-activite",  # Métallurgie de l'aluminium
    "24.43Z": "autre-activite",  # Métallurgie du plomb, du zinc ou de l'étain
    "24.44Z": "autre-activite",  # Métallurgie du cuivre
    "24.45Z": "autre-activite",  # Métallurgie des autres métaux non ferreux
    "24.46Z": "autre-activite",  # Élaboration et transformation de matières nucléaires
    "24.51Z": "autre-activite",  # Fonderie de fonte
    "24.52Z": "autre-activite",  # Fonderie d'acier
    "24.53Z": "autre-activite",  # Fonderie de métaux légers
    "24.54Z": "autre-activite",  # Fonderie d'autres métaux non ferreux

    # Division 25 - Fabrication de produits métalliques
    "25.11Z": "autre-activite",  # Fabrication de structures métalliques et de parties de structures
    "25.12Z": "menuisier",  # Fabrication de portes et fenêtres en métal
    "25.21Z": "chauffagiste",  # Fabrication de radiateurs et de chaudières
    "25.29Z": "autre-activite",  # Fabrication d'autres réservoirs, citernes et conteneurs
    "25.30Z": "autre-activite",  # Fabrication de générateurs de vapeur
    "25.40Z": "autre-activite",  # Fabrication d'armes et de munitions
    "25.50A": "autre-activite",  # Forge, estampage, matriçage; métallurgie des poudres
    "25.50B": "autre-activite",  # Découpage, emboutissage
    "25.61Z": "autre-activite",  # Traitement et revêtement des métaux
    "25.62A": "autre-activite",  # Décolletage
    "25.62B": "autre-activite",  # Mécanique industrielle
    "25.71Z": "autre-activite",  # Fabrication de coutellerie
    "25.72Z": "serrurier",  # Fabrication de serrures et de ferrures
    "25.73A": "autre-activite",  # Fabrication de moules et modèles
    "25.73B": "autre-activite",  # Fabrication d'autres outillages
    "25.91Z": "autre-activite",  # Fabrication de fûts et emballages métalliques similaires
    "25.92Z": "autre-activite",  # Fabrication d'emballages métalliques légers
    "25.93Z": "autre-activite",  # Fabrication d'articles en fils métalliques
    "25.94Z": "autre-activite",  # Fabrication de vis et de boulons
    "25.99A": "autre-activite",  # Fabrication d'articles métalliques ménagers
    "25.99B": "autre-activite",  # Fabrication d'autres articles métalliques

    # Division 26 - Fabrication de produits informatiques, électroniques et optiques
    "26.11Z": "autre-activite",  # Fabrication de composants électroniques
    "26.12Z": "autre-activite",  # Fabrication de cartes électroniques assemblées
    "26.20Z": "autre-activite",  # Fabrication d'ordinateurs et d'équipements périphériques
    "26.30Z": "autre-activite",  # Fabrication d'équipements de communication
    "26.40Z": "autre-activite",  # Fabrication de produits électroniques grand public
    "26.51A": "autre-activite",  # Fabrication d'équipements d'aide à la navigation
    "26.51B": "autre-activite",  # Fabrication d'instrumentation scientifique et technique
    "26.52Z": "autre-activite",  # Horlogerie
    "26.60Z": "autre-activite",  # Fabrication d'équipements d'irradiation médicale
    "26.70Z": "opticien",  # Fabrication de matériels optique et photographique
    "26.80Z": "autre-activite",  # Fabrication de supports magnétiques et optiques

    # Division 27 - Fabrication d'équipements électriques
    "27.11Z": "autre-activite",  # Fabrication de moteurs, génératrices et transformateurs
    "27.12Z": "autre-activite",  # Fabrication de matériel de distribution et de commande
    "27.20Z": "autre-activite",  # Fabrication de piles et d'accumulateurs électriques
    "27.31Z": "autre-activite",  # Fabrication de câbles de fibres optiques
    "27.32Z": "electricien",  # Fabrication d'autres fils et câbles électroniques
    "27.33Z": "electricien",  # Fabrication de matériel d'installation électrique
    "27.40Z": "autre-activite",  # Fabrication d'appareils d'éclairage électrique
    "27.51Z": "autre-activite",  # Fabrication d'appareils électroménagers
    "27.52Z": "autre-activite",  # Fabrication d'appareils ménagers non électriques
    "27.90Z": "autre-activite",  # Fabrication d'autres matériels électriques

    # Division 28 - Fabrication de machines et équipements n.c.a.
    "28.11Z": "autre-activite",  # Fabrication de moteurs et turbines
    "28.12Z": "autre-activite",  # Fabrication d'équipements hydrauliques et pneumatiques
    "28.13Z": "autre-activite",  # Fabrication d'autres pompes et compresseurs
    "28.14Z": "autre-activite",  # Fabrication d'autres articles de robinetterie
    "28.15Z": "autre-activite",  # Fabrication d'engrenages et d'organes mécaniques
    "28.21Z": "autre-activite",  # Fabrication de fours et brûleurs
    "28.22Z": "autre-activite",  # Fabrication de matériel de levage et de manutention
    "28.23Z": "autre-activite",  # Fabrication de machines et d'équipements de bureau
    "28.24Z": "autre-activite",  # Fabrication d'outillage portatif à moteur
    "28.25Z": "climaticien",  # Fabrication d'équipements aérauliques et frigorifiques
    "28.29A": "autre-activite",  # Fabrication d'équipements d'emballage
    "28.29B": "autre-activite",  # Fabrication d'autres machines d'usage général
    "28.30Z": "agriculteur",  # Fabrication de machines agricoles et forestières
    "28.41Z": "autre-activite",  # Fabrication de machines-outils pour le travail des métaux
    "28.49Z": "autre-activite",  # Fabrication d'autres machines-outils
    "28.91Z": "autre-activite",  # Fabrication de machines pour la métallurgie
    "28.92Z": "autre-activite",  # Fabrication de machines pour l'extraction ou la construction
    "28.93Z": "autre-activite",  # Fabrication de machines pour l'industrie agro-alimentaire
    "28.94Z": "autre-activite",  # Fabrication de machines pour les industries textiles
    "28.95Z": "autre-activite",  # Fabrication de machines pour les industries du papier
    "28.96Z": "autre-activite",  # Fabrication de machines pour le travail du caoutchouc
    "28.99A": "autre-activite",  # Fabrication de machines d'imprimerie
    "28.99B": "autre-activite",  # Fabrication d'autres machines spécialisées

    # Division 29 - Industrie automobile
    "29.10Z": "garage-automobile",  # Construction de véhicules automobiles
    "29.20Z": "garage-automobile",  # Fabrication de carrosseries et remorques
    "29.31Z": "garage-automobile",  # Fabrication d'équipements électriques et électroniques
    "29.32Z": "garage-automobile",  # Fabrication d'autres équipements automobiles

    # Division 30 - Fabrication d'autres matériels de transport
    "30.11Z": "autre-activite",  # Construction de navires et de structures flottantes
    "30.12Z": "autre-activite",  # Construction de bateaux de plaisance
    "30.20Z": "autre-activite",  # Construction de locomotives et d'autre matériel ferroviaire
    "30.30Z": "autre-activite",  # Construction aéronautique et spatiale
    "30.40Z": "autre-activite",  # Construction de véhicules militaires de combat
    "30.91Z": "autre-activite",  # Fabrication de motocycles
    "30.92Z": "autre-activite",  # Fabrication de bicyclettes et de véhicules pour invalides
    "30.99Z": "autre-activite",  # Fabrication d'autres équipements de transport n.c.a.

    # Division 31 - Fabrication de meubles
    "31.01Z": "menuisier",  # Fabrication de meubles de bureau et de magasin
    "31.02Z": "menuisier",  # Fabrication de meubles de cuisine
    "31.03Z": "autre-activite",  # Fabrication de matelas
    "31.09A": "menuisier",  # Fabrication de sièges d'ameublement d'intérieur
    "31.09B": "menuisier",  # Fabrication d'autres meubles et industries connexes

    # Division 32 - Autres industries manufacturières
    "32.11Z": "autre-activite",  # Frappe de monnaie
    "32.12Z": "autre-activite",  # Fabrication d'articles de joaillerie et bijouterie
    "32.13Z": "autre-activite",  # Fabrication d'articles de bijouterie fantaisie
    "32.20Z": "autre-activite",  # Fabrication d'instruments de musique
    "32.30Z": "autre-activite",  # Fabrication d'articles de sport
    "32.40Z": "autre-activite",  # Fabrication de jeux et jouets
    "32.50A": "autre-activite",  # Fabrication de matériel médico-chirurgical et dentaire
    "32.50B": "opticien",  # Fabrication de lunettes
    "32.91Z": "autre-activite",  # Fabrication d'articles de brosserie
    "32.99Z": "autre-activite",  # Autres activités manufacturières n.c.a.

    # Division 33 - Réparation et installation de machines et d'équipements
    "33.11Z": "autre-activite",  # Réparation d'ouvrages en métaux
    "33.12Z": "autre-activite",  # Réparation de machines et équipements mécaniques
    "33.13Z": "autre-activite",  # Réparation de matériels électroniques et optiques
    "33.14Z": "electricien",  # Réparation d'équipements électriques
    "33.15Z": "autre-activite",  # Réparation et maintenance navale
    "33.16Z": "autre-activite",  # Réparation et maintenance d'aéronefs et d'engins spatiaux
    "33.17Z": "autre-activite",  # Réparation et maintenance d'autres équipements de transport
    "33.19Z": "autre-activite",  # Réparation d'autres équipements
    "33.20A": "autre-activite",  # Installation de structures métalliques
    "33.20B": "autre-activite",  # Installation de machines et équipements mécaniques
    "33.20C": "electricien",  # Conception d'ensemble et assemblage sur site industriel
    "33.20D": "autre-activite",  # Installation d'équipements électriques, de matériels électroniques

    # =========================================================================
    # SECTION D - PRODUCTION ET DISTRIBUTION D'ÉLECTRICITÉ, DE GAZ, DE VAPEUR
    # =========================================================================
    "35.11Z": "producteur-electricite",  # Production d'électricité
    "35.12Z": "autre-activite",  # Transport d'électricité
    "35.13Z": "autre-activite",  # Distribution d'électricité
    "35.14Z": "autre-activite",  # Commerce d'électricité
    "35.21Z": "autre-activite",  # Production de combustibles gazeux
    "35.22Z": "autre-activite",  # Distribution de combustibles gazeux par conduites
    "35.23Z": "autre-activite",  # Commerce de combustibles gazeux par conduites
    "35.30Z": "autre-activite",  # Production et distribution de vapeur et d'air conditionné

    # =========================================================================
    # SECTION E - PRODUCTION ET DISTRIBUTION D'EAU; ASSAINISSEMENT, GESTION DES DÉCHETS
    # =========================================================================
    "36.00Z": "autre-activite",  # Captage, traitement et distribution d'eau
    "37.00Z": "autre-activite",  # Collecte et traitement des eaux usées
    "38.11Z": "autre-activite",  # Collecte des déchets non dangereux
    "38.12Z": "autre-activite",  # Collecte des déchets dangereux
    "38.21Z": "autre-activite",  # Traitement et élimination des déchets non dangereux
    "38.22Z": "autre-activite",  # Traitement et élimination des déchets dangereux
    "38.31Z": "autre-activite",  # Démantèlement d'épaves
    "38.32Z": "autre-activite",  # Récupération de déchets triés
    "39.00Z": "autre-activite",  # Dépollution et autres services de gestion des déchets

    # =========================================================================
    # SECTION F - CONSTRUCTION (41-43)
    # =========================================================================
    # Division 41 - Construction de bâtiments
    "41.10A": "macon",  # Développement de projets immobiliers sans construction
    "41.10B": "macon",  # Développement de projets immobiliers avec construction de logements
    "41.10C": "macon",  # Développement de projets immobiliers avec construction de bureaux
    "41.10D": "macon",  # Développement de projets immobiliers avec construction mixte
    "41.20A": "macon",  # Construction de maisons individuelles
    "41.20B": "macon",  # Construction d'autres bâtiments

    # Division 42 - Génie civil
    "42.11Z": "macon",  # Construction de routes et autoroutes
    "42.12Z": "macon",  # Construction de voies ferrées de surface et souterraines
    "42.13A": "macon",  # Construction d'ouvrages d'art
    "42.13B": "macon",  # Construction et entretien de tunnels
    "42.21Z": "plombier",  # Construction de réseaux pour fluides
    "42.22Z": "electricien",  # Construction de réseaux électriques et de télécommunications
    "42.91Z": "macon",  # Construction d'ouvrages maritimes et fluviaux
    "42.99Z": "macon",  # Construction d'autres ouvrages de génie civil n.c.a.

    # Division 43 - Travaux de construction spécialisés
    "43.11Z": "macon",  # Travaux de démolition
    "43.12A": "macon",  # Travaux de terrassement courants et travaux préparatoires
    "43.12B": "macon",  # Travaux de terrassement spécialisés ou de grande masse
    "43.13Z": "macon",  # Forages et sondages
    "43.21A": "electricien",  # Travaux d'installation électrique dans tous locaux
    "43.21B": "electricien",  # Travaux d'installation électrique sur la voie publique
    "43.22A": "plombier",  # Travaux d'installation d'eau et de gaz en tous locaux
    "43.22B": "plombier-chauffagiste",  # Travaux d'installation d'équipements thermiques
    "43.29A": "artisan-isolation",  # Travaux d'isolation
    "43.29B": "autre-activite",  # Autres travaux d'installation n.c.a.
    "43.31Z": "plaquiste",  # Travaux de plâtrerie
    "43.32A": "menuisier",  # Travaux de menuiserie bois et PVC
    "43.32B": "menuisier-charpentier",  # Travaux de menuiserie métallique et serrurerie
    "43.32C": "serrurier",  # Agencement de lieux de vente
    "43.33Z": "carreleur",  # Travaux de revêtement des sols et des murs
    "43.34Z": "peintre-batiment",  # Travaux de peinture et vitrerie
    "43.39Z": "artisan-renovation",  # Autres travaux de finition
    "43.91A": "couvreur",  # Travaux de charpente
    "43.91B": "couvreur-zingueur",  # Travaux de couverture par éléments
    "43.99A": "macon",  # Travaux d'étanchéification
    "43.99B": "macon",  # Travaux de montage de structures métalliques
    "43.99C": "artisan-renovation",  # Travaux de maçonnerie générale et gros œuvre de bâtiment
    "43.99D": "artisan-isolation",  # Autres travaux spécialisés de construction
    "43.99E": "macon",  # Location avec opérateur de matériel de construction
    "43.25Z": "climaticien",  # Travaux d'installation d'eau et de climatisation

    # =========================================================================
    # SECTION G - COMMERCE; RÉPARATION D'AUTOMOBILES ET DE MOTOCYCLES (45-47)
    # =========================================================================
    # Division 45 - Commerce et réparation d'automobiles et de motocycles
    "45.11Z": "garage-automobile",  # Commerce de voitures et de véhicules automobiles légers
    "45.19Z": "garage-automobile",  # Commerce d'autres véhicules automobiles
    "45.20A": "garage-automobile",  # Entretien et réparation de véhicules automobiles légers
    "45.20B": "garage-automobile",  # Entretien et réparation d'autres véhicules automobiles
    "45.31Z": "garage-automobile",  # Commerce de gros d'équipements automobiles
    "45.32Z": "garage-automobile",  # Commerce de détail d'équipements automobiles
    "45.40Z": "garage-automobile",  # Commerce et réparation de motocycles

    # Division 46 - Commerce de gros, à l'exception des automobiles
    "46.11Z": "agent-commercial",  # Intermédiaires du commerce en matières premières agricoles
    "46.12A": "agent-commercial",  # Centrales d'achat de carburant
    "46.12B": "agent-commercial",  # Autres intermédiaires du commerce en combustibles
    "46.13Z": "agent-commercial",  # Intermédiaires du commerce en bois et matériaux
    "46.14Z": "agent-commercial",  # Intermédiaires du commerce en machines
    "46.15Z": "agent-commercial",  # Intermédiaires du commerce en meubles
    "46.16Z": "agent-commercial",  # Intermédiaires du commerce en textiles
    "46.17Z": "agent-commercial",  # Intermédiaires du commerce en denrées
    "46.18Z": "agent-commercial",  # Intermédiaires spécialisés dans le commerce d'autres produits
    "46.19A": "agent-commercial",  # Centrales d'achat non alimentaires
    "46.19B": "agent-commercial",  # Autres intermédiaires du commerce
    "46.21Z": "grossiste",  # Commerce de gros de céréales, de tabac non manufacturé
    "46.22Z": "grossiste",  # Commerce de gros de fleurs et plantes
    "46.23Z": "grossiste",  # Commerce de gros d'animaux vivants
    "46.24Z": "grossiste",  # Commerce de gros de cuirs et peaux
    "46.31Z": "grossiste",  # Commerce de gros de fruits et légumes
    "46.32A": "grossiste",  # Commerce de gros de viandes de boucherie
    "46.32B": "grossiste",  # Commerce de gros de produits à base de viande
    "46.32C": "grossiste",  # Commerce de gros de volailles et gibier
    "46.33Z": "grossiste",  # Commerce de gros de produits laitiers, œufs
    "46.34Z": "grossiste",  # Commerce de gros de boissons
    "46.35Z": "grossiste",  # Commerce de gros de produits à base de tabac
    "46.36Z": "grossiste",  # Commerce de gros de sucre, chocolat et confiserie
    "46.37Z": "grossiste",  # Commerce de gros de café, thé, cacao et épices
    "46.38A": "grossiste",  # Commerce de gros de poissons, crustacés et mollusques
    "46.38B": "grossiste",  # Commerce de gros alimentaire spécialisé divers
    "46.39A": "grossiste",  # Commerce de gros de produits surgelés
    "46.39B": "grossiste",  # Commerce de gros alimentaire non spécialisé
    "46.41Z": "grossiste",  # Commerce de gros de textiles
    "46.42Z": "grossiste",  # Commerce de gros d'habillement et de chaussures
    "46.43Z": "grossiste",  # Commerce de gros d'appareils électroménagers
    "46.44Z": "grossiste",  # Commerce de gros de vaisselle, verrerie et produits d'entretien
    "46.45Z": "grossiste",  # Commerce de gros de parfumerie et de produits de beauté
    "46.46Z": "grossiste",  # Commerce de gros de produits pharmaceutiques
    "46.47Z": "grossiste",  # Commerce de gros de meubles, de tapis et d'appareils d'éclairage
    "46.48Z": "grossiste",  # Commerce de gros d'articles d'horlogerie et de bijouterie
    "46.49Z": "grossiste",  # Commerce de gros d'autres biens domestiques
    "46.51Z": "grossiste",  # Commerce de gros d'ordinateurs et d'équipements informatiques
    "46.52Z": "grossiste",  # Commerce de gros de composants et d'équipements électroniques
    "46.61Z": "grossiste",  # Commerce de gros de matériel agricole
    "46.62Z": "grossiste",  # Commerce de gros de machines-outils
    "46.63Z": "grossiste",  # Commerce de gros de machines pour l'extraction et la construction
    "46.64Z": "grossiste",  # Commerce de gros de machines pour l'industrie textile
    "46.65Z": "grossiste",  # Commerce de gros de mobilier de bureau
    "46.66Z": "grossiste",  # Commerce de gros d'autres machines et équipements de bureau
    "46.69A": "grossiste",  # Commerce de gros de matériel électrique
    "46.69B": "grossiste",  # Commerce de gros de fournitures et équipements industriels
    "46.69C": "grossiste",  # Commerce de gros de fournitures et équipements divers
    "46.71Z": "grossiste",  # Commerce de gros de combustibles et de produits annexes
    "46.72Z": "grossiste",  # Commerce de gros de minerais et métaux
    "46.73A": "grossiste",  # Commerce de gros de bois et de matériaux de construction
    "46.73B": "grossiste",  # Commerce de gros d'appareils sanitaires
    "46.74A": "grossiste",  # Commerce de gros de quincaillerie
    "46.74B": "grossiste",  # Commerce de gros de fournitures pour la plomberie
    "46.75Z": "grossiste",  # Commerce de gros de produits chimiques
    "46.76Z": "grossiste",  # Commerce de gros d'autres produits intermédiaires
    "46.77Z": "grossiste",  # Commerce de gros de déchets et débris
    "46.90Z": "grossiste",  # Commerce de gros non spécialisé

    # Division 47 - Commerce de détail
    "47.11A": "commerce-detail",  # Commerce de détail de produits surgelés
    "47.11B": "commerce-detail",  # Commerce d'alimentation générale
    "47.11C": "commerce-detail",  # Supérettes
    "47.11D": "commerce-detail",  # Supermarchés
    "47.11E": "commerce-detail",  # Magasins multi-commerces
    "47.11F": "commerce-detail",  # Hypermarchés
    "47.19A": "commerce-detail",  # Grands magasins
    "47.19B": "commerce-detail",  # Autres commerces de détail en magasin non spécialisé
    "47.21Z": "commerce-detail",  # Commerce de détail de fruits et légumes
    "47.22Z": "boucherie",  # Commerce de détail de viandes et de produits à base de viande
    "47.23Z": "poissonnier",  # Commerce de détail de poissons, crustacés et mollusques
    "47.24Z": "boulangerie-patisserie",  # Commerce de détail de pain, pâtisserie et confiserie
    "47.25Z": "commerce-detail",  # Commerce de détail de boissons
    "47.26Z": "commerce-detail",  # Commerce de détail de produits à base de tabac
    "47.29Z": "commerce-detail",  # Autres commerces de détail alimentaires
    "47.30Z": "commerce-detail",  # Commerce de détail de carburants en magasin spécialisé
    "47.41Z": "commerce-detail",  # Commerce de détail d'ordinateurs
    "47.42Z": "commerce-detail",  # Commerce de détail de matériels de télécommunication
    "47.43Z": "commerce-detail",  # Commerce de détail de matériels audio/vidéo
    "47.51Z": "commerce-detail",  # Commerce de détail de textiles
    "47.52A": "commerce-detail",  # Commerce de détail de quincaillerie
    "47.52B": "commerce-detail",  # Commerce de détail de peintures et vernis
    "47.53Z": "commerce-detail",  # Commerce de détail de tapis, moquettes
    "47.54Z": "commerce-detail",  # Commerce de détail d'appareils électroménagers
    "47.59A": "commerce-detail",  # Commerce de détail de meubles
    "47.59B": "commerce-detail",  # Commerce de détail d'autres équipements du foyer
    "47.61Z": "commerce-detail",  # Commerce de détail de livres
    "47.62Z": "commerce-detail",  # Commerce de détail de journaux et papeterie
    "47.63Z": "commerce-detail",  # Commerce de détail d'enregistrements musicaux et vidéo
    "47.64Z": "commerce-detail",  # Commerce de détail d'articles de sport
    "47.65Z": "commerce-detail",  # Commerce de détail de jeux et jouets
    "47.71Z": "commerce-detail",  # Commerce de détail d'habillement
    "47.72A": "commerce-detail",  # Commerce de détail de la chaussure
    "47.72B": "commerce-detail",  # Commerce de détail de maroquinerie et d'articles de voyage
    "47.73Z": "pharmacie",  # Commerce de détail de produits pharmaceutiques
    "47.74Z": "commerce-detail",  # Commerce de détail d'articles médicaux et orthopédiques
    "47.75Z": "commerce-detail",  # Commerce de détail de parfumerie et de produits de beauté
    "47.76Z": "fleuriste",  # Commerce de détail de fleurs, plantes
    "47.77Z": "commerce-detail",  # Commerce de détail d'articles d'horlogerie et de bijouterie
    "47.78A": "opticien",  # Commerces de détail d'optique
    "47.78B": "commerce-detail",  # Commerces de détail de charbons et combustibles
    "47.78C": "commerce-detail",  # Autres commerces de détail spécialisés divers
    "47.79Z": "commerce-detail",  # Commerce de détail de biens d'occasion en magasin
    "47.81Z": "commerce-ambulant",  # Commerce de détail alimentaire sur éventaires et marchés
    "47.82Z": "commerce-ambulant",  # Commerce de détail de textiles sur éventaires et marchés
    "47.89Z": "commerce-ambulant",  # Autres commerces de détail sur éventaires et marchés
    "47.91A": "e-commerce",  # Vente à distance sur catalogue général
    "47.91B": "e-commerce",  # Vente à distance sur catalogue spécialisé
    "47.99A": "commerce-ambulant",  # Vente à domicile
    "47.99B": "commerce-detail",  # Vente par automates et autres commerces de détail

    # =========================================================================
    # SECTION H - TRANSPORTS ET ENTREPOSAGE (49-53)
    # =========================================================================
    # Division 49 - Transports terrestres et transport par conduites
    "49.10Z": "transporteur",  # Transport ferroviaire interurbain de voyageurs
    "49.20Z": "transporteur",  # Transports ferroviaires de fret
    "49.31Z": "transporteur",  # Transports urbains et suburbains de voyageurs
    "49.32Z": "taxi-vtc",  # Transports de voyageurs par taxis
    "49.39A": "transporteur",  # Transports routiers réguliers de voyageurs
    "49.39B": "transporteur",  # Autres transports routiers de voyageurs
    "49.39C": "taxi-vtc",  # Téléphériques et remontées mécaniques
    "49.41A": "transporteur",  # Transports routiers de fret interurbains
    "49.41B": "transporteur",  # Transports routiers de fret de proximité
    "49.41C": "demenageur",  # Location de camions avec chauffeur
    "49.42Z": "demenageur",  # Services de déménagement
    "49.50Z": "autre-activite",  # Transports par conduites

    # Division 50 - Transports par eau
    "50.10Z": "autre-activite",  # Transports maritimes et côtiers de passagers
    "50.20Z": "autre-activite",  # Transports maritimes et côtiers de fret
    "50.30Z": "autre-activite",  # Transports fluviaux de passagers
    "50.40Z": "autre-activite",  # Transports fluviaux de fret

    # Division 51 - Transports aériens
    "51.10Z": "autre-activite",  # Transports aériens de passagers
    "51.21Z": "autre-activite",  # Transports aériens de fret
    "51.22Z": "autre-activite",  # Transports spatiaux

    # Division 52 - Entreposage et services auxiliaires des transports
    "52.10A": "autre-activite",  # Entreposage et stockage frigorifique
    "52.10B": "autre-activite",  # Entreposage et stockage non frigorifique
    "52.21Z": "autre-activite",  # Services auxiliaires des transports terrestres
    "52.22Z": "autre-activite",  # Services auxiliaires des transports par eau
    "52.23Z": "autre-activite",  # Services auxiliaires des transports aériens
    "52.24A": "autre-activite",  # Manutention portuaire
    "52.24B": "autre-activite",  # Manutention non portuaire
    "52.29A": "autre-activite",  # Messagerie, fret express
    "52.29B": "autre-activite",  # Affrètement et organisation des transports

    # Division 53 - Activités de poste et de courrier
    "53.10Z": "coursier",  # Activités de poste dans le cadre d'une obligation de service universel
    "53.20Z": "coursier",  # Autres activités de poste et de courrier

    # =========================================================================
    # SECTION I - HÉBERGEMENT ET RESTAURATION (55-56)
    # =========================================================================
    # Division 55 - Hébergement
    "55.10Z": "hotel",  # Hôtels et hébergement similaire
    "55.20Z": "chambre-d-hotes",  # Hébergement touristique et autre hébergement de courte durée
    "55.30Z": "gite",  # Terrains de camping et parcs pour caravanes ou véhicules de loisirs
    "55.90Z": "chambre-d-hotes",  # Autres hébergements

    # Division 56 - Restauration
    "56.10A": "restaurant",  # Restauration traditionnelle
    "56.10B": "restaurant-rapide",  # Cafétérias et autres libres-services
    "56.10C": "restaurant-rapide",  # Restauration de type rapide
    "56.21Z": "traiteur",  # Services des traiteurs
    "56.29A": "traiteur",  # Restauration collective sous contrat
    "56.29B": "traiteur",  # Autres services de restauration n.c.a.
    "56.30Z": "cafe-bar",  # Débits de boissons

    # =========================================================================
    # SECTION J - INFORMATION ET COMMUNICATION (58-63)
    # =========================================================================
    # Division 58 - Édition
    "58.11Z": "autre-activite",  # Édition de livres
    "58.12Z": "autre-activite",  # Édition de répertoires et de fichiers d'adresses
    "58.13Z": "autre-activite",  # Édition de journaux
    "58.14Z": "autre-activite",  # Édition de revues et périodiques
    "58.19Z": "autre-activite",  # Autres activités d'édition
    "58.21Z": "developpement-web",  # Édition de jeux électroniques
    "58.29A": "developpement-web",  # Édition de logiciels système et de réseau
    "58.29B": "developpement-web",  # Édition de logiciels outils de développement
    "58.29C": "developpement-web",  # Édition de logiciels applicatifs

    # Division 59 - Production de films cinématographiques, de vidéo et de programmes de télévision
    "59.11A": "videaste",  # Production de films et de programmes pour la télévision
    "59.11B": "production-video",  # Production de films institutionnels et publicitaires
    "59.11C": "videaste",  # Production de films pour le cinéma
    "59.12Z": "production-video",  # Post-production de films cinématographiques, de vidéo
    "59.13A": "production-video",  # Distribution de films cinématographiques
    "59.13B": "production-video",  # Édition et distribution vidéo
    "59.14Z": "autre-activite",  # Projection de films cinématographiques
    "59.20Z": "autre-activite",  # Enregistrement sonore et édition musicale

    # Division 60 - Programmation et diffusion
    "60.10Z": "autre-activite",  # Édition et diffusion de programmes radio
    "60.20A": "autre-activite",  # Édition de chaînes généralistes
    "60.20B": "autre-activite",  # Édition de chaînes thématiques

    # Division 61 - Télécommunications
    "61.10Z": "autre-activite",  # Télécommunications filaires
    "61.20Z": "autre-activite",  # Télécommunications sans fil
    "61.30Z": "autre-activite",  # Télécommunications par satellite
    "61.90Z": "autre-activite",  # Autres activités de télécommunication

    # Division 62 - Programmation, conseil et autres activités informatiques
    "62.01Z": "developpement-web",  # Programmation informatique
    "62.02A": "conseil-informatique",  # Conseil en systèmes et logiciels informatiques
    "62.02B": "infogerance",  # Tierce maintenance de systèmes et d'applications informatiques
    "62.03Z": "infogerance",  # Gestion d'installations informatiques
    "62.09Z": "developpement-web",  # Autres activités informatiques

    # Division 63 - Services d'information
    "63.11Z": "hebergement-web",  # Traitement de données, hébergement et activités connexes
    "63.12Z": "agence-web",  # Portails Internet
    "63.91Z": "autre-activite",  # Activités des agences de presse
    "63.99Z": "conseil-informatique",  # Autres services d'information n.c.a.

    # =========================================================================
    # SECTION K - ACTIVITÉS FINANCIÈRES ET D'ASSURANCE (64-66)
    # =========================================================================
    "64.11Z": "autre-activite",  # Activités de banque centrale
    "64.19Z": "autre-activite",  # Autres intermédiations monétaires
    "64.20Z": "holding-financiere",  # Activités des sociétés holding
    "64.30Z": "autre-activite",  # Fonds de placement et entités financières similaires
    "64.91Z": "autre-activite",  # Crédit-bail
    "64.92Z": "autre-activite",  # Autre distribution de crédit
    "64.99Z": "autre-activite",  # Autres activités des services financiers
    "65.11Z": "courtier-assurance",  # Assurance vie
    "65.12Z": "courtier-assurance",  # Autres assurances
    "65.20Z": "courtier-assurance",  # Réassurance
    "65.30Z": "courtier-assurance",  # Caisses de retraite
    "66.11Z": "autre-activite",  # Administration de marchés financiers
    "66.12Z": "autre-activite",  # Courtage de valeurs mobilières et de marchandises
    "66.19A": "autre-activite",  # Supports juridiques de gestion de patrimoine mobilier
    "66.19B": "autre-activite",  # Autres activités auxiliaires de services financiers
    "66.21Z": "courtier-assurance",  # Évaluation des risques et dommages
    "66.22Z": "courtier-assurance",  # Activités des agents et courtiers d'assurances
    "66.29Z": "courtier-assurance",  # Autres activités auxiliaires d'assurance
    "66.30Z": "gestion-fonds",  # Gestion de fonds

    # =========================================================================
    # SECTION L - ACTIVITÉS IMMOBILIÈRES (68)
    # =========================================================================
    "68.10Z": "agence-immobiliere",  # Activités des marchands de biens immobiliers
    "68.20A": "location-immobiliere",  # Location de logements
    "68.20B": "gestion-immobiliere",  # Location de terrains et d'autres biens immobiliers
    "68.31Z": "agence-immobiliere",  # Agences immobilières
    "68.32A": "gestionnaire-locatif",  # Administration d'immeubles et autres biens immobiliers
    "68.32B": "syndic-copropriete",  # Supports juridiques de gestion de patrimoine immobilier

    # =========================================================================
    # SECTION M - ACTIVITÉS SPÉCIALISÉES, SCIENTIFIQUES ET TECHNIQUES (69-75)
    # =========================================================================
    # Division 69 - Activités juridiques et comptables
    "69.10Z": "avocat",  # Activités juridiques
    "69.20Z": "comptable",  # Activités comptables

    # Division 70 - Activités des sièges sociaux; conseil de gestion
    "70.10Z": "holding",  # Activités des sièges sociaux
    "70.21Z": "conseil-gestion",  # Conseil en relations publiques et communication
    "70.22Z": "conseil-gestion",  # Conseil pour les affaires et autres conseils de gestion

    # Division 71 - Activités d'architecture et d'ingénierie
    "71.11Z": "architecte",  # Activités d'architecture
    "71.12A": "geometre",  # Activité des géomètres
    "71.12B": "diagnostiqueur-immobilier",  # Ingénierie, études techniques
    "71.20A": "controle-technique",  # Contrôle technique automobile
    "71.20B": "laboratoire-analyse",  # Analyses, essais et inspections techniques

    # Division 72 - Recherche-développement scientifique
    "72.11Z": "autre-activite",  # Recherche-développement en biotechnologie
    "72.19Z": "autre-activite",  # Recherche-développement en autres sciences physiques
    "72.20Z": "autre-activite",  # Recherche-développement en sciences humaines et sociales

    # Division 73 - Publicité et études de marché
    "73.11Z": "agence-publicite",  # Activités des agences de publicité
    "73.12Z": "regie-publicitaire",  # Régie publicitaire de médias
    "73.20Z": "autre-activite",  # Études de marché et sondages

    # Division 74 - Autres activités spécialisées, scientifiques et techniques
    "74.10Z": "autre-activite",  # Activités spécialisées de design
    "74.20Z": "photographe",  # Activités photographiques
    "74.30Z": "autre-activite",  # Traduction et interprétation
    "74.90A": "autre-activite",  # Activité des économistes de la construction
    "74.90B": "autre-activite",  # Activités spécialisées, scientifiques et techniques diverses

    # Division 75 - Activités vétérinaires
    "75.00Z": "autre-activite",  # Activités vétérinaires

    # =========================================================================
    # SECTION N - ACTIVITÉS DE SERVICES ADMINISTRATIFS ET DE SOUTIEN (77-82)
    # =========================================================================
    # Division 77 - Activités de location et location-bail
    "77.11A": "autre-activite",  # Location de courte durée de voitures et de véhicules
    "77.11B": "autre-activite",  # Location de longue durée de voitures et de véhicules
    "77.12Z": "autre-activite",  # Location et location-bail de camions
    "77.21Z": "autre-activite",  # Location et location-bail d'articles de loisirs et de sport
    "77.22Z": "autre-activite",  # Location de vidéocassettes et disques vidéo
    "77.29Z": "autre-activite",  # Location et location-bail d'autres biens personnels
    "77.31Z": "autre-activite",  # Location et location-bail de machines et équipements agricoles
    "77.32Z": "autre-activite",  # Location et location-bail de machines et équipements BTP
    "77.33Z": "autre-activite",  # Location et location-bail de machines de bureau
    "77.34Z": "autre-activite",  # Location et location-bail de matériels de transport par eau
    "77.35Z": "autre-activite",  # Location et location-bail de matériels de transport aérien
    "77.39Z": "autre-activite",  # Location et location-bail d'autres machines
    "77.40Z": "autre-activite",  # Location-bail de propriété intellectuelle

    # Division 78 - Activités liées à l'emploi
    "78.10Z": "autre-activite",  # Activités des agences de placement de main-d'œuvre
    "78.20Z": "autre-activite",  # Activités des agences de travail temporaire
    "78.30Z": "autre-activite",  # Autre mise à disposition de ressources humaines

    # Division 79 - Activités des agences de voyage, voyagistes
    "79.11Z": "autre-activite",  # Activités des agences de voyage
    "79.12Z": "autre-activite",  # Activités des voyagistes
    "79.90Z": "autre-activite",  # Autres services de réservation et activités connexes

    # Division 80 - Enquêtes et sécurité
    "80.10Z": "securite-gardiennage",  # Activités de sécurité privée
    "80.20Z": "serrurier",  # Activités liées aux systèmes de sécurité
    "80.30Z": "autre-activite",  # Activités d'enquête

    # Division 81 - Services relatifs aux bâtiments et aménagement paysager
    "81.10Z": "concierge",  # Activités combinées de soutien lié aux bâtiments
    "81.21Z": "nettoyage-bureaux",  # Nettoyage courant des bâtiments
    "81.22Z": "nettoyage-industriel",  # Autres activités de nettoyage des bâtiments
    "81.29A": "nettoyage-industriel",  # Désinfection, désinsectisation, dératisation
    "81.29B": "nettoyage-industriel",  # Autres activités de nettoyage n.c.a.
    "81.29C": "lavage-auto",  # Lavage de véhicules
    "81.30Z": "paysagiste",  # Services d'aménagement paysager

    # Division 82 - Activités administratives et autres activités de soutien
    "82.11Z": "conseil-gestion",  # Services administratifs combinés de bureau
    "82.19Z": "autre-activite",  # Photocopie, préparation de documents
    "82.20Z": "autre-activite",  # Activités de centres d'appels
    "82.30Z": "autre-activite",  # Organisation de foires, salons professionnels et congrès
    "82.91Z": "autre-activite",  # Activités des agences de recouvrement de factures
    "82.92Z": "autre-activite",  # Activités de conditionnement
    "82.99Z": "autre-activite",  # Autres activités de soutien aux entreprises n.c.a.

    # =========================================================================
    # SECTION O - ADMINISTRATION PUBLIQUE (84)
    # =========================================================================
    "84.11Z": "administration-publique",  # Administration publique générale
    "84.12Z": "administration-publique",  # Administration publique (tutelle) de la santé
    "84.13Z": "administration-publique",  # Administration publique (tutelle) des activités économiques
    "84.21Z": "administration-publique",  # Affaires étrangères
    "84.22Z": "administration-publique",  # Défense
    "84.23Z": "administration-publique",  # Justice
    "84.24Z": "administration-publique",  # Activités d'ordre public et de sécurité
    "84.25Z": "administration-publique",  # Services du feu et de secours
    "84.30A": "administration-publique",  # Activités générales de sécurité sociale
    "84.30B": "administration-publique",  # Gestion des retraites complémentaires
    "84.30C": "administration-publique",  # Distribution sociale de revenus

    # =========================================================================
    # SECTION P - ENSEIGNEMENT (85)
    # =========================================================================
    "85.10Z": "formation",  # Enseignement pré-primaire
    "85.20Z": "formation",  # Enseignement primaire
    "85.31Z": "formation",  # Enseignement secondaire général
    "85.32Z": "formation",  # Enseignement secondaire technique ou professionnel
    "85.41Z": "formation",  # Enseignement post-secondaire non supérieur
    "85.42Z": "formation",  # Enseignement supérieur
    "85.51Z": "coach-sportif",  # Enseignement de disciplines sportives et d'activités de loisirs
    "85.52Z": "ecole-musique",  # Enseignement culturel
    "85.53Z": "auto-ecole",  # Enseignement de la conduite
    "85.59A": "formation",  # Formation continue d'adultes
    "85.59B": "formation",  # Autres enseignements
    "85.60Z": "formation",  # Activités de soutien à l'enseignement

    # =========================================================================
    # SECTION Q - SANTÉ HUMAINE ET ACTION SOCIALE (86-88)
    # =========================================================================
    # Division 86 - Activités pour la santé humaine
    "86.10Z": "autre-activite",  # Activités hospitalières
    "86.21Z": "medecin",  # Activité des médecins généralistes
    "86.22A": "medecin",  # Activités de radiodiagnostic et de radiothérapie
    "86.22B": "medecin",  # Activités chirurgicales
    "86.22C": "medecin",  # Autres activités des médecins spécialistes
    "86.23Z": "dentiste",  # Pratique dentaire
    "86.90A": "ambulancier",  # Ambulances
    "86.90B": "laboratoire-analyse",  # Laboratoires d'analyses médicales
    "86.90C": "autre-activite",  # Centres de collecte et banques d'organes
    "86.90D": "autre-activite",  # Activités des infirmiers et des sages-femmes
    "86.90E": "kinesitherapeute",  # Activités des professionnels de la rééducation
    "86.90F": "osteopathe",  # Activités de santé humaine non classées ailleurs
    "86.90G": "autre-activite",  # Activités des psychologues

    # Division 87 - Hébergement médico-social et social
    "87.10A": "autre-activite",  # Hébergement médicalisé pour personnes âgées
    "87.10B": "autre-activite",  # Hébergement médicalisé pour enfants handicapés
    "87.10C": "autre-activite",  # Hébergement médicalisé pour adultes handicapés
    "87.20A": "autre-activite",  # Hébergement social pour handicapés mentaux et malades mentaux
    "87.20B": "autre-activite",  # Hébergement social pour toxicomanes
    "87.30A": "autre-activite",  # Hébergement social pour personnes âgées
    "87.30B": "autre-activite",  # Hébergement social pour handicapés physiques
    "87.90A": "autre-activite",  # Hébergement social pour enfants en difficultés
    "87.90B": "autre-activite",  # Hébergement social pour adultes et familles en difficultés

    # Division 88 - Action sociale sans hébergement
    "88.10A": "aide-domicile",  # Aide à domicile
    "88.10B": "aide-domicile",  # Accueil ou accompagnement sans hébergement d'adultes handicapés
    "88.10C": "aide-domicile",  # Aide par le travail
    "88.91A": "creche",  # Accueil de jeunes enfants
    "88.91B": "creche",  # Accueil ou accompagnement sans hébergement d'enfants handicapés
    "88.99A": "aide-sociale",  # Autre accueil ou accompagnement sans hébergement d'enfants
    "88.99B": "aide-sociale",  # Action sociale sans hébergement n.c.a.

    # =========================================================================
    # SECTION R - ARTS, SPECTACLES ET ACTIVITÉS RÉCRÉATIVES (90-93)
    # =========================================================================
    # Division 90 - Activités créatives, artistiques et de spectacle
    "90.01Z": "artiste-spectacle",  # Arts du spectacle vivant
    "90.02Z": "production-spectacle",  # Activités de soutien au spectacle vivant
    "90.03A": "artiste-plasticien",  # Création artistique relevant des arts plastiques
    "90.03B": "artiste",  # Autre création artistique
    "90.04Z": "autre-activite",  # Gestion de salles de spectacles

    # Division 91 - Bibliothèques, archives, musées et autres activités culturelles
    "91.01Z": "autre-activite",  # Gestion des bibliothèques et des archives
    "91.02Z": "autre-activite",  # Gestion des musées
    "91.03Z": "autre-activite",  # Gestion des sites et monuments historiques
    "91.04Z": "autre-activite",  # Gestion des jardins botaniques et zoologiques

    # Division 92 - Organisation de jeux de hasard et d'argent
    "92.00Z": "autre-activite",  # Organisation de jeux de hasard et d'argent

    # Division 93 - Activités sportives, récréatives et de loisirs
    "93.11Z": "equipement-sportif",  # Gestion d'installations sportives
    "93.12Z": "club-sportif",  # Activités de clubs de sports
    "93.13Z": "salle-sport",  # Activités des centres de culture physique
    "93.19Z": "loisirs",  # Autres activités liées au sport
    "93.21Z": "loisirs",  # Activités des parcs d'attractions et parcs à thèmes
    "93.29Z": "loisirs",  # Autres activités récréatives et de loisirs

    # =========================================================================
    # SECTION S - AUTRES ACTIVITÉS DE SERVICES (94-96)
    # =========================================================================
    # Division 94 - Activités des organisations associatives
    "94.11Z": "association",  # Activités des organisations patronales et consulaires
    "94.12Z": "association",  # Activités des organisations professionnelles
    "94.20Z": "association",  # Activités des syndicats de salariés
    "94.91Z": "association",  # Activités des organisations religieuses
    "94.92Z": "association",  # Activités des organisations politiques
    "94.99Z": "association",  # Autres organisations fonctionnant par adhésion volontaire

    # Division 95 - Réparation d'ordinateurs et de biens personnels
    "95.11Z": "maintenance-informatique",  # Réparation d'ordinateurs et d'équipements périphériques
    "95.12Z": "maintenance-informatique",  # Réparation d'équipements de communication
    "95.21Z": "reparation",  # Réparation de produits électroniques grand public
    "95.22Z": "reparation-electromenager",  # Réparation d'appareils électroménagers
    "95.23Z": "cordonnerie",  # Réparation de chaussures et d'articles en cuir
    "95.24Z": "reparation",  # Réparation de meubles et d'équipements du foyer
    "95.25Z": "reparation",  # Réparation d'articles d'horlogerie et de bijouterie
    "95.29Z": "reparation",  # Réparation d'autres biens personnels et domestiques

    # Division 96 - Autres services personnels
    "96.01A": "pressing-blanchisserie",  # Blanchisserie-teinturerie de gros
    "96.01B": "pressing-blanchisserie",  # Blanchisserie-teinturerie de détail
    "96.02A": "coiffure",  # Coiffure
    "96.02B": "esthetique-beaute",  # Soins de beauté
    "96.03Z": "autre-activite",  # Services funéraires
    "96.04Z": "spa-massage",  # Entretien corporel
    "96.09Z": "institut-beaute",  # Autres services personnels n.c.a.

    # =========================================================================
    # SECTION T - ACTIVITÉS DES MÉNAGES (97-98)
    # =========================================================================
    "97.00Z": "aide-domicile",  # Activités des ménages en tant qu'employeurs de personnel domestique
    "98.10Z": "autre-activite",  # Activités indifférenciées des ménages pour leur propre usage
    "98.20Z": "autre-activite",  # Activités indifférenciées des ménages producteurs de services

    # =========================================================================
    # SECTION U - ACTIVITÉS EXTRA-TERRITORIALES (99)
    # =========================================================================
    "99.00Z": "autre-activite",  # Activités des organisations et organismes extraterritoriaux

    # =========================================================================
    # CODES SPÉCIAUX ET COMPATIBILITÉ
    # =========================================================================
    # Code NAF non renseigné
    "00.00Z": "autre-activite",

    # Codes NAF anciens/abrégés (compatibilité NAF Rev.1)
    "01.1A": "agriculteur",
    "01.1B": "agriculteur",
    "01.1C": "agriculteur",
    "01.1D": "maraicher",
    "01.1E": "agriculteur",
    "01.1F": "agriculteur",
    "01.1G": "agriculteur",
    "01.2A": "viticulteur",
    "01.2B": "agriculteur",
    "01.2C": "agriculteur",
    "01.2D": "agriculteur",
    "01.2E": "agriculteur",
    "01.2F": "agriculteur",
    "01.2G": "agriculteur",
    "01.3Z": "jardinier",
    "01.4A": "eleveur",
    "01.4B": "eleveur",
    "01.4C": "eleveur",
    "01.4D": "eleveur",
    "01.4E": "aviculteur",
    "01.4F": "eleveur",
    "01.5Z": "agriculteur",
    "01.6A": "jardinier",
    "01.6B": "eleveur",
}


# =============================================================================
# FONCTIONS UTILITAIRES
# =============================================================================

def get_subcategory_from_naf(naf_code: str):
    """
    Retourne la SousCategorie correspondant au code NAF.

    Args:
        naf_code: Code NAF (ex: "43.22A")

    Returns:
        SousCategorie instance ou None si pas de mapping
    """
    from foxreviews.subcategory.models import SousCategorie

    if not naf_code:
        return None

    # Normaliser le code NAF (enlever espaces, mettre en majuscules)
    naf_code = naf_code.strip().upper()

    # Normalisation de format:
    # - INSEE renvoie souvent sans point: 6201Z / 4322A
    # - Notre mapping est avec point: 62.01Z / 43.22A
    if re.fullmatch(r"\d{4}[A-Z0-9]", naf_code):
        naf_code = f"{naf_code[:2]}.{naf_code[2:]}"

    # Vérifier le cache d'abord
    cache_key = f"naf_mapping_{naf_code}"
    cached_result = cache.get(cache_key)
    if cached_result is not None:
        return cached_result

    # Chercher dans le mapping
    slug = NAF_TO_SUBCATEGORY.get(naf_code)
    if not slug:
        cache.set(cache_key, None, timeout=3600)
        return None

    # Récupérer la sous-catégorie
    try:
        sous_cat = SousCategorie.objects.select_related("categorie").get(slug=slug)
        cache.set(cache_key, sous_cat, timeout=3600)
        return sous_cat
    except SousCategorie.DoesNotExist:
        cache.set(cache_key, None, timeout=3600)
        return None


def get_naf_codes_for_subcategory(sous_categorie_slug: str) -> list[str]:
    """
    Retourne la liste des codes NAF associés à une sous-catégorie.

    Utile pour les recherches inverses.

    Args:
        sous_categorie_slug: Slug de la sous-catégorie

    Returns:
        Liste des codes NAF
    """
    return [
        naf_code
        for naf_code, slug in NAF_TO_SUBCATEGORY.items()
        if slug == sous_categorie_slug
    ]


def get_all_mappings() -> dict[str, str]:
    """
    Retourne tous les mappings NAF → SousCategorie.

    Returns:
        Dictionnaire {code_naf: slug_sous_categorie}
    """
    return NAF_TO_SUBCATEGORY.copy()


def get_mapping_stats() -> dict:
    """
    Retourne des statistiques sur le mapping.

    Returns:
        Dictionnaire avec les stats
    """
    from collections import Counter

    slugs = list(NAF_TO_SUBCATEGORY.values())
    counter = Counter(slugs)

    return {
        "total_naf_codes": len(NAF_TO_SUBCATEGORY),
        "unique_subcategories": len(counter),
        "top_10_subcategories": counter.most_common(10),
    }


def add_mapping(naf_code: str, sous_categorie_slug: str):
    """
    Ajoute un mapping NAF → SousCategorie dynamiquement.

    Note: Ce mapping sera perdu au redémarrage. Pour un mapping permanent,
    modifier directement le dictionnaire NAF_TO_SUBCATEGORY.

    Args:
        naf_code: Code NAF
        sous_categorie_slug: Slug de la sous-catégorie
    """
    NAF_TO_SUBCATEGORY[naf_code.strip().upper()] = sous_categorie_slug
    # Invalider le cache
    cache.delete(f"naf_mapping_{naf_code.strip().upper()}")
