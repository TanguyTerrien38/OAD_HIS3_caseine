# OAD - Outil d'Aide à la Décision (Planification & Supervision)

Une application interactive et visuelle d'aide à la planification, développée en Python avec **Pygame**. Cet outil intègre un puissant moteur de résolution de contraintes (**CPLEX**) pour assister l'utilisateur dans l'assignation de tâches, la résolution de conflits et l'optimisation d'un planning sous contraintes.

## 🌟 Fonctionnalités Principales

* **Interface Graphique Interactive (Gantt) :** Déplacement de tâches par glisser-déposer, ajustement dynamique, et navigation fluide dans le temps.
* **Trois Modes Intégrés :**
    * *Planification :* Création et ajustement libre du planning.
    * *Simulation :* Prévisualisation dynamique de l'exécution des tâches.
    * *Supervision :* Mode d'expérimentation en temps réel gérant des aléas (retards, absences, etc.) nécessitant une replanification.
* **Moteur d'Optimisation (Solveur CPLEX) :**
    * Génération de nouvelles solutions optimisées.
    * Boutons d'aide ciblée : "Placer au plus tôt" ou "Résoudre les conflits".
    * Réparation intelligente du planning en cas de problèmes complexes.
* **Ergonomie Avancée :** * Sélection multiple (Area selection ou `Ctrl + Clic`).
    * Menu contextuel (Clic droit) pour des actions rapides (Épingler, Déplanifier, etc.).
    * Outil "Ciseaux" pour découper des tâches.
    * Historique complet (Annuler/Rétablir).
* **Import / Export :** Sauvegarde et chargement de scénarios au format `.json`.

---

## 🚀 Utilisation (Pour les participants / utilisateurs finaux)

L'application a été packagée pour fonctionner directement sous Windows, **sans aucune installation préalable requise** (ni Python, ni bibliothèques externes).

1. Téléchargez la dernière archive (ex: `OAD_Release.zip`) depuis la section **Releases** de ce dépôt GitHub.
2. Extrayez l'intégralité du dossier sur votre ordinateur.
3. Lancez simplement le fichier **`experience_oad.exe`**.

> **Note :** Le chargement initial peut prendre quelques secondes. L'application se lancera en plein écran.

### ⌨️ Contrôles de base
* **Clic Gauche (Maintenu) :** Déplacer une tâche depuis le panier ou sur la timeline.
* **Clic Droit :** Ouvrir le menu contextuel sur une tâche ou une activité.
* **Clic sur le fond + Glisser :** Créer un rectangle de sélection (Area Selection).
* **`Ctrl` + Clic :** Ajouter/Retirer une tâche à la sélection multiple.
* **`Ctrl` + `Z` / `Ctrl` + `Y` :** Annuler / Rétablir la dernière action.
* **`C` :** Activer/Désactiver l'outil Ciseaux (cliquez ensuite sur une tâche pour la couper au jour ciblé).
* **`Suppr` :** Déplanifier les tâches actuellement sélectionnées.
* **Molette de la souris :** Faire défiler la ligne du temps (Timeline) ou le panier de tâches.

---

## 🛠️ Développement (Pour les développeurs)

Si vous souhaitez modifier le code ou compiler vous-même le projet, voici les instructions.

### Prérequis

* **Python 3.8+**
* Le moteur IBM ILOG CPLEX Optimization Studio (le binaire `cpoptimizer.exe` doit être placé dans le dossier `moteur_cplex/` à la racine, ou correctement configuré dans votre environnement).

### Installation des dépendances

Clonez le dépôt et installez les bibliothèques requises :

```bash
git clone [https://github.com/VOTRE_NOM/VOTRE_PROJET.git](https://github.com/VOTRE_NOM/VOTRE_PROJET.git)
cd VOTRE_PROJET
pip install pygame docplex cx_Freeze
