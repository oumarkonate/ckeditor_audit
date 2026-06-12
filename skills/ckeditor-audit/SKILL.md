---
name: ckeditor-audit
description: >-
  Dashboard d'audit de migration CKEditor. Utiliser quand l'utilisateur demande à "auditer
  CKEditor", "voir l'état de migration des plugins CKEditor", "quels plugins CKEditor sont migrés",
  "migration status CKEditor", "overview CKEditor", "bilan plugins CKEditor", ou mentionne
  vouloir savoir où en est la migration CKEditor 5.
  Utiliser aussi quand l'utilisateur dit "audit ckeditor", "check ckeditor plugins",
  "migration overview", "show ckeditor status".
version: 0.1.0
user-invocable: true
allowed-tools:
  - mcp__ckeditor_audit__audit_all
  - mcp__ckeditor_audit__audit_plugin
  - mcp__ckeditor_audit__find_plugin_usages
  - mcp__ckeditor_audit__list_patterns
---

# CKEditor Audit — Dashboard de migration

Présente un tableau de bord complet de l'état de migration de tous les plugins CKEditor du projet.

## Workflow

### Étape 1 — Vue d'ensemble

Appeler `audit_all` pour obtenir le résumé global :

```
mcp__ckeditor_audit__audit_all()
```

Afficher un tableau récapitulatif :

| Statut | Nombre |
|--------|--------|
| Migrés (✅) | `migrated` |
| Partiels (⚠️) | `partial` |
| Non migrés (❌) | `not_migrated` |
| **Total** | `total` |

### Étape 2 — Détail des plugins problématiques

Pour chaque plugin dont le statut est `partial` ou `not_migrated`, appeler `audit_plugin` pour
obtenir le nombre d'issues et les fichiers de config qui le référencent :

```
mcp__ckeditor_audit__audit_plugin(plugin="<nom>")
```

Afficher par plugin :
- Statut (`partial` / `not_migrated`)
- Nombre d'issues détectées (patterns legacy trouvés)
- Fichiers de config qui le référencent (actifs vs commentés)

### Étape 3 — Prochaines actions

Présenter les actions disponibles :

- Pour migrer un plugin précis : `/ckeditor-migrate <nom-du-plugin>`
- Pour générer le rapport complet : `/ckeditor-report`
- Pour voir les patterns de migration connus : `list_patterns`

## Format de sortie attendu

```
## CKEditor Migration Dashboard

| Statut | Count |
|--------|-------|
| ✅ Migrés | 5 |
| ⚠️ Partiels | 2 |
| ❌ Non migrés | 3 |
| Total | 10 |

### Plugins à migrer

| Plugin | Statut | Issues | Config refs |
|--------|--------|--------|-------------|
| ckeditor5-image | ❌ not_migrated | 4 | 2 actifs |
| ckeditor5-toolbar | ⚠️ partial | 2 | 1 actif |

### Prochaines étapes
- `/ckeditor-migrate ckeditor5-image` — migrer ce plugin
- `/ckeditor-report` — rapport Markdown complet
```

## Notes

- Si tous les plugins sont `migrated`, féliciter l'utilisateur et proposer `/ckeditor-report` pour
  archiver le bilan.
- Si aucun plugin n'est trouvé (liste vide), vérifier que `CKEDITOR_AUDIT_PROJECT_ROOT` et
  `CKEDITOR_AUDIT_PLUGINS_GLOB` sont correctement configurés.
