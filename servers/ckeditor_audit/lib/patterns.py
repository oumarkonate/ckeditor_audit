"""
Known legacy → latest migration patterns.

Each Pattern describes one import or API change that must be applied when
migrating a CKEditor custom plugin to a newer version.

- `legacy`      : the old import or code signature to look for (regex-ready string)
- `replacement` : the equivalent in the target version
- `description` : plain-English explanation for the developer
- `category`    : groups patterns by theme (import | api | schema | utils)

Add new entries here whenever a migration session reveals an unknown pattern.
"""

from pydantic import BaseModel


class Pattern(BaseModel):
    legacy: str
    replacement: str
    description: str
    category: str


# ---------------------------------------------------------------------------
# Pattern table — populated from observed migrations (v26 → v47+)
# ---------------------------------------------------------------------------

PATTERNS: list[Pattern] = [
    # --- Imports : core ---
    Pattern(
        legacy="from '@ckeditor/ckeditor5-core/src/plugin'",
        replacement="import { Plugin } from 'ckeditor5'",
        description="Plugin base class is now a named export from the 'ckeditor5' package",
        category="import",
    ),
    Pattern(
        legacy="from '@ckeditor/ckeditor5-core/src/command'",
        replacement="import { Command } from 'ckeditor5'",
        description="Command base class is now a named export from 'ckeditor5'",
        category="import",
    ),
    Pattern(
        legacy="from '@ckeditor/ckeditor5-core/src/editor/",
        replacement="import { ... } from 'ckeditor5'",
        description="Editor classes are now named exports from 'ckeditor5'",
        category="import",
    ),
    # --- Imports : widget ---
    Pattern(
        legacy="from '@ckeditor/ckeditor5-widget/src/widget'",
        replacement="import { Widget } from 'ckeditor5'",
        description="Widget plugin is now a named export from 'ckeditor5'",
        category="import",
    ),
    Pattern(
        legacy="from '@ckeditor/ckeditor5-widget/src/utils'",
        replacement="import { toWidget, toWidgetEditable, ... } from 'ckeditor5'",
        description="Widget utilities are now named exports from 'ckeditor5'",
        category="import",
    ),
    # --- Imports : engine ---
    Pattern(
        legacy="from '@ckeditor/ckeditor5-engine/src/model/text'",
        replacement="# Text is internal — use writer.createText() instead",
        description="Direct import of Text is replaced by writer.createText()",
        category="import",
    ),
    Pattern(
        legacy="from '@ckeditor/ckeditor5-engine/src/model/element'",
        replacement="# ModelElement is internal — use writer.createElement() instead",
        description="Direct import of ModelElement is replaced by writer factory methods",
        category="import",
    ),
    Pattern(
        legacy="from '@ckeditor/ckeditor5-engine/src/view/placeholder'",
        replacement="import { enablePlaceholder } from 'ckeditor5'",
        description="enablePlaceholder is now a named export from 'ckeditor5'",
        category="import",
    ),
    # --- Imports : ui ---
    Pattern(
        legacy="from '@ckeditor/ckeditor5-ui/src/notification/notification'",
        replacement="import { Notification } from 'ckeditor5'",
        description="Notification plugin is now a named export from 'ckeditor5'",
        category="import",
    ),
    # --- Imports : utils ---
    Pattern(
        legacy="from '@ckeditor/ckeditor5-utils/src/first'",
        replacement="import { first } from 'ckeditor5'",
        description="first() utility is now a named export from 'ckeditor5'",
        category="import",
    ),
    # --- API : model ---
    Pattern(
        legacy="new TextProxy(",
        replacement="writer.createText(",
        description="TextProxy constructor is replaced by writer.createText()",
        category="api",
    ),
    # --- Schema ---
    Pattern(
        legacy="allowIn: 'root'",
        replacement="allowWhere: '$block'",
        description="schema.register() option allowIn:'root' becomes allowWhere:'$block'",
        category="schema",
    ),
    Pattern(
        legacy="allowIn: '$root'",
        replacement="allowWhere: '$block'",
        description="schema.register() option allowIn:'$root' becomes allowWhere:'$block'",
        category="schema",
    ),
]
