---
name: ckeditor-migrate
description: >-
  Workflow complet de migration d'un plugin CKEditor spécifique. Utiliser quand l'utilisateur
  demande à "migrer ckeditor5-X", "corriger les imports de ckeditor5-X", "mettre à jour le plugin
  ckeditor5-X", "fix legacy imports ckeditor", "migrate ckeditor plugin", "appliquer la migration
  de X", "corriger le plugin CKEditor X", ou quand il mentionne un nom de plugin CKEditor en
  contexte de migration.
  Également pertinent quand l'utilisateur dit "migrate plugin", "fix ckeditor imports",
  "update ckeditor plugin".
  Prend le nom du plugin en argument (ex: /ckeditor-migrate ckeditor5-image).
version: 0.1.0
user-invocable: true
allowed-tools:
  - mcp__ckeditor_audit__audit_plugin
  - mcp__ckeditor_audit__suggest_migration
  - mcp__ckeditor_audit__validate_migration
  - mcp__ckeditor_audit__list_patterns
  - Read
  - Edit
---

# CKEditor Migrate — Migration complète d'un plugin

Orchestre la migration complète d'un plugin CKEditor de ses imports legacy (`@ckeditor/ckeditor5-*`)
vers les imports modernes (flat `ckeditor5`).

## Usage

```
/ckeditor-migrate ckeditor5-nom-du-plugin
```

Si le nom du plugin n'est pas fourni, demander à l'utilisateur : "Quel plugin voulez-vous migrer ?"

## Workflow

### Étape 1 — Diagnostic initial

```
mcp__ckeditor_audit__audit_plugin(plugin="<nom>")
```

Afficher :
- Statut actuel (`migrated` / `partial` / `not_migrated`)
- Liste des issues (patterns legacy détectés avec file:line)
- Fichiers de config qui référencent le plugin

**Si statut == `migrated`** : appeler `validate_migration` pour double-check, afficher le résultat,
et indiquer que le plugin est propre. Fin du workflow.

### Étape 2 — Suggestions de corrections

```
mcp__ckeditor_audit__suggest_migration(plugin="<nom>")
```

Afficher le tableau des corrections à appliquer :

| Fichier | Ligne | Legacy | Remplacement |
|---------|-------|--------|--------------|
| src/box.js | 1 | `from '@ckeditor/ckeditor5-core/src/plugin'` | `import { Plugin } from 'ckeditor5'` |

### Étape 3 — Application des corrections

Pour chaque fix retourné par `suggest_migration` :

1. Lire le fichier avec `Read` : `Read(path="<path-complet>")`
2. Localiser la ligne exacte contenant le pattern legacy
3. Appliquer la correction avec `Edit`
4. Passer au fix suivant

**Règle importante** : ne modifier que les lignes exactes identifiées par `suggest_migration`.
Ne pas refactoriser le reste du fichier. Une correction = un `Edit`.

**Chemin complet** : construire le chemin absolu en préfixant avec `CKEDITOR_AUDIT_PROJECT_ROOT`
(disponible dans `audit_plugin.token_savings.note` ou via la config du serveur).

### Étape 4 — Validation

```
mcp__ckeditor_audit__validate_migration(plugin="<nom>")
```

**Si `clean: true`** → afficher un message de succès :
```
✅ Plugin `ckeditor5-X` entièrement migré — aucune signature legacy restante.
```

**Si `clean: false`** → afficher les hits restants et proposer de les corriger (reboucle sur
étape 2-3 avec les hits restants uniquement).

## Gestion des cas particuliers

- **Plugin introuvable** : indiquer que le plugin n'existe pas dans `CKEDITOR_AUDIT_PLUGINS_GLOB`
  et suggérer `/ckeditor-audit` pour voir la liste des plugins disponibles.
- **Statut `partial`** : il reste des imports mixed — les corriger comme un `not_migrated`, en ne
  touchant que les patterns legacy identifiés.
- **Pattern inconnu** : si un import legacy ne figure pas dans la table `suggest_migration`, le
  signaler à l'utilisateur sans modifier le fichier — ne pas deviner le remplacement.

## Après migration

Suggérer :
- `/ckeditor-audit` pour voir l'état global mis à jour
- `/ckeditor-report` pour générer le rapport final si tous les plugins sont migrés
