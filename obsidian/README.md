# Obsidian Themes — Mission Control

Two CSS snippets that make Obsidian match the two mission-control dashboard palettes.

## Install (Windows PowerShell)

```powershell
# Replace <VaultName> with your actual Obsidian vault folder.
$vault = "$env:USERPROFILE\Documents\<VaultName>\.obsidian\snippets"
New-Item -ItemType Directory -Force -Path $vault

Copy-Item "C:\Users\whitt\Development\expert-ai-skills\obsidian\mission-control-red.css" $vault
Copy-Item "C:\Users\whitt\Development\expert-ai-skills\obsidian\mission-control-bluegold.css" $vault
```

## Enable

1. Open Obsidian
2. Settings → Appearance
3. Under "CSS snippets", click the refresh icon if the files don't show
4. Toggle ON **either** `mission-control-red` **or** `mission-control-bluegold` (not both — they override each other)

## What they do

- Map mission-control palette tokens to Obsidian's theme CSS variables
- Sharpen all `border-radius` to 2px (no pill shapes)
- Accent color (red or gold) used for active file indicator, links, tag text, blockquote border, selection highlight
- Monospace status bar

## Switching palettes

Just toggle one off and the other on in `Settings → Appearance → CSS snippets`. No app restart needed.
