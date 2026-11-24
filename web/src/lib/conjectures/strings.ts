// « Moteur de conjectures » strings (FR / EN), kept apart from the shared catalogues like the Calcul strings
// (parallel sessions edit those); the language follows the app's. The statements, strength labels and journal
// texts come from the server in both languages (`{fr, en}`): `pick` chooses.
import { i18n } from '../i18n/index.svelte';

export const FR: Record<string, string> = {
  title: 'Explorer', lead: 'De la question à la conjecture : calculer, reconnaître, énoncer, chercher un contre-exemple. Chaque étape est visible, peut être arrêtée et reste dans le journal.',
  back: 'Conjectures', question: 'Votre question', questionPh: 'Une question en mots, une formule ou les premiers termes d’une suite (ex. : la somme des n premiers nombres impairs)',
  start: 'Explorer', starting: 'Préparation…', examples: 'Exemples', past: 'Explorations du projet', noPast: 'Aucune exploration pour l’instant.',
  open: 'Ouvrir', del: 'Supprimer', delOf: 'Supprimer l’exploration « {q} »', deleted: 'Exploration supprimée.', newOne: 'Nouvelle exploration',
  candidatesN: '{n} conjecture(s)', refutedN: '{n} réfutée(s)',
  run: 'Lancer', rerun: 'Relancer', stop: 'Arrêter', stopHint: 'Échap arrête aussi.', runningNow: 'En cours…', stoppedToast: 'Arrêté.',
  steps: 'Étapes',
  'step.explore': 'Explorer', 'step.recognise': 'Reconnaître', 'step.state': 'Énoncer', 'step.attack': 'Attaquer', 'step.journal': 'Journal',
  'stepLead.explore': 'Calculer des données dans le carnet du projet.', 'stepLead.recognise': 'Chercher des régularités dans ces données, et la suite dans l’OEIS.',
  'stepLead.state': 'Écrire chaque régularité comme une conjecture précise.', 'stepLead.attack': 'Chercher un contre-exemple, puis tenter la preuve.',
  'stepLead.journal': 'Tout ce qui a été essayé, gardé ou écarté.',
  'state.todo': 'à faire', 'state.running': 'en cours', 'state.awaiting_approval': 'à approuver', 'state.done': 'fait', 'state.failed': 'échec', 'state.stopped': 'arrêté',
  stateOf: '{step} : {state}', seconds: '{s} s',
  recognised: 'Reconnu : {what}', notRecognised: 'Non reconnu : un modèle a écrit le code de l’expérience. Il ne s’exécute qu’après votre accord.',
  givenTerms: 'Termes donnés : rien à calculer.', byCatalogue: 'code vérifié, écrit sans modèle', byUser: 'code modifié par vous',
  code: 'Code de l’expérience', showCode: 'Voir le code', editCode: 'Modifier le code', closeCode: 'Terminer',
  codeHint: 'Un code modifié devient le vôtre : il s’exécute sans approbation.',
  noCodeYet: 'Aucun code : le modèle n’a rien proposé. Vous pouvez l’écrire vous-même.',
  inNotebook: 'Ouvrir dans Calcul', output: 'Sortie du calcul',
  data: 'Données', rowsShown: '{n} premières lignes sur {total}', rowsAll: '{total} lignes', plot: 'Graphique', plotAlt: 'Graphique de {col} en fonction de {x} : {n} points, de {min} à {max}{log}.',
  plotLog: ' (échelle logarithmique)', noPlot: 'Pas de graphique pour ces données.',
  oeis: 'OEIS', oeisAgrees: '{n} termes identiques', oeisShift: 'indice OEIS = n + {k}', oeisFormulas: 'Formules de l’OEIS',
  'oeis.ok': 'Suites de l’OEIS qui coïncident avec tous les termes calculés :', 'oeis.none': 'Aucune suite de l’OEIS ne coïncide avec tous les termes calculés.',
  'oeis.off': 'Mode Local : l’OEIS n’est pas interrogé (rien ne sort de cet ordinateur).', 'oeis.too_short': 'Trop peu de termes pour interroger l’OEIS.',
  'oeis.error': 'L’OEIS n’a pas répondu : recherche non faite.', 'oeis.unrecorded': 'Démonstration : seule la recherche enregistrée (nombres de Catalan) répond.',
  oeisRejected: 'Écartée : {num} diffère au terme n = {n}.',
  lmfdb: 'LMFDB n’est pas interrogée : son interface ne permet pas de chercher par une liste de termes.',
  kept: 'Régularités retenues', discarded: 'Régularités écartées', noneFound: 'Aucune régularité trouvée dans ces données.',
  sageAgrees: 'Sage trouve la même série génératrice.', sageDiffers: 'Sage propose une autre série génératrice : {g}',
  candidates: 'Conjectures candidates', noCandidates: 'Aucune conjecture à énoncer.',
  'kind.polynomial': 'Formule close', 'kind.constant': 'Suite constante', 'kind.rational': 'Fraction rationnelle', 'kind.recurrence': 'Récurrence linéaire',
  'kind.holonomic': 'Récurrence à coefficients polynomiaux', 'kind.algebraic_gf': 'Série génératrice algébrique', 'kind.multiplicative': 'Multiplicativité',
  'kind.periodic': 'Périodicité', 'kind.congruence': 'Congruence', 'kind.residue_periodic': 'Résidus périodiques', 'kind.all_prime': 'Toujours premier',
  'kind.all_square': 'Toujours un carré', 'kind.increasing': 'Croissance stricte', 'kind.growth': 'Ordre de grandeur', 'kind.equal': 'Égalité',
  'kind.inequality': 'Inégalité', 'kind.linear': 'Relation linéaire', 'kind.oeis': 'Identification OEIS',
  'cstatus.candidate': 'candidate', 'cstatus.kept': 'gardée', 'cstatus.survived': 'a résisté', 'cstatus.refuted': 'réfutée', 'cstatus.disputed': 'contre-exemple non confirmé', 'cstatus.discarded': 'écartée',
  heuristic: 'heuristique', strength: 'Portée',
  lean: 'Énoncé Lean', leanOk: 'accepté par Lean', leanBad: 'refusé par Lean', leanUnknown: 'Lean n’a pas pu le vérifier',
  leanNone: 'Pas d’énoncé Lean : la formalisation se fera par la chaîne normale.',
  duplicate: 'Déjà dans le projet : « {title} ».', openConj: 'Ouvrir la conjecture', openDossier: 'Ouvrir le dossier',
  attack: 'Chercher un contre-exemple', attacking: 'Recherche en cours…', prove: 'Tenter la preuve', keep: 'Garder comme conjecture ouverte', discard: 'Écarter',
  discardWhy: 'Pourquoi l’écarter ? (facultatif)', discardOk: 'Écarter', cancel: 'Annuler', keptToast: 'Gardée comme conjecture du projet.', dupToast: 'Cette conjecture est déjà dans le projet.',
  proveToast: 'Preuve lancée par la chaîne normale.', discardedToast: 'Conjecture écartée.',
  counter: 'Contre-exemple', counterRecomputed: 'recalculé dans un noyau neuf', counterLean: 'vérifié par Lean',
  disputed: 'Contre-exemple trouvé mais non confirmé : la conjecture n’est pas réfutée.',
  survived: 'Aucun contre-exemple : {n} cas de plus, jusqu’à n = {max}.', survivedFamily: 'Aucun contre-exemple sur {n} objets de plus.',
  attackSkipped: 'Recherche impossible : {why}', 'skip.no_code': 'la suite a été donnée terme par terme, ajoutez des termes.',
  showDiscarded: 'Conjectures écartées ({n})',
  journal: 'Journal', journalEmpty: 'Rien pour l’instant.', exportNote: 'Exporter vers une note', exportArticle: 'Exporter vers l’article',
  exportedNote: 'Journal exporté vers une note.', exportedArticle: 'Conjectures ajoutées à l’article.', openNote: 'Ouvrir la note', openArticle: 'Ouvrir l’article',
  'err.empty': 'Écrivez une question, une formule ou des termes.', 'err.too_many': 'Trop d’explorations dans ce projet : supprimez-en.',
  'err.busy': 'Une étape est déjà en cours : attendez la fin ou arrêtez-la.', 'err.not_approved': 'Ce code a été écrit par un modèle : relisez-le et approuvez-le d’abord.',
  'err.experiments_host_only': 'Le code s’exécute sur l’ordinateur hôte : autorisé seulement depuis l’hôte (réglage).',
  'err.bad_code': 'Le code est vide ou trop long.', 'err.bad_contract': 'Le code doit définir cj_columns, cj_index et cj_rows_for(n).',
  'err.no_model': 'Aucun modèle disponible pour écrire le code : écrivez-le vous-même ou reformulez.', 'err.no_code': 'Le modèle n’a pas proposé de code utilisable : écrivez-le ou reformulez.',
  'err.demo_no_kernel': 'Démonstration : pas de noyau de calcul ici, seules les suites reconnues se calculent.', 'err.calcul_busy': 'Le carnet est occupé : attendez la fin du calcul en cours.',
  'err.run_failed': 'Le calcul a échoué.', 'err.no_table': 'Le calcul n’a pas produit de tableau de données.', 'err.keep_failed': 'La conjecture n’a pas pu être créée.',
  'err.refuted': 'Cette conjecture est réfutée : il n’y a rien à prouver.', 'err.nothing_to_export': 'Aucune conjecture à exporter.', 'err.internal': 'Erreur interne : voyez le journal du serveur.',
  'err.not_checkable': 'Cette régularité ne se teste pas terme à terme.', 'err.no_more_terms': 'L’OEIS ne liste pas d’autres termes à comparer.',
  'err.not_found': 'Exploration introuvable.', 'err.no_workbench': 'Le carnet de calcul n’est pas disponible.', 'err.no_workshop': 'L’atelier de conjectures n’est pas disponible.',
  'err.no_code_step': 'Aucun code à exécuter.',
};

export const EN: Record<string, string> = {
  title: 'Explore', lead: 'From a question to a conjecture: compute, recognise, state, look for a counter-example. Every step is visible, can be stopped and stays in the journal.',
  back: 'Conjectures', question: 'Your question', questionPh: 'A question in words, a formula or the first terms of a sequence (e.g. the sum of the first n odd numbers)',
  start: 'Explore', starting: 'Preparing…', examples: 'Examples', past: 'Explorations of the project', noPast: 'No exploration yet.',
  open: 'Open', del: 'Delete', delOf: 'Delete the exploration “{q}”', deleted: 'Exploration deleted.', newOne: 'New exploration',
  candidatesN: '{n} conjecture(s)', refutedN: '{n} refuted',
  run: 'Run', rerun: 'Run again', stop: 'Stop', stopHint: 'Escape stops too.', runningNow: 'Running…', stoppedToast: 'Stopped.',
  steps: 'Steps',
  'step.explore': 'Explore', 'step.recognise': 'Recognise', 'step.state': 'State', 'step.attack': 'Attack', 'step.journal': 'Journal',
  'stepLead.explore': 'Compute data in the project’s notebook.', 'stepLead.recognise': 'Look for patterns in the data, and for the sequence in the OEIS.',
  'stepLead.state': 'Write each pattern as a precise conjecture.', 'stepLead.attack': 'Look for a counter-example, then attempt the proof.',
  'stepLead.journal': 'Everything that was tried, kept or discarded.',
  'state.todo': 'to do', 'state.running': 'running', 'state.awaiting_approval': 'to approve', 'state.done': 'done', 'state.failed': 'failed', 'state.stopped': 'stopped',
  stateOf: '{step}: {state}', seconds: '{s} s',
  recognised: 'Recognised: {what}', notRecognised: 'Not recognised: a model wrote the experiment’s code. It only runs after you approve it.',
  givenTerms: 'Given terms: nothing to compute.', byCatalogue: 'checked code, written without a model', byUser: 'code edited by you',
  code: 'Experiment code', showCode: 'Show the code', editCode: 'Edit the code', closeCode: 'Done',
  codeHint: 'Edited code becomes yours: it runs without approval.',
  noCodeYet: 'No code: the model proposed nothing. You can write it yourself.',
  inNotebook: 'Open in Calcul', output: 'Computation output',
  data: 'Data', rowsShown: 'first {n} rows of {total}', rowsAll: '{total} rows', plot: 'Plot', plotAlt: 'Plot of {col} against {x}: {n} points, from {min} to {max}{log}.',
  plotLog: ' (logarithmic scale)', noPlot: 'No plot for this data.',
  oeis: 'OEIS', oeisAgrees: '{n} identical terms', oeisShift: 'OEIS index = n + {k}', oeisFormulas: 'Formulas from the OEIS',
  'oeis.ok': 'OEIS sequences that agree with every computed term:', 'oeis.none': 'No OEIS sequence agrees with every computed term.',
  'oeis.off': 'Local mode: the OEIS is not queried (nothing leaves this computer).', 'oeis.too_short': 'Too few terms to query the OEIS.',
  'oeis.error': 'The OEIS did not answer: look-up not done.', 'oeis.unrecorded': 'Demo: only the recorded look-up (Catalan numbers) answers.',
  oeisRejected: 'Discarded: {num} differs at term n = {n}.',
  lmfdb: 'LMFDB is not queried: its interface has no search by a list of terms.',
  kept: 'Patterns kept', discarded: 'Patterns discarded', noneFound: 'No pattern found in this data.',
  sageAgrees: 'Sage finds the same generating function.', sageDiffers: 'Sage proposes another generating function: {g}',
  candidates: 'Candidate conjectures', noCandidates: 'No conjecture to state.',
  'kind.polynomial': 'Closed formula', 'kind.constant': 'Constant sequence', 'kind.rational': 'Rational function', 'kind.recurrence': 'Linear recurrence',
  'kind.holonomic': 'Recurrence with polynomial coefficients', 'kind.algebraic_gf': 'Algebraic generating function', 'kind.multiplicative': 'Multiplicativity',
  'kind.periodic': 'Periodicity', 'kind.congruence': 'Congruence', 'kind.residue_periodic': 'Periodic residues', 'kind.all_prime': 'Always prime',
  'kind.all_square': 'Always a square', 'kind.increasing': 'Strictly increasing', 'kind.growth': 'Order of growth', 'kind.equal': 'Equality',
  'kind.inequality': 'Inequality', 'kind.linear': 'Linear relation', 'kind.oeis': 'OEIS identification',
  'cstatus.candidate': 'candidate', 'cstatus.kept': 'kept', 'cstatus.survived': 'survived', 'cstatus.refuted': 'refuted', 'cstatus.disputed': 'counter-example not confirmed', 'cstatus.discarded': 'discarded',
  heuristic: 'heuristic', strength: 'Scope',
  lean: 'Lean statement', leanOk: 'accepted by Lean', leanBad: 'refused by Lean', leanUnknown: 'Lean could not check it',
  leanNone: 'No Lean statement: the normal pipeline will formalise it.',
  duplicate: 'Already in the project: “{title}”.', openConj: 'Open the conjecture', openDossier: 'Open the dossier',
  attack: 'Look for a counter-example', attacking: 'Searching…', prove: 'Attempt the proof', keep: 'Keep as an open conjecture', discard: 'Discard',
  discardWhy: 'Why discard it? (optional)', discardOk: 'Discard', cancel: 'Cancel', keptToast: 'Kept as a conjecture of the project.', dupToast: 'This conjecture is already in the project.',
  proveToast: 'Proof started through the normal pipeline.', discardedToast: 'Conjecture discarded.',
  counter: 'Counter-example', counterRecomputed: 'recomputed in a fresh kernel', counterLean: 'checked by Lean',
  disputed: 'A counter-example was found but not confirmed: the conjecture is not refuted.',
  survived: 'No counter-example: {n} more cases, up to n = {max}.', survivedFamily: 'No counter-example on {n} more objects.',
  attackSkipped: 'Search not possible: {why}', 'skip.no_code': 'the sequence was given term by term, add more terms.',
  showDiscarded: 'Discarded conjectures ({n})',
  journal: 'Journal', journalEmpty: 'Nothing yet.', exportNote: 'Export to a note', exportArticle: 'Export to the article',
  exportedNote: 'Journal exported to a note.', exportedArticle: 'Conjectures added to the article.', openNote: 'Open the note', openArticle: 'Open the article',
  'err.empty': 'Write a question, a formula or some terms.', 'err.too_many': 'Too many explorations in this project: delete some.',
  'err.busy': 'A step is already running: wait for it or stop it.', 'err.not_approved': 'This code was written by a model: review and approve it first.',
  'err.experiments_host_only': 'Code runs on the host computer: allowed only from the host (setting).',
  'err.bad_code': 'The code is empty or too long.', 'err.bad_contract': 'The code must define cj_columns, cj_index and cj_rows_for(n).',
  'err.no_model': 'No model available to write the code: write it yourself or rephrase.', 'err.no_code': 'The model proposed no usable code: write it or rephrase.',
  'err.demo_no_kernel': 'Demo: no computing kernel here, only recognised sequences are computed.', 'err.calcul_busy': 'The notebook is busy: wait for the running computation.',
  'err.run_failed': 'The computation failed.', 'err.no_table': 'The computation produced no table of data.', 'err.keep_failed': 'The conjecture could not be created.',
  'err.refuted': 'This conjecture is refuted: there is nothing to prove.', 'err.nothing_to_export': 'No conjecture to export.', 'err.internal': 'Internal error: see the server log.',
  'err.not_checkable': 'This pattern cannot be tested term by term.', 'err.no_more_terms': 'The OEIS lists no further terms to compare.',
  'err.not_found': 'Exploration not found.', 'err.no_workbench': 'The Calcul notebook is not available.', 'err.no_workshop': 'The conjecture workshop is not available.',
  'err.no_code_step': 'No code to run.',
};

export function xt(key: string, params: Record<string, string | number> = {}): string {
  const s = (i18n.base === 'en' ? EN : FR)[key] ?? FR[key] ?? key;
  return s.replace(/\{(\w+)\}/g, (_m, k: string) => String(params[k] ?? `{${k}}`));
}

export function hasX(key: string): boolean {
  return key in FR;
}

/** Text the server gives in both languages. */
export function pick(v: { fr: string; en: string } | null | undefined): string {
  if (!v) return '';
  return (i18n.base === 'en' ? v.en : v.fr) || v.fr || '';
}

/** Plain words for an API error kind of the engine (falls back to '' so callers can use the generic text). */
export function errText(kind: string): string {
  return hasX(`err.${kind}`) ? xt(`err.${kind}`) : '';
}
