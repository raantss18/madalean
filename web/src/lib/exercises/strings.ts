// Strings and API of the « Exercices » screen (S-BE, D63): lazy-loaded with it. mg falls back to fr.
import { i18n } from '../i18n/index.svelte';
import { request, ApiError } from '../api/client';
import { errorText } from '../ui/errors';
import type { CheckResult } from '../api/types';

const FR = {
  title: 'Exercices', lead: 'Chaque énoncé a été écrit en Lean : votre preuve est contrôlée par Lean, jamais par une opinion.',
  level: 'Niveau', domain: 'Domaine', lang: 'Langue des énoncés', state: 'Avancement', all: 'Tous', search: 'Chercher',
  todo: 'À faire', solved: 'Résolu', solvedAfter: 'Résolu après la solution', tried: 'Commencé', progress: '{n} résolu(s) sur {total}',
  none: 'Aucun exercice ne correspond.', reset: 'Effacer les filtres', back: 'Tous les exercices', missing: 'Exercice introuvable.',
  'l.lycee': 'Lycée', 'l.licence': 'Licence', 'l.master': 'Master', 'l.olympiade': 'Olympiade',
  'd.arithmetique': 'Arithmétique', 'd.algebre': 'Algèbre', 'd.algebre-lineaire': 'Algèbre linéaire', 'd.analyse': 'Analyse',
  'd.ensembles': 'Ensembles et fonctions', 'd.inegalites': 'Inégalités', 'd.topologie': 'Topologie', 'd.autre': 'Autre',
  leanStatement: 'Énoncé Lean', how: 'Écrire la preuve', words: 'En mots', lean: 'En Lean', wordsLabel: 'Votre preuve en mots',
  leanLabel: 'Votre preuve Lean (la suite de « by »)', wordsNote: 'Un modèle traduit votre raisonnement en Lean. Lean vérifie cette traduction ; relisez-la. Vos mots seuls ne sont pas vérifiés.',
  check: 'Vérifier', checking: 'Vérification…', okLean: 'Lean accepte votre preuve.', okWords: 'Lean accepte une preuve qui suit votre raisonnement.',
  koLean: 'Lean refuse cette preuve.', koWords: 'Aucune preuve suivant ce raisonnement n’a été acceptée par Lean : cela ne dit pas que l’énoncé est faux.',
  formal: 'La preuve Lean acceptée', review: 'Remarques du modèle (non vérifiées)', hints: 'Indices', hint: 'Indice {n}', nextHint: 'Indice suivant ({n} sur {total})',
  triedLabel: 'Avant le premier indice : qu’avez-vous essayé ?', solution: 'Solution', showSolution: 'Voir la solution', solutionLater: 'La solution se montre après tous les indices, ou quand vous avez résolu l’exercice.',
  noSolution: 'Cet exercice n’a pas de solution.', solutionOk: 'Solution acceptée par Lean. « Expliquer » la lit ligne par ligne.', source: 'Source : {s}', licence: 'Licence : {l}',
  own: 'le vôtre', import: 'importé', teacher: 'Outils de l’enseignant', make: 'En faire un exercice', from: 'À partir de', fromDossier: 'Dossier', fromLibrary: 'Bibliothèque', choose: 'Choisir…',
  stFr: 'Énoncé en français', stMg: 'Énoncé en malgache (facultatif)', stEn: 'Énoncé en anglais (facultatif)', create: 'Créer l’exercice', created: 'Exercice créé, énoncé accepté par Lean.',
  creating: 'Lean lit l’énoncé…', sheet: 'Feuille d’exercices', sheetHint: 'Cochez des exercices dans la liste ({n} choisi(s)).', sheetTitle: 'Titre de la feuille', withSol: 'Avec les corrigés vérifiés', withLean: 'Avec les énoncés Lean',
  pick: 'Mettre « {t} » sur la feuille', pdf: 'PDF', tex: 'LaTeX', bank: 'Banque d’exercices', importFile: 'Importer un fichier', exportFile: 'Exporter mes exercices', imported: '{n} exercice(s) importé(s).',
  remove: 'Supprimer cet exercice', removed: 'Exercice supprimé.',
  'err.attempt_first': 'Dites d’abord, en quelques mots, ce que vous avez essayé.', 'err.hints_first': 'La solution vient après tous les indices.', 'err.no_more_hints': 'Il n’y a plus d’indice.',
  'err.bad_answer': 'Réponse refusée : seulement des tactiques (pas de « sorry », pas d’autre déclaration).', 'err.empty': 'Écrivez d’abord une preuve.',
  'err.solution_refused': 'Lean refuse cette solution dans votre espace : elle n’est pas montrée.', 'err.lean_unavailable': 'Lean n’a pas pu vérifier la solution : réessayez.',
  'err.bad_statement': 'L’énoncé Lean doit être un seul théorème, compris par Lean sans résultat supplémentaire.', 'err.too_large': 'Fichier ou texte trop grand.', 'err.bad_bank': 'Ce fichier n’est pas une banque d’exercices Madalean.',
  'err.bad_exercise': 'Exercice refusé : {where}.',
};
type K = keyof typeof FR;
const MG: Partial<Record<K, string>> = {
  title: 'Fanazaran-tena', lead: 'Voasoratra amin’ny Lean ny laza adina tsirairay: i Lean no manamarina ny porofonao.',
  level: 'Ambaratonga', domain: 'Sehatra', lang: 'Fitenin’ny laza adina', state: 'Fandrosoana', all: 'Rehetra', search: 'Hitady',
  todo: 'Mbola hatao', solved: 'Voavaha', solvedAfter: 'Voavaha taorian’ny vahaolana', tried: 'Natomboka', progress: '{n} voavaha amin’ny {total}',
  none: 'Tsy misy fanazaran-tena mifanaraka.', reset: 'Esory ny sivana', back: 'Ny fanazaran-tena rehetra', missing: 'Tsy hita ny fanazaran-tena.',
  'l.lycee': 'Lisea', 'l.licence': 'Lisansa', 'l.master': 'Master', 'l.olympiade': 'Olimpiada',
  'd.arithmetique': 'Aritmetika', 'd.algebre': 'Aljebra', 'd.algebre-lineaire': 'Aljebra lineera', 'd.analyse': 'Analizy', 'd.ensembles': 'Ensemble sy fonction',
  'd.inegalites': 'Tsy fitoviana', 'd.topologie': 'Topolojia', 'd.autre': 'Hafa',
  leanStatement: 'Laza adina Lean', how: 'Soraty ny porofo', words: 'Amin’ny teny', lean: 'Amin’ny Lean', wordsLabel: 'Ny porofonao amin’ny teny', leanLabel: 'Ny porofonao Lean (ny tohin’ny « by »)',
  wordsNote: 'Modely iray no mandika ny fanjohian-kevitrao amin’ny Lean. Io dikan-teny io no hamarinin’i Lean; vakio izy. Tsy voamarina ny teninao irery.',
  check: 'Hamarino', checking: 'Eo am-panamarinana…', okLean: 'Neken’i Lean ny porofonao.', okWords: 'Neken’i Lean ny porofo iray manaraka ny fanjohian-kevitrao.',
  koLean: 'Nolavin’i Lean io porofo io.', koWords: 'Tsy nisy porofo manaraka io fanjohian-kevitra io neken’i Lean: tsy midika akory izany fa diso ny laza adina.',
  formal: 'Ny porofo Lean nekena', review: 'Fanamarihan’ny modely (tsy voamarina)', hints: 'Toro-hevitra', hint: 'Toro-hevitra {n}', nextHint: 'Toro-hevitra manaraka ({n} amin’ny {total})',
  triedLabel: 'Alohan’ny toro-hevitra voalohany: inona no nandramanao?', solution: 'Vahaolana', showSolution: 'Jereo ny vahaolana', solutionLater: 'Aseho ny vahaolana aorian’ny toro-hevitra rehetra, na rehefa voavahanao.',
  noSolution: 'Tsy misy vahaolana ity fanazaran-tena ity.', solutionOk: 'Vahaolana neken’i Lean. « Hazavao » dia mamaky azy isaky ny andalana.', source: 'Loharano: {s}', licence: 'Lisansa: {l}',
  own: 'anao', import: 'nampidirina', teacher: 'Fitaovan’ny mpampianatra', make: 'Ataovy fanazaran-tena', from: 'Avy amin’ny', fromDossier: 'Dosie', fromLibrary: 'Tranomboky', choose: 'Misafidiana…',
  stFr: 'Laza adina amin’ny teny frantsay', stMg: 'Laza adina amin’ny teny malagasy (tsy voatery)', stEn: 'Laza adina amin’ny teny anglisy (tsy voatery)', create: 'Mamorona', created: 'Voaforona, neken’i Lean ny laza adina.',
  creating: 'Mamaky ny laza adina i Lean…', sheet: 'Taratasy fanazaran-tena', sheetHint: 'Mifidiana fanazaran-tena ao amin’ny lisitra ({n} voafidy).', sheetTitle: 'Lohateny', withSol: 'Miaraka amin’ny vahaolana voamarina', withLean: 'Miaraka amin’ny laza adina Lean',
  pick: 'Ataovy ao amin’ny taratasy ny « {t} »', bank: 'Fitehirizana fanazaran-tena', importFile: 'Mampiditra rakitra', exportFile: 'Avoahy ny fanazaran-tenako', imported: 'Fanazaran-tena {n} nampidirina.',
  remove: 'Fafao ity fanazaran-tena ity', removed: 'Voafafa ny fanazaran-tena.',
  'err.attempt_first': 'Lazao aloha, amin’ny teny vitsy, izay nandramanao.', 'err.hints_first': 'Aorian’ny toro-hevitra rehetra ny vahaolana.', 'err.no_more_hints': 'Tsy misy toro-hevitra intsony.',
  'err.bad_answer': 'Nolavina ny valiny: tactique ihany (tsy azo atao ny « sorry » na fanambarana hafa).', 'err.empty': 'Soraty aloha ny porofo.',
  'err.solution_refused': 'Nolavin’i Lean io vahaolana io: tsy aseho izy.', 'err.lean_unavailable': 'Tsy afaka nanamarina i Lean: andramo indray.',
  'err.too_large': 'Lehibe loatra ny rakitra na ny lahatsoratra.', 'err.bad_exercise': 'Nolavina ny fanazaran-tena: {where}.',
};
const EN: Record<K, string> = {
  title: 'Exercises', lead: 'Every statement is written in Lean: your proof is checked by Lean, never by an opinion.',
  level: 'Level', domain: 'Domain', lang: 'Language of the statements', state: 'Progress', all: 'All', search: 'Search',
  todo: 'To do', solved: 'Solved', solvedAfter: 'Solved after the solution', tried: 'Started', progress: '{n} solved out of {total}',
  none: 'No matching exercise.', reset: 'Clear the filters', back: 'All exercises', missing: 'Exercise not found.',
  'l.lycee': 'High school', 'l.licence': 'Bachelor', 'l.master': 'Master', 'l.olympiade': 'Olympiad',
  'd.arithmetique': 'Arithmetic', 'd.algebre': 'Algebra', 'd.algebre-lineaire': 'Linear algebra', 'd.analyse': 'Analysis',
  'd.ensembles': 'Sets and functions', 'd.inegalites': 'Inequalities', 'd.topologie': 'Topology', 'd.autre': 'Other',
  leanStatement: 'Lean statement', how: 'Write the proof', words: 'In words', lean: 'In Lean', wordsLabel: 'Your proof in words',
  leanLabel: 'Your Lean proof (what follows “by”)', wordsNote: 'A model translates your argument into Lean. Lean checks that translation; read it. Your words alone are not verified.',
  check: 'Check', checking: 'Checking…', okLean: 'Lean accepts your proof.', okWords: 'Lean accepts a proof that follows your argument.',
  koLean: 'Lean refuses this proof.', koWords: 'No proof following this argument was accepted by Lean: this does not mean the statement is false.',
  formal: 'The accepted Lean proof', review: 'The model’s remarks (not verified)', hints: 'Hints', hint: 'Hint {n}', nextHint: 'Next hint ({n} of {total})',
  triedLabel: 'Before the first hint: what did you try?', solution: 'Solution', showSolution: 'Show the solution', solutionLater: 'The solution is shown after every hint, or once you solved the exercise.',
  noSolution: 'This exercise has no solution.', solutionOk: 'Solution accepted by Lean. “Explain” reads it line by line.', source: 'Source: {s}', licence: 'Licence: {l}',
  own: 'yours', import: 'imported', teacher: 'Teacher tools', make: 'Make it an exercise', from: 'From', fromDossier: 'Dossier', fromLibrary: 'Library', choose: 'Choose…',
  stFr: 'Statement in French', stMg: 'Statement in Malagasy (optional)', stEn: 'Statement in English (optional)', create: 'Create the exercise', created: 'Exercise created, statement accepted by Lean.',
  creating: 'Lean reads the statement…', sheet: 'Worksheet', sheetHint: 'Tick exercises in the list ({n} chosen).', sheetTitle: 'Worksheet title', withSol: 'With the verified solutions', withLean: 'With the Lean statements',
  pick: 'Put “{t}” on the worksheet', pdf: 'PDF', tex: 'LaTeX', bank: 'Exercise bank', importFile: 'Import a file', exportFile: 'Export my exercises', imported: '{n} exercise(s) imported.',
  remove: 'Delete this exercise', removed: 'Exercise deleted.',
  'err.attempt_first': 'First say, in a few words, what you tried.', 'err.hints_first': 'The solution comes after every hint.', 'err.no_more_hints': 'There is no hint left.',
  'err.bad_answer': 'Answer refused: tactics only (no “sorry”, no other declaration).', 'err.empty': 'Write a proof first.',
  'err.solution_refused': 'Lean refuses this solution in your workspace: it is not shown.', 'err.lean_unavailable': 'Lean could not check the solution: try again.',
  'err.bad_statement': 'The Lean statement must be a single theorem Lean reads without any extra result.', 'err.too_large': 'File or text too large.', 'err.bad_bank': 'This file is not a Madalean exercise bank.',
  'err.bad_exercise': 'Exercise refused: {where}.',
};
export const CATALOGUES = { FR, MG, EN };

export function xt(key: K, params: Record<string, string | number> = {}): string {
  const s = (i18n.lang === 'en' ? EN : i18n.lang === 'mg' ? MG : FR)[key] ?? FR[key];
  return s.replace(/\{(\w+)\}/g, (_m, k: string) => String(params[k] ?? ''));
}
export function xError(e: unknown): string {
  if (e instanceof ApiError && `err.${e.kind}` in FR) return xt(`err.${e.kind}` as K, { where: String(e.body['where'] ?? '') });
  return errorText(e);
}

export type Tr = { fr: string; mg?: string; en?: string };
export interface Progress { attempts: number; hints: number; solved: boolean; how?: 'lean' | 'words' | 'after_solution'; tried?: boolean; seen?: boolean }
export interface Exercise { id: string; level: string; domain: string; title: Tr; statement: Tr; lean: string; source: string; licence: string;
  origin: 'seed' | 'own' | 'import'; hints: number; has_solution: boolean; progress: Progress | null }
export interface Verdict { ok: boolean; check: CheckResult | null; lean: string; review: string; progress: Progress }

const enc = encodeURIComponent;
const x = (id: string) => `/exercises/${enc(id)}`;
export const exercises = {
  list: () => request<{ exercises: Exercise[]; levels: string[]; domains: string[] }>('GET', '/exercises'),
  submit: (id: string, kind: 'lean' | 'words', text: string) => request<Verdict>('POST', `${x(id)}/submit`, { kind, text }),
  hint: (id: string, body: { tried?: string; again?: boolean }) => request<{ hints: Tr[]; progress: Progress }>('POST', `${x(id)}/hint`, body),
  solution: (id: string) => request<{ code: string; workspace: string; progress: Progress }>('POST', `${x(id)}/solution`, {}),
  create: (body: Record<string, unknown>) => request<{ exercise: Exercise }>('POST', '/exercises', body),
  importBank: (text: string) => request<{ ids: string[] }>('POST', '/exercises/import', { text }),
  remove: (id: string) => request<unknown>('DELETE', x(id)),
  exportUrl: '/api/exercises/export',
  sheetUrl: (q: { ids: string[]; title: string; lang: string; solutions: boolean; lean: boolean; format: 'pdf' | 'tex' }) =>
    `/api/exercises/worksheet?ids=${enc(q.ids.join(','))}&title=${enc(q.title)}&lang=${q.lang}&format=${q.format}${q.solutions ? '&solutions=1' : ''}${q.lean ? '&lean=1' : ''}`,
};
