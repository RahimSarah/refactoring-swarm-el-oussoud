# TP IGL 2025-2026 : The Refactoring Swarm

**Module** : Ingenierie Logicielle  
**Etablissement** : ESI (Ecole nationale Superieure d'Informatique)  
**Niveau** : 1CS  
**Enseignant** : BATATA Sofiane  

---

## Informations generales

| Element | Details |
|---------|---------|
| Duree | 2 a 3 semaines (Sprint unique) |
| Organisation | Equipes de 4 etudiants |
| Evaluation | 100% automatisee (Performance & Data-Driven) |

---

## 1. Contexte

Ce TP s'inscrit dans une experience de recherche en Genie Logiciel Empirique.

**Objectif** : Concevoir une architecture d'agents autonomes (LLM) capable de realiser de la maintenance logicielle sans intervention humaine.

**Mission** : Construire un systeme multi-agents "The Refactoring Swarm" qui :
- Prend en entree un dossier contenant du code Python "mal fait" (bugge, non documente, non teste)
- Livre en sortie une version propre, fonctionnelle et validee par des tests

---

## 2. Architecture du systeme

Le systeme doit orchestrer la collaboration entre **au moins 3 agents specialises** :

### Agent Auditeur (The Auditor)
- Lit le code
- Lance l'analyse statique
- Produit un plan de refactoring

### Agent Correcteur (The Fixer)
- Lit le plan de l'Auditeur
- Modifie le code fichier par fichier pour corriger les erreurs

### Agent Testeur (The Judge)
- Execute les tests unitaires
- **Si echec** : Renvoie le code au Correcteur avec les logs d'erreur (Boucle de Self-Healing)
- **Si succes** : Valide la fin de mission

---

## 3. Organisation de l'equipe (4 roles)

Chaque membre est responsable de sa partie, mais le code final doit etre integre dans un seul depot Git.

### 3.1 Orchestrateur (Lead Dev)
- Concoit le graphe d'execution (via LangGraph, CrewAI ou AutoGen)
- Gere la logique de passage de relais entre agents
- Responsable du `main.py` et de la gestion des arguments CLI

### 3.2 Ingenieur Outils (The Toolsmith)
- Developpe les fonctions Python que les agents appellent (API interne)
- Implemente la securite : interdiction pour les agents d'ecrire hors du dossier "sandbox"
- Gere les interfaces vers les outils d'analyse (pylint) et de test (pytest)

### 3.3 Ingenieur Prompt (Prompt Engineer)
- Redige et versionne les instructions systemes (System Prompts)
- Optimise les prompts pour minimiser les hallucinations et le cout en tokens
- Gere le contexte : s'assurer que l'agent a acces au code pertinent sans saturer sa memoire

### 3.4 Responsable Qualite & Data (Data Officer)
- **CRITIQUE** : Responsable de la telemetrie
- Garantit que chaque action des agents est enregistree dans `logs/experiment_data.json` selon le schema impose
- Cree le jeu de donnees de test interne pour valider le systeme avant soumission

> **Note importante** : Le code de chaque membre depend du code des autres. Si l'Ingenieur Outils change le nom d'une fonction sans prevenir l'Ingenieur Prompt, l'agent cessera de fonctionner. Communication permanente obligatoire.

---

## 4. Criteres d'evaluation automatisee

Le Bot de Correction clonera le depot et lancera le systeme sur un "Hidden Dataset" (5 cas minimum de code bugge non connus a l'avance).

| Dimension | Poids | Criteres |
|-----------|-------|----------|
| **Performance** | 40% | Le code final passe-t-il les tests unitaires ? Le score Pylint a-t-il augmente ? |
| **Robustesse Technique** | 30% | Le systeme tourne-t-il sans planter ? Pas de boucle infinie (max 10 iterations) ? Respect de `--target_dir` |
| **Qualite des Donnees** | 30% | Le fichier `experiment_data.json` est-il valide ? Contient-il l'historique complet des actions ? |

---

## 5. Demarche conseillee

### Etape 1 : Hello World & Outils
- Installation propre (Virtualenv)
- Lancer `python check_setup.py` pour valider
- Creation des outils (lecture/ecriture fichier, execution pylint)
- Premier agent simple qui analyse un fichier

### Etape 2 : La Boucle de Feedback
- Connexion : Auditeur -> Correcteur
- Gestion des iterations : le correcteur doit pouvoir reessayer si l'auditeur n'est pas satisfait
- Optimisation des prompts

### Etape 3 : Tests & Robustesse
- Ajout de l'Agent Testeur (pytest)
- Validation complete du format JSON des logs
- Test sur des "fichiers pieges" pour verifier que le systeme ne casse pas tout

---

## 6. Configuration technique

### 6.1 Pre-requis systeme
- **Python** : Version 3.10 ou 3.11 (Python 3.12+ non supporte)
- **Git** : Installe
- **Cle API** : Google Gemini

### 6.2 Installation

#### A. Cloner le template (obligatoire)
```bash
git clone https://github.com/sof-coder/refactoring-swarm-template.git
cd refactoring-swarm-template
```

#### B. Structure du depot

```
/refactoring-swarm-template
|
|-- main.py              [VERROUILLE] Point d'entree obligatoire
|-- requirements.txt     [VERROUILLE] Liste des dependances
|-- .env                 [VERROUILLE] Cles API (ne jamais commiter)
|-- check_setup.py       [VERROUILLE] Script de verification d'environnement
|-- /src                 Code source des agents et outils
|-- /logs                [VERROUILLE] Dossier de sortie pour les donnees
|-- /sandbox             Dossier de travail temporaire
```

> Ne pas modifier les noms des dossiers/fichiers marques comme verrouilles.

#### C. Environnement virtuel
```bash
# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
.\venv\Scripts\activate
```

#### D. Installer les dependances
```bash
pip install -r requirements.txt
```

#### E. Configuration des cles API
1. Dupliquer `.env.example` et renommer en `.env`
2. Obtenir une cle gratuite sur Google AI Studio
3. Ajouter la cle : `GOOGLE_API_KEY=AIzaSy...`

#### F. Verification
```bash
python check_setup.py
```
Si des erreurs apparaissent, corriger l'environnement avant de commencer a coder.

---

## 7. Protocole de Logging

### 7.1 Types d'actions standardises

Utiliser imperativement la classe `ActionType` fournie :

| Action | Utilisation |
|--------|-------------|
| `ActionType.ANALYSIS` | L'agent lit le code pour comprendre, verifier les normes ou chercher des bugs. Aucune modification. |
| `ActionType.GENERATION` | L'agent cree du contenu nouveau (tests unitaires, documentation). |
| `ActionType.DEBUG` | L'agent analyse une erreur d'execution ou une stacktrace pour diagnostiquer un probleme. |
| `ActionType.FIX` | L'agent reecrit une partie du code existant pour corriger un bug ou ameliorer la qualite (Refactoring). |

### 7.2 Contenu obligatoire

Chaque log doit contenir :
1. `input_prompt` : Le texte exact envoye au LLM
2. `output_response` : La reponse brute recue du LLM

Si ces champs sont manquants, le programme s'arretera avec une erreur.

### 7.3 Exemple d'implementation

```python
from src.utils.logger import log_experiment, ActionType

log_experiment(
    agent_name="Auditor_Agent",
    model_used="gemini-2.5-flash",
    action=ActionType.ANALYSIS,
    details={
        "file_analyzed": "messy_code.py",
        "input_prompt": "Tu es un expert Python. Analyse ce code...",
        "output_response": "J'ai detecte une absence de docstring...",
        "issues_found": 3
    },
    status="SUCCESS"
)
```

Le fichier `logs/experiment_data.json` sera genere automatiquement. Verifier regulierement qu'il se remplit correctement.

---

## 8. Point d'entree (main.py)

Le Bot de Correction lancera le programme avec :
```bash
python main.py --target_dir "./sandbox/dataset_inconnu"
```

Le code doit :
- Lire cet argument
- Lancer les agents sur ce dossier
- S'arreter proprement une fois termine

---

## 9. Instructions de rendu

### 9.1 Verification finale
Avant de rendre, ouvrir `logs/experiment_data.json` et s'assurer qu'il contient l'historique complet des tests avec les prompts.

### 9.2 Forcer l'ajout des logs
Par defaut, Git ignore souvent les fichiers de logs. Pour que le travail soit valide :

```bash
git add -f logs/experiment_data.json
git commit -m "DATA: Submission of experiment logs"
git push origin main
```

### 9.3 Soumission
Deposer le lien du depot Git sur la plateforme de cours.

> **Si le fichier logs est absent du depot, la note "Qualite des Donnees" sera de 0.**

---

## 10. Politique anti-plagiat

1. **Code Similarity** : Tout le code Python sera analyse avec un outil de detection du plagiat
2. **Prompt Forensics** : Les fichiers de prompts seront compares. Similarite >70% = plagiat
3. **Git History** : L'historique des commits est analyse. Un projet depose en un seul commit le dernier jour sera rejete (Note = 0)
4. **Log Signature** : Les logs contiennent des signatures uniques (ID/Timestamps). Copier les logs d'un autre groupe est mathematiquement detectable et entraine l'exclusion immediate

---

## 11. Hygiene Git

### Commits frequents
Faire un commit a chaque etape logique plutot qu'un seul gros commit a la fin.

### Messages clairs
Utiliser des messages descriptifs :
- `feat: ajout logic agent de test`
- `fix: parsing json error`

### Workflow recommande (branches)
1. Recuperer les dernieres modifications : `git checkout main && git pull origin main`
2. Creer une branche pour la tache : `git checkout -b ma-feature`
3. Coder et sauvegarder : `git add . && git commit -m "message"`
4. Partager le travail : `git push origin ma-feature`
5. Creer une Pull Request sur GitHub pour fusionner dans main

### Gestion des conflits
- Chacun son fichier (ex: l'Orchestrateur touche a `main.py`)
- Pour modifier le fichier d'un autre : prevenir avant via l'outil de collaboration
