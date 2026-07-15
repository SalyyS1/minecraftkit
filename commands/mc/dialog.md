---
description: Design native Minecraft dialogs, inputs, actions, and safe fallbacks through mc:dialog.
argument-hint: "[dialog flow or problem]"
---

# /mc:dialog

Activate the installed `mc-dialog` skill for the `/mc:dialog` route:

<request>$ARGUMENTS</request>

Pin Minecraft/Paper version and registration mode. Define dialog body, inputs, actions, after-action behavior, namespaced keys, authorization and replay limits. Treat client payloads as untrusted, preserve upstream experimental labels, and provide a semantically honest fallback for unsupported clients.
