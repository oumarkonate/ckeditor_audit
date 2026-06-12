---
name: ckeditor-report
description: >-
  Génère le rapport de migration CKEditor complet. Utiliser quand l'utilisateur demande un
  "rapport de migration CKEditor", "générer rapport CKEditor", "export audit CKEditor",
  "bilan de migration CKEditor", "migration report", "rapport complet CKEditor",
  "résumé de la migration", "export du bilan CKEditor", ou veut archiver l'état de migration.
  Utiliser aussi pour "ckeditor report", "generate migration report".
version: 0.1.0
user-invocable: true
allowed-tools:
  - mcp__ckeditor_audit__export_audit_report
  - AskUserQuestion
---

# CKEditor Report — Rapport de migration complet

Génère et affiche le rapport de migration Markdown couvrant tous les plugins du projet.

## Workflow

### Étape 1 — Génération du rapport

```
mcp__ckeditor_audit__export_audit_report(format="markdown")
```

Afficher directement le contenu Markdown retourné par l'outil (field `content`).

Afficher ensuite le résumé des compteurs :

```
Rapport généré :
- ✅ Migrés : X
- ⚠️ Partiels : X
- ❌ Non migrés : X
- Total : X
```

### Étape 2 — Sauvegarde optionnelle

Demander à l'utilisateur s'il veut sauvegarder le rapport dans un fichier :

> "Voulez-vous sauvegarder ce rapport dans un fichier ? Si oui, indiquez le chemin
> (relatif au projet, ex: `docs/ckeditor-migration-report.md`)."

Si l'utilisateur confirme avec un chemin, rappeler l'outil avec `output_path` :

```
mcp__ckeditor_audit__export_audit_report(
  format="markdown",
  output_path="<chemin-fourni>"
)
```

Confirmer le fichier écrit en affichant le `output_path` retourné.

## Format JSON

Si l'utilisateur demande explicitement un rapport JSON (ex: "rapport JSON", "format JSON") :

```
mcp__ckeditor_audit__export_audit_report(format="json")
```

## Notes

- Le rapport inclut pour chaque plugin : statut, tableau des issues (file/line/legacy/replacement),
  et les remplacements à effectuer.
- Idéal à générer en fin de session de migration pour archiver l'état final.
- Pour migrer des plugins précis : `/ckeditor-migrate <plugin>`
- Pour l'overview rapide : `/ckeditor-audit`
