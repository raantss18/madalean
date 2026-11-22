<script lang="ts" module>
  // 24×24 stroke icons (drawn for Madalean, no icon font). Decorative unless `label` is given.
  export const ICONS: Record<string, string> = {
    plus: 'M12 5v14M5 12h14',
    mail: 'M4 6h16v12H4zM4 7l8 6 8-6',
    phone: 'M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a1 1 0 0 1-1 1A16 16 0 0 1 4 5a1 1 0 0 1 1-1z',
    github: 'M9 19c-4 1.5-4-2-6-2.5M15 21v-3.5a3 3 0 0 0-.9-2.4c3-.3 6-1.4 6-6.6a5 5 0 0 0-1.4-3.6 4.7 4.7 0 0 0-.1-3.6s-1.1-.3-3.6 1.4a12.3 12.3 0 0 0-6.4 0C6.1 1.6 5 1.9 5 1.9a4.7 4.7 0 0 0-.1 3.6A5 5 0 0 0 3.5 9c0 5.2 3 6.3 6 6.6a3 3 0 0 0-.9 2.3V21',
    search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4',
    settings: 'M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
    activity: 'M3 12h4l3-8 4 16 3-8h4',
    library: 'M4 4h4v16H4zM10 4h4v16h-4zM16 5l3.5-1 3 15-3.5 1z',
    list: 'M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01',
    check: 'M5 12.5l4.5 4.5L19 7.5',
    x: 'M6 6l12 12M18 6L6 18',
    stop: 'M7 7h10v10H7z',
    play: 'M8 5l11 7-11 7z',
    home: 'M3 11l9-7 9 7M5 10v10h5v-6h4v6h5V10',
    chevronDown: 'M6 9l6 6 6-6',
    chevronUp: 'M6 15l6-6 6 6',
    chevronRight: 'M9 6l6 6-6 6',
    chevronLeft: 'M15 6l-6 6 6 6',
    undo: 'M9 14L4 9l5-5M4 9h10.5a5.5 5.5 0 0 1 0 11H11',
    download: 'M12 4v11M7 10l5 5 5-5M5 20h14',
    menu: 'M4 7h16M4 12h16M4 17h16',
    globe: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18',
    lock: 'M6 11h12v9H6zM8.5 11V8a3.5 3.5 0 0 1 7 0v3',
    cloud: 'M7 18a4.5 4.5 0 1 1 .9-8.9A6 6 0 0 1 19 11a3.5 3.5 0 0 1-1 7z',
    cpu: 'M7 7h10v10H7zM10 10h4v4h-4zM10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4',
    book: 'M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5zM4 20.5A2.5 2.5 0 0 0 6.5 23H20v-5',
    bulb: 'M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9c.6.5 1 1.2 1 2V16h5v-.1c0-.8.4-1.5 1-2A6 6 0 0 0 12 3z',
    split: 'M6 3v6a3 3 0 0 0 3 3h6a3 3 0 0 1 3 3v6M6 21v-6M18 3v4M16 5h4',
    history: 'M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2',
    send: 'M4 12l16-8-6 16-2.5-6.5z',
    edit: 'M4 20h4L19 9l-4-4L4 16zM13.5 6.5l4 4',
    trash: 'M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3',
    external: 'M14 4h6v6M20 4l-9 9M18 14v5H5V6h5',
    key: 'M14.5 4a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11zM10.5 13.5L3 21M6 18l2.5 2.5M8.5 15.5L11 18',
    device: 'M7 3h10v18H7zM11 18h2',
    refresh: 'M20 11a8 8 0 0 0-14.7-4.3L3 9M3 4v5h5M4 13a8 8 0 0 0 14.7 4.3L21 15M21 20v-5h-5',
    more: 'M5 12h.01M12 12h.01M19 12h.01',
    file: 'M14 3H6v18h12V7zM14 3v4h4',
    eye: 'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z',
    info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v6M12 7.5h.01',
    warn: 'M12 3l10 18H2zM12 10v5M12 18h.01',
    wifiOff: 'M2 8.5a15 15 0 0 1 4-2.4M10 5.1A15 15 0 0 1 22 8.5M5 12.5a10 10 0 0 1 5-2.4M14.5 10.3a10 10 0 0 1 4.5 2.2M8.5 16a5 5 0 0 1 7 0M12 19.5h.01M3 3l18 18',
    terminal: 'M4 5h16v14H4zM7 9l3 3-3 3M12 15h5',
    folder: 'M3 6h6l2 2h10v11H3z',
    sparkle: 'M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5L18 18M6 18l2.5-2.5M15.5 8.5L18 6',
    graduate: 'M2 9l10-5 10 5-10 5zM6 11v5c3 2 9 2 12 0v-5M22 9v6',
    microscope: 'M9 3l4 2-4 8-4-2zM7 12l-2 4M10 21h10M15 21a6 6 0 0 0-3-11',
    sun: 'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
    moon: 'M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z',
    command: 'M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z',
    link: 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
    tree: 'M5 4h5v4H5zM14 10h5v4h-5zM14 17h5v4h-5zM7.5 8v11H14M7.5 12H14',
    notebook: 'M6 3h12v18H6zM9 3v18M12 8h4M12 12h4',
    heart: 'M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z',
    copy: 'M9 9h11v11H9zM5 15H4V4h11v1',
    // S-AD: kinds of project items beside the article (always shown with a text label, never colour alone)
    proof: 'M3 4l5.5 13L14 4M5.2 9.5h6.6M14 17.5l2.5 2.5 4.5-5',                         // ∀ + check: a dossier / proof
    plot: 'M4 3v17h17M6.5 16c2-7.5 4.5-8.5 6.5-4.5s4 3.5 6-4.5',                         // function plot: a Calcul notebook
    cell: 'M3 5h18v14H3zM8.5 10l-2 2 2 2M15.5 10l2 2-2 2M13 9l-2 6',                     // code cell: a Calcul cell
    note: 'M5 3h10l4 4v14H5zM15 3v4h4M8.5 11h7M8.5 14.5h7M8.5 18h4',                       // page with lines: a note
    conjecture: 'M4 4h16v12h-9l-5 4v-4H4zM9.8 8.2a2.3 2.3 0 1 1 3.2 2.1c-.6.3-1 .8-1 1.4M12 13.8h.01', // speech bubble + ?
    source: 'M2.5 5.5c3.2-1.2 6.6-1 9.5 1v13c-2.9-2-6.3-2.2-9.5-1zM21.5 5.5c-3.2-1.2-6.6-1-9.5 1v13c2.9-2 6.3-2.2 9.5-1z', // open book
    image: 'M3 4h18v16H3zM3 16l5-5 5 5M13 14l3-3 5 5M16 6.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z',  // framed picture: a figure
    clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 7v5l3.5 2',                           // a version of the article
    texfile: 'M14 3H6v18h12V7zM14 3v4h4M10 11.5l-2 2.5 2 2.5M14 11.5l2 2.5-2 2.5',          // a .tex file
    bookmark: 'M6 3h12v18l-6-4.5L6 21z',                                                   // bibliography (refs.bib)
    sliders: 'M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1M15 4v4M9 10v4M17 16v4',          // settings file
    folderOpen: 'M3 19V5h6l2 2h8v3M3 19l3-8h15l-3 8z',
    panelLeft: 'M3 4h18v16H3zM9 4v16',
    panelRight: 'M3 4h18v16H3zM15 4v16',
    focus: 'M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5',
  };
</script>

<script lang="ts">
  let { name, label = '', size = 18 }: { name: string; label?: string; size?: number } = $props();
</script>

<svg
  class="ico"
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="1.8"
  stroke-linecap="round"
  stroke-linejoin="round"
  role={label ? 'img' : undefined}
  aria-label={label || undefined}
  aria-hidden={label ? undefined : 'true'}
  focusable="false"><path d={ICONS[name] ?? ''} /></svg>
