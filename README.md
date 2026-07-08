# Outil d'aide à la décision pour la planification et la supervision

Une application interactive et visuelle d'aide à la planification, développée en Python avec **Pygame**. Cet outil intègre un moteur de résolution de contraintes (**IBM ILOG CP OPTIMIZER**) pour assister l'utilisateur dans l'assignation de tâches, la résolution de conflits et l'optimisation d'un planning sous contraintes.

## 🌟 Fonctionnalités Principales

* **Interface Graphique Interactive (Gantt) :** Déplacement de tâches par glisser-déposer, ajustement dynamique, et navigation fluide dans le temps.
* **Trois Modes Intégrés :**
    * *Planification :* Création et ajustement libre du planning.
    * *Simulation :* Co-construction d'un planning en manipulant le solveur de manière haut-niveau, et comparaison de différentes solutions.
    * *Supervision :* Monitoring en temps réel des aléas (retards, absences, etc.) nécessitant une replanification.
* **Moteur d'Optimisation (Solveur CPO) :**
    * Aide globale : génération de nouvelles solutions optimisées.
    * Aide locale : "Placer au plus tôt" ou "Résoudre les conflits".
    * Réparation intelligente du planning en cas de problèmes complexes.
* **Ergonomie Avancée :** * Sélection multiple de tâches (Area selection ou `Ctrl + Clic`).
    * Menu contextuel (Clic droit) pour des actions rapides (Épingler, Déplanifier, etc.).
    * Outil "Ciseaux" pour découper des tâches.
    * Historique complet (undo/redo).
* **Import / Export :** Sauvegarde et chargement de scénarios au format `.json`.

---

## 🚀 Utilisation (Pour les participants / utilisateurs finaux)

L'application a été packagée pour fonctionner directement sous Windows, **sans aucune installation préalable requise**.

1. Téléchargez ce dépôt GitHub en .zip.
2. Extrayez l'intégralité du dossier sur votre ordinateur.
3. Lancez simplement le fichier **`Experience_OAD.exe`**.

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
