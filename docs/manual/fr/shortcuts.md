---
id: shortcuts
title: Raccourcis clavier
order: 430
section: reference
audience: all
summary: Les raccourcis clavier de l'interface et de l'éditeur Lean.
---

# Raccourcis clavier

Sur macOS, `Ctrl` se lit `⌘`. Les raccourcis d'une seule touche (`/`, `n`) ne s'appliquent pas pendant la saisie
dans un champ de texte.

## Partout

| Raccourci | Action |
|---|---|
| `Ctrl+K` ou `/` | ouvrir la palette : chercher un dossier, une commande, une page d'aide |
| `n` | nouveau dossier (mode *Recherche* seulement) |
| `Échap` | fermer le menu, la palette ou le volet ouvert ; un clic ailleurs le ferme aussi |
| `Ctrl+Maj+1` | afficher ou masquer la barre du projet (Dossiers · Sources · Notes…) |
| `Tab`, `Maj+Tab` | passer d'une commande à l'autre ; un lien « Aller au contenu » apparaît en premier |

## Palette, menus et onglets

| Raccourci | Action |
|---|---|
| `↑` `↓` | choisir dans la palette ou un menu |
| `Entrée` | lancer l'élément choisi |
| `Début`, `Fin` | premier, dernier élément d'un menu |
| `←` `→`, `Début`, `Fin` | passer entre les étapes Énoncé, Traduction Lean, Preuve d'un dossier |

## Envoyer, exécuter, aller à la ligne

Dans tout champ qui envoie quelque chose (nouvel énoncé, demande de suivi, question sur une source, explication,
indices, consigne de recherche, correction de la traduction, demande dans Calcul, assistant du carnet), **`Entrée`
envoie** et **`Maj+Entrée` va à la ligne**. Une petite ligne sous le champ le rappelle.

| Champ | `Entrée` | `Maj+Entrée` |
|---|---|---|
| champs d'envoi (ci-dessus) | envoyer | aller à la ligne |
| cellule de code de Calcul | exécuter la cellule | aller à la ligne (en gardant l'indentation) ; `Tab` / `Maj+Tab` indente |
| preuve Lean modifiée à la main, correction d'un exercice | vérifier avec Lean | aller à la ligne |
| article, corps d'une note, cellule de texte, profil | aller à la ligne | aller à la ligne |

Dans l'article et les notes, `Entrée` reste un retour à la ligne : on y écrit de longs textes. Sur un téléphone ou une
tablette sans clavier, `Entrée` va à la ligne partout et le bouton du champ envoie. `Ctrl+Entrée` envoie aussi.

## Éditeurs (énoncé, Lean, fil du dossier)

| Raccourci | Action |
|---|---|
| `\le` puis `Espace` ou `Tab` | insérer un symbole : `\forall` → `∀`, `\R` → `ℝ`, `\le` → `≤`, `\to` → `→`, `\mid` → `∣` (liste complète dans l'écran « Glossaire ») |
| `Ctrl+Z`, `Ctrl+Maj+Z` | annuler, rétablir |
| `Tab`, `Maj+Tab` | indenter, désindenter (dans l'éditeur Lean) |

Dans l'énoncé en langage courant, les abréviations ne sont pas développées entre `$…$`, pour garder le LaTeX.

## Application de bureau

| Raccourci | Action |
|---|---|
| `Ctrl+Maj+K` | changer de serveur |
